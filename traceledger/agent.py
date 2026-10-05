"""Responses API loop with strict tools, attribution and durable attempt telemetry.

Only the public task, instructions, schemas and observed tool results reach the model.
Checkpoint and event logs can contain task data; keep them private until reviewed.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any
from .environment import Environment
from .schemas import TOOLS, FINAL_SCHEMA, BASELINE, INTERVENTION


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sdk_version() -> str:
    try:
        return importlib.metadata.version("openai")
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def append_event(path: Path, event: dict) -> None:
    """Append and flush one event so a later error does not erase earlier evidence."""
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def safe_error(exc: Exception) -> dict:
    """Capture structured diagnostics, never a request body, credential or raw error."""
    data = {"error_type": type(exc).__name__}
    for key in ("status_code", "request_id"):
        value = getattr(exc, key, None)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            data[key] = str(value)[:160] if isinstance(value, str) else value
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            code = error.get("code")
            if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", code):
                data["api_error_code"] = code
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {})
    for key in ("retry-after", "x-ratelimit-remaining-requests", "x-ratelimit-remaining-tokens"):
        value = headers.get(key) if headers else None
        if value is not None:
            data.setdefault("rate_limit_headers", {})[key] = str(value)[:100]
    return data


class RunError(RuntimeError):
    def __init__(self, code: str, message: str = "", diagnostics: dict | None = None):
        super().__init__(message or code)
        self.code = code
        self.diagnostics = diagnostics or {}


def run_agent(client: Any, model: str, prompt: str, env: Environment,
              condition: str = "intervention", max_turns: int = 12,
              max_tool_calls: int = 24, max_output_tokens: int = 2500,
              reasoning_effort: str | None = None,
              before_request: Callable[[], None] | None = None) -> dict:
    if condition not in ("baseline", "intervention"):
        raise ValueError("condition must be baseline or intervention")
    if min(max_turns, max_tool_calls, max_output_tokens) < 1:
        raise ValueError("Run limits must be positive")
    instructions = INTERVENTION if condition == "intervention" else BASELINE
    history: list = [{"role": "user", "content": prompt}]
    calls, responses, requests = 0, [], []
    started = time.monotonic()

    def checkpoint() -> None:
        temporary = env.root / ".checkpoint.tmp"
        temporary.write_text(json.dumps({"responses": responses, "api_requests": requests,
            "trace": env.trace, "input_items": history}, indent=2), encoding="utf-8")
        temporary.replace(env.root / "checkpoint.json")

    for turn in range(max_turns):
        if before_request is not None:
            before_request()
        request = {"turn": turn, "started_utc": utc(), "state": "started",
                   "input_sha256": hashlib.sha256(json.dumps(history, sort_keys=True).encode()).hexdigest()}
        requests.append(request)
        append_event(env.root / "api_events.jsonl", {"event": "api_request_started", **request})
        checkpoint()
        options = dict(model=model, instructions=instructions, input=history, tools=TOOLS,
                       parallel_tool_calls=False, store=False,
                       text={"format": {"type": "json_schema", "name": "workflow_outcome",
                                        "schema": FINAL_SCHEMA, "strict": True}},
                       max_output_tokens=max_output_tokens)
        if reasoning_effort is not None:
            options["reasoning"] = {"effort": reasoning_effort}
        try:
            response = client.responses.create(**options)
        except Exception as exc:
            error = safe_error(exc)
            request.update(state="error", finished_utc=utc(), **error)
            append_event(env.root / "api_events.jsonl", {"event": "api_request_error", **request})
            checkpoint()
            raise RunError("api_error", "API request failed; see structured diagnostics.", error) from exc
        request.update(state="received", finished_utc=utc(), request_id=getattr(response, "_request_id", None))
        output = [item.model_dump(exclude_none=True) for item in response.output]
        # Preserve EVERY response item, including opaque reasoning state.
        history.extend(output)
        meta = {"id": response.id, "request_id": getattr(response, "_request_id", None),
                "model": getattr(response, "model", None), "status": getattr(response, "status", None),
                "usage": response.usage.model_dump() if getattr(response, "usage", None) else None}
        details = getattr(response, "incomplete_details", None)
        if details is not None:
            meta["incomplete_details"] = details.model_dump() if hasattr(details, "model_dump") else str(details)[:100]
        responses.append(meta)
        append_event(env.root / "api_events.jsonl", {"event": "api_response_received", "turn": turn, **meta})
        checkpoint()
        if getattr(response, "status", "completed") != "completed":
            raise RunError("incomplete_response", "Response did not complete; retain usage and output for review.")
        function_calls = [item for item in output if item.get("type") == "function_call"]
        if not function_calls:
            # Preserve raw final text locally even when JSON parsing fails.
            raw = response.output_text or ""
            (env.root / "final_text.txt").write_text(raw, encoding="utf-8")
            try:
                final = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                raise RunError("invalid_final_json", "Final text was not JSON; possible refusal or format failure.") from exc
            return {"final": final, "responses": responses, "api_requests": requests, "trace": env.trace,
                    "elapsed_seconds": round(time.monotonic() - started, 3), "condition": condition,
                    "requested_model": model, "sdk_version": sdk_version()}
        for fc in function_calls:
            calls += 1
            if calls > max_tool_calls:
                raise RunError("tool_budget", "Tool-call limit reached before executing the excess call.")
            try:
                args = json.loads(fc["arguments"])
            except (json.JSONDecodeError, TypeError):
                args = None
            result = env.call(fc["name"], args)
            history.append({"type": "function_call_output", "call_id": fc["call_id"], "output": json.dumps(result)})
            checkpoint()
    raise RunError("model_budget", "Model-turn limit reached; completion is not claimed.")


def load_cases(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="HAND-07")
    parser.add_argument("--cases", default="data/cases.jsonl")
    parser.add_argument("--model", required=True)
    parser.add_argument("--condition", choices=["baseline", "intervention"], default="intervention")
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true", help="Authorize this live, billable episode (at most 12 requests)")
    args = parser.parse_args()
    if not args.execute:
        parser.error("No requests made. Add --execute to authorize a live episode; prefer the frozen experiment runner.")
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("API credential is not configured locally. No API request was made.")
    if Path(args.out).exists():
        parser.error("Output directory exists; use a fresh path to preserve evidence.")
    matches = [c for c in load_cases(args.cases) if c["id"] == args.case]
    if not matches:
        parser.error("Unknown case id")
    try:
        from openai import OpenAI
    except ImportError:
        parser.error("Install the live extra: python -m pip install -e '.[live]'")
    from .grading import grade
    case = matches[0]
    env = Environment(case["environment"], args.out)
    with OpenAI(max_retries=0, timeout=45.0) as client:
        try:
            record = run_agent(client, args.model, case["prompt"], env, args.condition)
            record.update(grading=grade(case, record["final"], env), case_id=case["id"])
            (env.root / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            print(json.dumps(record["final"], indent=2))
            print("Machine checks:", record["grading"])
        except Exception as exc:
            record = {"case_id": case["id"], "run_status": getattr(exc, "code", "execution_error"),
                      "error": safe_error(exc), "trace": env.trace}
            (env.root / "error.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            raise SystemExit("Run stopped. See local evidence; completion is not claimed.")

if __name__ == "__main__":
    main()
