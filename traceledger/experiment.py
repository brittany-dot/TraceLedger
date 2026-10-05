"""Freeze and run a paired live experiment; planning never calls the API.

A full protocol has 24 scenarios x 3 repeats x 2 conditions = 144 episodes.
An episode can require several API requests. A request cap is NOT a dollar cap.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import time
from pathlib import Path
from typing import Any
from .agent import load_cases, run_agent, RunError, utc, append_event, sdk_version, safe_error
from .environment import Environment
from .grading import grade
from .schemas import BASELINE, INTERVENTION, TOOLS, FINAL_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
PILOT_IDS = ["CTX-01", "CTX-05", "HAND-01", "HAND-02", "REC-01", "REC-05"]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def source_hashes(root: Path = ROOT) -> dict:
    paths = sorted((root / "traceledger").glob("*.py"))
    paths += [root / "data/cases.jsonl", root / "pyproject.toml", root / "docs/REVIEW_RUBRIC.md"]
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in paths}


def runtime_versions() -> dict:
    """Record the execution and grading runtimes, not only the SDK."""
    try:
        validator = importlib.metadata.version("jsonschema")
    except importlib.metadata.PackageNotFoundError:
        validator = "unavailable"
    return {"python": platform.python_version(), "openai": sdk_version(), "jsonschema": validator}


def build_plan(model: str, mode: str = "full", max_requests: int | None = None,
               reasoning_effort: str | None = None, seed: int = 17, root: Path = ROOT) -> dict:
    if not model.strip() or mode not in ("pilot", "full"):
        raise ValueError("Explicit model and pilot/full mode required")
    all_cases = load_cases(root / "data/cases.jsonl")
    cases = [c for c in all_cases if mode == "full" or c["id"] in PILOT_IDS]
    repeats = 3 if mode == "full" else 1
    rng = random.Random(seed)
    schedule = []
    # Validation stays after development. Randomize blocks and condition order within each block.
    for split in ("development", "reserved_validation"):
        blocks = [(c, r) for c in cases if c["split"] == split for r in range(1, repeats + 1)]
        rng.shuffle(blocks)
        for case, repeat in blocks:
            conditions = ["baseline", "intervention"]
            rng.shuffle(conditions)
            for condition in conditions:
                schedule.append({"attempt_id": f"{case['id']}.r{repeat:02d}.{condition}",
                    "case_id": case["id"], "family": case["family"], "split": case["split"],
                    "repeat": repeat, "condition": condition})
    cap = max_requests if max_requests is not None else len(schedule) * 12
    if cap < 1:
        raise ValueError("Request cap must be positive")
    return {"protocol_version": "0.2", "created_utc": utc(), "model_requested": model,
        "mode": mode, "case_count": len(cases), "repeats": repeats, "order_seed": seed,
        "sdk_version_at_freeze": sdk_version(), "python_version_at_freeze": platform.python_version(),
        "runtime_versions_at_freeze": runtime_versions(),
        "source_hashes": source_hashes(root),
        "prompt_hashes": {"baseline": sha(BASELINE.encode()), "intervention": sha(INTERVENTION.encode())},
        "tool_schema_sha256": sha(canonical(TOOLS)), "final_schema_sha256": sha(canonical(FINAL_SCHEMA)),
        "settings": {"max_turns": 12, "max_tool_calls": 24, "max_output_tokens": 2500,
                     "reasoning_effort": reasoning_effort, "sdk_max_retries": 0,
                     "timeout_seconds": 45.0, "max_api_requests": cap,
                     "stop_on_http_status": [401, 403, 404, 429], "between_episodes_seconds": 0.0},
        "metrics": {"primary": "machine passes / all attempted episodes",
                    "secondary": "machine passes / schema-valid completions",
                    "semantic_pass": "pending independent review",
                    "paired_unit": "scenario mean of repeated paired conditions",
                    "bootstrap_replicates": 2000, "bootstrap_seed": 107},
        "schedule": schedule,
        "scope_note": "Synthetic protocol benchmark. Reserved validation is authored, visible and not an independent holdout.",
        "billing_note": "Cap bounds SDK create calls (retries disabled), not billed dollars or provider execution certainty."}


def seal(plan: dict) -> dict:
    plan = dict(plan)
    plan.pop("plan_sha256", None)
    plan["plan_sha256"] = sha(canonical(plan))
    return plan


def verify_plan(plan: dict, root: Path = ROOT) -> None:
    if plan.get("plan_sha256") != seal(plan)["plan_sha256"]:
        raise ValueError("Plan hash mismatch. Do not modify a registered plan.")
    if plan.get("source_hashes") != source_hashes(root):
        raise ValueError("Source/fixture/grader changed after freeze; create a new versioned plan.")
    if plan["prompt_hashes"] != {"baseline": sha(BASELINE.encode()), "intervention": sha(INTERVENTION.encode())}:
        raise ValueError("Prompt mismatch")
    if plan["tool_schema_sha256"] != sha(canonical(TOOLS)) or plan["final_schema_sha256"] != sha(canonical(FINAL_SCHEMA)):
        raise ValueError("Schema mismatch")


def recover_checkpoint(path: Path) -> dict:
    p = path / "checkpoint.json"
    if p.exists():
        value = json.loads(p.read_text(encoding="utf-8"))
        return {key: value.get(key, []) for key in ("responses", "api_requests", "trace")}
    return {"responses": [], "api_requests": [], "trace": []}


def execute_plan(plan: dict, client: Any, out: Path, run_kind: str = "live_api") -> dict:
    """Dependency injection is for local tests only; those tests must label run_kind=mocked_test."""
    from .analyze import summarize
    verify_plan(plan)
    if run_kind not in ("live_api", "mocked_test"):
        raise ValueError("Unknown run kind")
    if out.exists():
        raise ValueError("Output path exists. Evidence is not overwritten or silently resumed.")
    out.mkdir(parents=True)
    (out / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    runtime = {"run_kind": run_kind, "started_utc": utc(), "sdk_version": sdk_version(),
               "python_version": platform.python_version(), "runtime_versions": runtime_versions(), "plan_sha256": plan["plan_sha256"],
               "semantic_review": "pending", "model_snapshot_note": "Requested and returned identifiers are recorded verbatim; an alias is not an inferred snapshot."}
    (out / "runtime.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    cases = {c["id"]: c for c in load_cases(ROOT / "data/cases.jsonl")}
    records, api_requests = [], 0
    cap = plan["settings"]["max_api_requests"]

    def before_request() -> None:
        nonlocal api_requests
        if api_requests >= cap:
            raise RunError("api_budget", "Global API request cap reached.")
        api_requests += 1

    for item in plan["schedule"]:
        if api_requests >= cap:
            break
        case = cases[item["case_id"]]
        root = out / item["attempt_id"]
        rec = {**item, "run_kind": run_kind, "started_utc": utc()}
        append_event(out / "attempt_events.jsonl", {"event": "attempt_started", **rec})
        env = Environment(case["environment"], root)
        stop = False
        try:
            result = run_agent(client, plan["model_requested"], case["prompt"], env, item["condition"],
                max_turns=plan["settings"]["max_turns"], max_tool_calls=plan["settings"]["max_tool_calls"],
                max_output_tokens=plan["settings"]["max_output_tokens"],
                reasoning_effort=plan["settings"]["reasoning_effort"], before_request=before_request)
            rec.update(result)
            rec["grading"] = grade(case, rec["final"], env)
            rec["run_status"] = "invalid_schema" if "final_schema" in rec["grading"]["failures"] else "completed"
        except RunError as exc:
            rec.update(recover_checkpoint(root))
            rec.update(run_status=exc.code, error=exc.diagnostics, trace=env.trace)
            stop = exc.code == "api_budget" or exc.diagnostics.get("status_code") in plan["settings"]["stop_on_http_status"]
        except KeyboardInterrupt:
            rec.update(recover_checkpoint(root))
            rec.update(run_status="interrupted", trace=env.trace)
            stop = True
        except Exception as exc:
            rec.update(recover_checkpoint(root))
            rec.update(run_status="execution_error", error=safe_error(exc), trace=env.trace)
            stop = True  # A harness bug must not trigger a billable cascade.
        rec["finished_utc"] = utc()
        records.append(rec)
        (root / "result.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
        append_event(out / "results.jsonl", rec)
        append_event(out / "attempt_events.jsonl", {"event": "attempt_finished", "attempt_id": item["attempt_id"],
                     "run_status": rec["run_status"], "finished_utc": rec["finished_utc"]})
        report = summarize(plan, records)
        (out / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if stop:
            break
        time.sleep(plan["settings"]["between_episodes_seconds"])
    report = summarize(plan, records)
    (out / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    preview = sub.add_parser("preview", help="Show counts; no SDK or key required")
    preview.add_argument("--mode", choices=["pilot", "full"], default="pilot")
    freeze = sub.add_parser("freeze", help="Freeze code, fixtures, prompts, SDK and settings; makes no API calls")
    freeze.add_argument("--model", required=True)
    freeze.add_argument("--mode", choices=["pilot", "full"], default="pilot")
    freeze.add_argument("--max-api-requests", type=int)
    freeze.add_argument("--reasoning-effort")
    freeze.add_argument("--out", required=True)
    run = sub.add_parser("run", help="Execute an already frozen plan")
    run.add_argument("--plan", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--confirm-max-requests", type=int, required=True)
    a = p.parse_args()
    if a.command == "preview":
        plan = build_plan("UNSELECTED-NOT-FROZEN", a.mode)
        print(json.dumps({"mode": a.mode, "cases": plan["case_count"], "episodes": len(plan["schedule"]),
            "repeats": plan["repeats"], "max_api_requests": plan["settings"]["max_api_requests"],
            "live_requests_made": 0, "plan_status": "preview_not_frozen"}, indent=2))
        return
    if a.command == "freeze":
        if sdk_version() == "unavailable":
            p.error("Install the live extra before freezing so the installed SDK version can be recorded.")
        plan = seal(build_plan(a.model, a.mode, a.max_api_requests, a.reasoning_effort))
        out = Path(a.out)
        if out.exists():
            p.error("Plan already exists; choose a new path.")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"Frozen {len(plan['schedule'])} planned episodes; no API requests. SHA-256: {plan['plan_sha256']}")
        return
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    verify_plan(plan)
    if not a.execute or a.confirm_max_requests != plan["settings"]["max_api_requests"]:
        p.error("No requests made. Explicit --execute and a matching --confirm-max-requests are required.")
    if sdk_version() != plan["sdk_version_at_freeze"] or sdk_version() == "unavailable":
        p.error("Installed SDK differs from the frozen plan. Freeze a new plan with the actual installed version.")
    if runtime_versions() != plan.get("runtime_versions_at_freeze"):
        p.error("Python or grading dependency differs from the frozen plan. Freeze a new plan before execution.")
    if not os.environ.get("OPENAI_API_KEY"):
        p.error("API credential is not configured locally; no request was made.")
    if os.environ.get("OPENAI_BASE_URL"):
        p.error("An alternate API base URL is set. This protocol requires the official endpoint; no request was made.")
    from openai import OpenAI
    with OpenAI(max_retries=0, timeout=plan["settings"]["timeout_seconds"]) as client:
        report = execute_plan(plan, client, Path(a.out), run_kind="live_api")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
