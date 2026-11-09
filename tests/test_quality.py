"""Adversarial grader checks; no model downloads or generation required."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from answer_quality import FIXTURES, grade_answer, load_cases, summarize
from evaluate_quality import grade_rows, write_summary
from tune_kv_cache import choose_candidates, validate_reused_baseline, measure_allocation
import tune_kv_cache
import run_benchmarks


class QualityGradingTests(unittest.TestCase):
    def case(self, kind="exact", expected="local private offline"):
        return dict(id="fixture", category="instruction", prompt="Test prompt", grader=dict(kind=kind, expected=expected))

    def test_exact_rejects_added_words_punctuation_and_wrong_case(self):
        case=self.case()
        for answer in ("These words are local private offline", "local private offline.", "Local private offline", "not local private offline"):
            self.assertEqual(grade_answer(case,answer)["strict_status"],"fail")
        self.assertEqual(grade_answer(case,"\nlocal private offline\n")["strict_status"],"pass")

    def test_substrings_do_not_satisfy_full_answers(self):
        self.assertEqual(grade_answer(self.case(expected="no"),"not recommended")["strict_status"],"fail")

    def test_exact_internal_whitespace_is_checked(self):
        self.assertEqual(grade_answer(self.case(),"local  private offline")["strict_status"],"fail")

    def test_one_of_only_accepts_declared_alternatives(self):
        case=self.case("one_of",["CPU", "cpu"])
        self.assertEqual(grade_answer(case,"CPU")["strict_status"],"pass")
        self.assertEqual(grade_answer(case,"CPU means central processing unit")["strict_status"],"fail")

    def test_units_accept_equivalent_binary_and_decimal_storage(self):
        case=next(c for c in load_cases() if c["id"]=="strict-013")
        for answer in ("3 GB", "3.0gb", "2.794 GiB"):
            self.assertEqual(grade_answer(case,answer)["strict_status"],"pass",answer)
        for answer in ("2.8125 GB", "2.8125 GiB", "3 GiB", "3 MB", "The answer is 3 GB", "3 GB or 12 GB"):
            self.assertEqual(grade_answer(case,answer)["strict_status"],"fail",answer)

    def test_nonfinite_and_malformed_numbers_fail(self):
        case=next(c for c in load_cases() if c["id"]=="strict-013")
        for answer in ("NaN GB", "Infinity GB", "3e99 GB", " GB", "3.1.2 GB"):
            self.assertEqual(grade_answer(case,answer)["strict_status"],"fail")

    def test_json_ignores_object_key_order_only(self):
        case=self.case("json",dict(device="CPU",offline=True))
        self.assertEqual(grade_answer(case,' {"offline":true,"device":"CPU"} ')["strict_status"],"pass")
        for answer in ('```json\n{"device":"CPU","offline":true}\n```', '{"device":"CPU","offline":true,"extra":1}',
                       '{"device":"CPU","offline":1}', '{"device":"CPU","device":"CPU","offline":true}',
                       '{"device":"CPU","offline":NaN}'):
            self.assertEqual(grade_answer(case,answer)["strict_status"],"fail",answer)

    def test_json_array_types_and_order_are_checked(self):
        case=self.case("json",[2,4,6])
        for answer in ('[6,4,2]','[2,4,6.0]','[2,4,"6"]'):
            self.assertEqual(grade_answer(case,answer)["strict_status"],"fail")

    def test_manual_answers_never_get_automatic_correctness_credit(self):
        result=grade_answer(self.case("manual"),"quantization is always perfect")
        self.assertEqual(result["strict_status"],"needs_review")
        self.assertEqual(result["strict_pass"],"")

    def test_missing_results_are_execution_errors_not_model_failures(self):
        rows=grade_rows([], [self.case()], "profile")
        result=summarize(rows)
        self.assertEqual(result["objective_cases"],0)
        self.assertEqual(result["execution_errors"],1)
        self.assertIsNone(result["pass_percent"])

    def test_duplicate_and_unknown_result_ids_are_rejected(self):
        with self.assertRaises(ValueError):grade_rows([dict(id="other",response="OK")],[self.case()],"profile")
        with self.assertRaises(ValueError):grade_rows([dict(id="fixture",response="OK")]*2,[self.case()],"profile")

    def test_declared_fixture_set_has_unique_ids_and_objective_coverage(self):
        cases=load_cases()
        self.assertEqual(len(cases),24)
        self.assertEqual(sum(c["grader"]["kind"]!="manual" for c in cases),22)
        self.assertEqual(sum(c["category"]=="long-context" for c in cases),4)
        self.assertFalse(any("{padding}" in c["prompt"] for c in cases))

    def test_fixture_loader_rejects_duplicates_and_invalid_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"fixture.jsonl"
            path.write_text(json.dumps(self.case())+'\n'+json.dumps(self.case())+'\n')
            with self.assertRaises(ValueError):load_cases(path)
            case=self.case("unknown")
            path.write_text(json.dumps(case)+'\n')
            with self.assertRaises(ValueError):load_cases(path)
            case=self.case("number_unit")
            case["grader"]["units"]={"GB":{"value":"3","tolerance":"not-a-number"}}
            path.write_text(json.dumps(case)+'\n')
            with self.assertRaises(ValueError):load_cases(path)

    def test_summary_separates_pass_failure_review_and_execution(self):
        rows=[dict(strict_status="pass"),dict(strict_status="fail"),dict(strict_status="needs_review"),
              dict(status="error",strict_status="execution_error")]
        result=summarize(rows)
        self.assertEqual((result["passed"],result["failed"],result["needs_review"],result["execution_errors"]),(1,1,1,1))
        self.assertEqual(result["pass_percent"],50)

    def test_saved_responses_can_be_regraded_without_generation(self):
        rows=grade_rows([dict(id="fixture",response="local private offline",status="ok")],[self.case()],"profile")
        with tempfile.TemporaryDirectory() as folder:
            report=write_summary(Path(folder),rows,"fixture-hash")
            self.assertEqual(report["profiles"]["profile"]["passed"],1)
            self.assertIn("not general accuracy",(Path(folder)/"summary.md").read_text())

    def test_main_quality_suite_uses_one_greedy_answer_per_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            cases=load_cases()
            generated=[dict(id=c["id"],response="wrong",status="ok") for c in cases]
            models={name:Path(folder)/name for name in ("int4","int8","fp16")}
            for path in models.values():path.mkdir()
            with patch.object(run_benchmarks,"run_cpp",return_value=generated) as run, patch.object(run_benchmarks,"MODELS",models):
                rows=run_benchmarks.quality_suite(Path(folder),SimpleNamespace(repetitions=5,warmup_runs=1,max_new_tokens=64))
            self.assertEqual(run.call_count,3)
            self.assertTrue(all(c.args[3].repetitions==1 and c.args[3].warmup_runs==0 for c in run.call_args_list))
            self.assertEqual(len(rows),72)
            self.assertTrue(all("strict_status" in row for row in rows))

    def test_fast_cache_candidate_is_rejected_if_a_baseline_pass_is_lost(self):
        conv=[]
        for profile,warm in (("int4-auto",1000),("int4-prefix-64",100)):
            for identity,latency in (("turn-1",2000),("turn-2",warm)):
                conv.append(dict(profile=profile,id=identity,ttft_ms=latency,status="ok",strict_status="pass"))
        quality=[dict(profile="int4-auto",id="case",strict_status="pass",status="ok"),
                 dict(profile="int4-prefix-64",id="case",strict_status="fail",status="ok")]
        decision=choose_candidates(conv,quality,{"int4-auto":1000,"int4-prefix-64":100})
        self.assertIsNone(decision["experimental_candidate"])
        self.assertEqual(decision["profiles"]["int4-prefix-64"]["regressions_on_baseline_passes"],["case"])

    def test_cache_screening_is_explicitly_opt_in_and_never_rewrites_defaults(self):
        conv=[];quality=[]
        for profile,warm in (("int4-auto",1000),("int4-prefix-64",100)):
            for identity,latency in (("turn-1",2000),("turn-2",warm)):
                conv.append(dict(profile=profile,id=identity,ttft_ms=latency,status="ok",strict_status="pass"))
            quality.append(dict(profile=profile,id="case",strict_status="pass",status="ok"))
        decision=choose_candidates(conv,quality,{"int4-auto":1000,"int4-prefix-64":100})
        self.assertEqual(decision["experimental_candidate"],"int4-prefix-64")
        self.assertFalse(decision["default_change_justified"])
        for identity,latency in (("turn-1",2000),("turn-2",200)):
            conv.append(dict(profile="int4-prefix-u4",id=identity,ttft_ms=latency,status="ok",strict_status="pass"))
        for profile in ("int4-auto", "int4-prefix-64"):
            quality.append(dict(profile=profile,id="extra",strict_status="fail",status="ok"))
        quality.extend([dict(profile="int4-prefix-u4",id="case",strict_status="pass",status="ok"),
                        dict(profile="int4-prefix-u4",id="extra",strict_status="pass",status="ok")])
        decision=choose_candidates(conv,quality,{"int4-auto":1000,"int4-prefix-64":100,"int4-prefix-u4":200})
        self.assertEqual(decision["memory_focused_candidate"],"int4-prefix-64")
        self.assertEqual(decision["quality_focused_candidate"],"int4-prefix-u4")
        self.assertEqual(set(decision["eligible_pareto_frontier"]),{"int4-prefix-64","int4-prefix-u4"})

    def test_cache_screen_rejects_omitted_failed_fixtures_and_conversation_turns(self):
        conv=[]; quality=[]
        for profile, warm in (("int4-auto",1000),("int4-prefix-64",100)):
            for identity, latency in (("turn-1",2000),("turn-2",warm)):
                conv.append(dict(profile=profile,id=identity,ttft_ms=latency,status="ok",strict_status="pass"))
            quality.append(dict(profile=profile,id="pass",strict_status="pass",status="ok"))
            quality.append(dict(profile=profile,id="fail",strict_status="fail",status="ok"))
        allocations={"int4-auto":1000,"int4-prefix-64":100}
        self.assertIsNotNone(choose_candidates(conv,quality,allocations)["experimental_candidate"])
        missing=[r for r in quality if not (r["profile"]=="int4-prefix-64" and r["id"]=="fail")]
        self.assertIsNone(choose_candidates(conv,missing,allocations)["experimental_candidate"])
        missing=[r for r in conv if not (r["profile"]=="int4-prefix-64" and r["id"]=="turn-2")]
        self.assertIsNone(choose_candidates(missing,quality,allocations)["experimental_candidate"])

    def test_cache_screen_rejects_invalid_latency_and_failed_baseline(self):
        quality=[dict(profile=p,id="case",strict_status="pass",status="ok")
                 for p in ("int4-auto","int4-prefix-64")]
        for invalid in ("nan", "inf", "-1", "", "broken"):
            conv=[dict(profile=p,id=i,ttft_ms=(invalid if p.endswith("64") and i=="turn-2" else latency),
                       status="ok",strict_status="pass")
                  for p in ("int4-auto","int4-prefix-64") for i,latency in (("turn-1",2000),("turn-2",1000))]
            decision=choose_candidates(conv,quality,{"int4-auto":1000,"int4-prefix-64":100})
            self.assertIsNone(decision["experimental_candidate"],invalid)
        quality[0]["status"]="error"
        conv=[dict(profile=p,id=i,ttft_ms=latency,status="ok",strict_status="pass")
              for p in ("int4-auto","int4-prefix-64") for i,latency in (("turn-1",2000),("turn-2",100))]
        self.assertIsNone(choose_candidates(conv,quality,{"int4-prefix-64":100})["experimental_candidate"])

    def test_baseline_reuse_requires_matching_provenance_and_all_runtime_settings(self):
        manifest=dict(source=dict(revision="revision"),export=dict(sha256={"openvino_model.bin":"artifact"}))
        metadata=dict(prompts_sha256="prompts",binary_sha256="binary",model_manifest_sha256="manifest",
                      model_revision="revision",artifact_hash="artifact",weight_format="int4",
                      runtime_version="2026.4.1",command=["benchmark","--greedy"])
        row=dict(device="CPU",max_new_tokens="64",thread_setting="4",kv_cache_precision="auto",
                 prefix_caching="0",context_budget="2048",cache_eviction="0",conversation="0",
                 num_kv_blocks="0",cache_size_gb="0",max_num_batched_tokens="256",
                 eviction_start="32",eviction_recent="128",eviction_max="672")
        def validate(meta, rows):
            return validate_reused_baseline(meta,rows,"prompts","binary","manifest",manifest)
        validate(metadata,[row])
        for key in ("prompts_sha256","binary_sha256","model_manifest_sha256","artifact_hash","runtime_version"):
            with self.subTest(provenance=key), self.assertRaises(ValueError):
                validate({**metadata,key:"different"},[row])
        for key in row:
            with self.subTest(setting=key), self.assertRaises(ValueError):
                validate(metadata,[{**row,key:"different"}])
        with self.assertRaises(ValueError):validate(metadata,[])
        with self.assertRaises(ValueError):validate({**metadata,"command":["--do-sample"]},[row])

    def test_allocation_probe_failure_timeout_and_empty_output_remain_failures(self):
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"probe.csv"
            for effect in (SimpleNamespace(returncode=1,stdout="",stderr="unsupported"),
                           subprocess.TimeoutExpired(["probe"],120)):
                mocked=(dict(side_effect=effect) if isinstance(effect,Exception) else dict(return_value=effect))
                with patch.object(tune_kv_cache.subprocess,"run",**mocked):
                    self.assertIsNone(measure_allocation(["probe"],output))
                self.assertTrue(output.with_suffix(".txt").read_text())
            for content in ("cache_allocated_bytes\n", "cache_allocated_bytes\n-1\n", "wrong_header\n12\n"):
                output.write_text(content)
                with patch.object(tune_kv_cache.subprocess,"run",return_value=SimpleNamespace(returncode=0,stdout="",stderr="")):
                    self.assertIsNone(measure_allocation(["probe"],output))

    def test_allocation_probe_returns_observed_positive_peak(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/"probe.csv"
            output.write_text("cache_allocated_bytes\n1024\n2048\n")
            with patch.object(tune_kv_cache.subprocess,"run",return_value=SimpleNamespace(returncode=0,stdout="saved",stderr="")):
                self.assertEqual(measure_allocation(["probe"],output),2048)


if __name__=="__main__":unittest.main()
