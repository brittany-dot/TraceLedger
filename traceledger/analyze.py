"""Summarize every attempted episode, preserving errors and incomplete coverage."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
import random
import statistics
from pathlib import Path


def passed(row: dict) -> bool:
    return row.get("run_status") == "completed" and row.get("grading", {}).get("machine_pass") is True


def quantile(values: list[float], p: float) -> float:
    xs = sorted(values)
    pos = (len(xs) - 1) * p
    lo, hi = int(pos), min(int(pos) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def summarize(plan: dict, rows: list[dict]) -> dict:
    schedule = {s["attempt_id"]: s for s in plan["schedule"]}
    ids = [r["attempt_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate attempt IDs; reconcile evidence rather than double-counting.")
    if any(i not in schedule for i in ids):
        raise ValueError("Result not in the frozen schedule")
    for row in rows:
        if any(row.get(k) != schedule[row['attempt_id']][k] for k in ('case_id','family','split','repeat','condition')):
            raise ValueError("Result metadata disagrees with the frozen schedule")
    kinds = sorted({r.get("run_kind", "unknown") for r in rows})
    if len(kinds) > 1:
        raise ValueError("Do not combine live and mocked results")
    tables = []
    for split in ("development", "reserved_validation", "ALL"):
        for family in ("CTX", "HAND", "REC", "ALL"):
            for condition in ("baseline", "intervention", "ALL"):
                keep = lambda r: (split == "ALL" or r['split'] == split) and (family == "ALL" or r['family'] == family) and (condition == "ALL" or r['condition'] == condition)
                expected, actual = [s for s in schedule.values() if keep(s)], [r for r in rows if keep(r)]
                if not expected:
                    continue
                statuses = Counter(r.get("run_status", "unresolved_attempt") for r in actual)
                complete = statuses.get("completed", 0)
                passes = sum(passed(r) for r in actual)
                tables.append({"split": split, "family": family, "condition": condition,
                    "planned": len(expected), "attempted": len(actual), "not_attempted": len(expected) - len(actual),
                    "schema_valid_completions": complete, "machine_passes": passes, "status_counts": dict(statuses),
                    "all_attempt_success_rate": passes / len(actual) if actual else None,
                    "machine_pass_rate_valid": passes / complete if complete else None,
                    "human_confirmed_pass_rate": None})
    # Include failed attempts as zero. Do not silently invent outcomes for unattempted episodes.
    by_case = defaultdict(list)
    for row in rows:
        by_case[row["case_id"]].append(row)
    comparisons = []
    for split in ("development", "reserved_validation", "ALL"):
        diffs, case_rows = [], []
        for cid in sorted({s['case_id'] for s in schedule.values() if split == "ALL" or s['split'] == split}):
            planned_case = [s for s in schedule.values() if s['case_id'] == cid]
            actual = by_case[cid]
            if len(actual) != len(planned_case):
                continue
            arms = {c: [r for r in actual if r['condition'] == c] for c in ('baseline','intervention')}
            delta = statistics.mean(passed(r) for r in arms['intervention']) - statistics.mean(passed(r) for r in arms['baseline'])
            diffs.append(delta)
            case_rows.append({'case_id':cid,'delta':delta,'attempts_per_condition':len(arms['baseline'])})
        interval = None
        if len(diffs) >= 2:
            rng = random.Random(plan['metrics']['bootstrap_seed'])
            draws = [statistics.mean(rng.choices(diffs, k=len(diffs))) for _ in range(plan['metrics']['bootstrap_replicates'])]
            interval = [quantile(draws, .025), quantile(draws, .975)]
        comparisons.append({'split':split, 'fully_attempted_scenarios':len(diffs),
            'mean_paired_delta':statistics.mean(diffs) if diffs else None,
            'scenario_bootstrap_95_percent_interval':interval, 'scenario_results':case_rows})
    responses = [s for r in rows for s in r.get('responses', [])]
    requests = [s for r in rows for s in r.get('api_requests', [])]
    result = {"run_kind": kinds[0] if kinds else "no_attempts", "planned_episodes":len(schedule),
        "attempted_episodes":len(rows), "not_attempted_episodes":len(schedule)-len(rows),
        "full_schedule_attempted":len(rows)==len(schedule), "api_create_attempts_recorded":len(requests),
        "api_request_errors":sum(r.get('state')=='error' for r in requests),
        "http_status_counts":dict(Counter(str(r['status_code']) for r in requests if 'status_code' in r)),
        "model_identifiers_returned":sorted({r['model'] for r in responses if r.get('model')}),
        "usage": {"input_tokens_reported":sum((r.get('usage') or {}).get('input_tokens',0) for r in responses),
                  "output_tokens_reported":sum((r.get('usage') or {}).get('output_tokens',0) for r in responses),
                  "responses_without_usage":sum(r.get('usage') is None for r in responses),
                  "billing_complete":False},
        "tables":tables,"paired_comparisons":comparisons,
        "interpretation":"Machine grading only; semantic review is pending. Bootstrap resamples scenarios, not repeats. The purposive synthetic set does not estimate product-wide reliability. Missing error-response usage prevents a complete billing total."}
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True)
    a = p.parse_args()
    root = Path(a.run)
    plan = json.loads((root/'plan.json').read_text(encoding='utf-8'))
    rows = [json.loads(s) for s in (root/'results.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()] if (root/'results.jsonl').exists() else []
    known = {r['attempt_id'] for r in rows}
    events = [json.loads(s) for s in (root/'attempt_events.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()] if (root/'attempt_events.jsonl').exists() else []
    for event in events:
        if event.get('event') == 'attempt_started' and event['attempt_id'] not in known:
            from .experiment import recover_checkpoint
            rows.append({**event, **recover_checkpoint(root/event['attempt_id']), 'run_status':'unresolved_attempt'})
            known.add(event['attempt_id'])
    report = summarize(plan, rows)
    (root/'summary_recomputed.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__ == '__main__': main()
