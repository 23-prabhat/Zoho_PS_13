# Quality rubric

The current objective suite is `quality_strict_v1.jsonl`: 22 checks and two
open-ended answers kept separate for human review. Run `scripts/evaluate_quality.py`
or `scripts/run_benchmarks.py --suite quality`. Exact, numeric/unit and typed-JSON
graders check the full response. Scores measure only those declared tasks,
including formatting, and are not general model accuracy. Execution errors are
separate from failed model answers. See `guides/answer-quality.md` for the contract,
re-scoring, cache comparison and adversarial grader tests.

## Legacy five-case keyword rubric

The script applies a small keyword/concept matching heuristic (including substring
matches), not a semantic judge. The descriptions below are the intended manual
rubric. Automatic scores can miss paraphrases and can award points to incorrect
answers or extra words. Review the saved response for each case, especially exact
instruction compliance. Repeating greedy decoding is a repeatability check, not
additional independent quality evidence. Do not present these scores as accuracy.

The storage case uses decimal GB: 1.5 billion weights times two bytes is 3 billion
bytes = 3 GB, approximately 2.794 GiB. A historical fixture incorrectly accepted
"2.8125 gigabytes"; that alternative was removed during the final audit. Historical
scores and their original fixture are retained in the curated evidence without
retroactive relabeling.

- 0: incorrect or unusable
- 1: partly correct or materially incomplete
- 2: correct for the supplied task
