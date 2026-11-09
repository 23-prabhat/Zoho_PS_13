"""Versioned objective answer checks. Pass rates describe these fixtures only."""
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION = "strict-v1"
FIXTURES = Path(__file__).resolve().parents[1] / "benchmarks/quality_strict_v1.jsonl"
KINDS = {"exact", "one_of", "number_unit", "json", "manual"}


def load_cases(path=FIXTURES):
    cases = []
    ids = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"]:
            raise ValueError(f"{path}:{number}: nonempty string id required")
        if case["id"] in ids:
            raise ValueError(f"{path}:{number}: duplicate id {case['id']}")
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            raise ValueError(f"{path}:{number}: nonempty prompt required")
        if not isinstance(case.get("category"), str) or not case["category"]:
            raise ValueError(f"{path}:{number}: category required")
        grader = case.get("grader", {})
        kind = grader.get("kind") if isinstance(grader, dict) else None
        if kind not in KINDS:
            raise ValueError(f"{path}:{number}: unsupported grader")
        if kind == "exact" and not isinstance(grader.get("expected"), str):
            raise ValueError("exact grader requires expected text")
        if kind == "one_of" and (not isinstance(grader.get("expected"), list) or
                not grader["expected"] or not all(isinstance(x, str) for x in grader["expected"])):
            raise ValueError("one_of grader requires nonempty text alternatives")
        if kind == "number_unit":
            if not isinstance(grader.get("units"), dict) or not grader["units"]:
                raise ValueError("number_unit requires unit definitions")
            for unit, definition in grader["units"].items():
                if not unit or not isinstance(definition, dict):
                    raise ValueError("invalid unit definition")
                for key in ("value", "tolerance"):
                    try:
                        value = Decimal(str(definition.get(key)))
                    except InvalidOperation as error:
                        raise ValueError("numeric value/tolerance required") from error
                    if not value.is_finite() or (key == "tolerance" and value < 0):
                        raise ValueError("finite values and nonnegative tolerances required")
        if kind == "json" and "expected" not in grader:
            raise ValueError("json grader requires expected value")
        ids.add(case["id"])
        # Long-context fixtures specify transparent synthetic padding, not hidden data.
        if "padding_words" in case:
            count = case["padding_words"]
            if type(count) is not int or not 0 <= count <= 1500 or "{padding}" not in case["prompt"]:
                raise ValueError("padding_words must be 0..1500 and have a placeholder")
            case["prompt"] = case["prompt"].replace("{padding}", "background " * count)
        cases.append(case)
    if not cases:
        raise ValueError("quality fixture set is empty")
    return cases


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_typed_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def grade_answer(case, answer):
    """Trim boundary whitespace only; never accept a substring as a full answer."""
    grader = case.get("grader", {"kind": "manual"})
    kind = grader["kind"]
    result = dict(grader_version=VERSION, grader_kind=kind, strict_status="needs_review",
                  strict_pass="", grading_reason="Open-ended answer requires human review")
    if not isinstance(answer, str):
        raise ValueError("answer must be text")
    if kind == "manual":
        return result
    text = answer.strip()
    reason = "Full answer differs from the expected response"
    if kind == "exact":
        passed = text == grader["expected"]
    elif kind == "one_of":
        passed = text in grader["expected"]
    elif kind == "number_unit":
        match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z]+)", text)
        passed = False
        reason = "Expected only a finite number and a supported unit within the declared tolerance"
        if match:
            value, unit = Decimal(match[1]), match[2].lower()
            allowed = {name.lower(): definition for name, definition in grader["units"].items()}
            if unit in allowed:
                spec = allowed[unit]
                passed = abs(value - Decimal(str(spec["value"]))) <= Decimal(str(spec["tolerance"]))
    elif kind == "json":
        reason = "Expected valid JSON with the exact requested keys, types and values; no surrounding prose"
        try:
            value = json.loads(text, object_pairs_hook=_unique_object,
                               parse_constant=lambda x: (_ for _ in ()).throw(ValueError("non-finite JSON")))
            passed = _typed_equal(value, grader["expected"])
        except (ValueError, TypeError):
            passed = False
    else:
        raise ValueError(f"Unknown grader {kind}")
    result.update(strict_status="pass" if passed else "fail", strict_pass=int(passed),
                  grading_reason="All declared objective checks passed" if passed else reason)
    return result


def summarize(rows):
    errors = [row for row in rows if row.get("status") == "error"]
    objective = [row for row in rows if row.get("strict_status") in ("pass", "fail") and row.get("status", "ok") == "ok"]
    passed = sum(row["strict_status"] == "pass" for row in objective)
    return dict(objective_cases=len(objective), passed=passed, failed=len(objective)-passed,
        needs_review=sum(row.get("strict_status") == "needs_review" for row in rows),
        execution_errors=len(errors), pass_percent=round(100*passed/len(objective), 2) if objective else None)
