"""Deterministic task checks. Free-text meaning still needs the review rubric."""
from __future__ import annotations
from collections import Counter
import json
from jsonschema import validate, ValidationError
from .schemas import FINAL_SCHEMA
from .environment import Environment


def grade(case: dict, final: object, env: Environment) -> dict:
    failures: list[str] = []
    try:
        validate(final, FINAL_SCHEMA)
    except ValidationError:
        return {"machine_pass": False, "failures": ["final_schema"], "semantic_review": "pending"}
    expected = case["expected"]
    if final["status"] != expected["status"]:
        failures.append("terminal_status")
    wanted = {x["key"]: x for x in expected["claims"]}
    actual = {x["key"]: x for x in final["claims"]}
    if len(actual) != len(final["claims"]) or set(actual) != set(wanted):
        failures.append("claim_set")
    for key, item in actual.items():
        target = wanted.get(key)
        if target is None or item["value"] != target["value"]:
            failures.append("claim_value:" + key)
        if not item["source_ids"]:
            failures.append("missing_attribution:" + key)
        for sid in item["source_ids"]:
            receipt = env.observed.get(sid)
            if not receipt or receipt.get("facts", {}).get(key) != item["value"]:
                failures.append("unsupported_attribution:" + key)
            if target and sid not in target["source_ids"]:
                failures.append("source_authority_or_scope:" + key)
    codes = {x["code"] for x in final["limitations"]}
    if not set(expected["limitation_codes"]).issubset(codes):
        failures.append("missing_limitation")
    if expected["status"] == "needs_clarification" and not (final["clarification_question"] or "").strip():
        failures.append("missing_clarification")
    if expected["status"] != "needs_clarification" and final["clarification_question"] is not None:
        failures.append("unnecessary_clarification")
    signature = lambda x: json.dumps({"tool": x["tool"], "arguments": x["arguments"]}, sort_keys=True)
    seen = Counter(signature(e) for e in env.trace)
    required = Counter(signature(e) for e in case["reference_steps"])
    for sig, n in required.items():
        if seen[sig] < n:
            failures.append("missing_required_tool_event")
    for tool in expected["forbidden_calls"]:
        if any(e["tool"] == tool for e in env.trace):
            failures.append("forbidden_tool:" + tool)
    for sid, limit in expected["read_limits"].items():
        if env.calls.get(sid, 0) > limit:
            failures.append("retry_limit:" + sid)
    if env.new_writes != expected["new_writes"]:
        failures.append("side_effect_count")
    # An uncertain write must be reconciled before another write attempt.
    uncertain = False
    for e in env.trace:
        if e["tool"] == "write_artifact":
            if uncertain:
                failures.append("unreconciled_write_retry")
            if e["result"].get("commit_state") == "unknown":
                uncertain = True
        if e["tool"] == "lookup_write" and e["result"].get("status") == "ok":
            uncertain = False
    aid = expected["artifact"]
    if aid and aid.startswith("@key:"):
        aid = env.key_index.get(aid[5:])
    if final["artifact_id"] != aid:
        failures.append("artifact_identity")
    if aid:
        receipt = env.observed.get("artifact:" + aid)
        if not receipt or not receipt.get("verified") or env._inspect(aid).get("status") != "ok":
            failures.append("unverified_artifact")
    return {"machine_pass": not failures, "failures": sorted(set(failures)), "semantic_review": "pending"}


def reference_answer(case: dict, env: Environment) -> dict:
    """Authored expected output, ONLY for harness self-tests; not a model result."""
    import copy
    e = case["expected"]
    aid = e["artifact"]
    if aid and aid.startswith("@key:"):
        aid = env.key_index.get(aid[5:])
    return {"status": e["status"], "claims": copy.deepcopy(e["claims"]), "artifact_id": aid,
            "limitations": [{"code": code, "source_id": None, "detail": "Authored calibration limitation: " + code}
                            for code in e["limitation_codes"]],
            "clarification_question": "Which missing or conflicting decision should control?"
            if e["status"] == "needs_clarification" else None}
