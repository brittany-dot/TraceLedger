"""Small deterministic tool environment; external workers and failures are simulated.

Artifacts really are written and hashed locally. A ledger is atomically saved after
writes; this is a single-process demo, not a distributed exactly-once guarantee.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from jsonschema import ValidationError, validate
from .schemas import SPECS


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class Environment:
    def __init__(self, spec: dict, directory: str | Path):
        self.spec = copy.deepcopy(spec)
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.trace: list[dict] = []
        self.calls: dict[str, int] = {}
        self.observed: dict[str, dict] = {}
        self.receipts: dict[str, dict] = {}
        self.key_index: dict[str, str] = {}
        self.new_writes = 0
        self.started_jobs = 0
        for artifact in self.spec.get("artifacts", []):
            receipt = self._commit(artifact["name"], artifact["content"], artifact.get("source_ids", []),
                                   artifact.get("key", artifact["id"]), artifact["id"], artifact.get("facts", {}))
            self.receipts[receipt["artifact_id"]] = receipt
        self.new_writes = 0
        self._save()

    def _save(self) -> None:
        temp = self.root / ".ledger.tmp"
        temp.write_text(json.dumps({"receipts": self.receipts, "keys": self.key_index}, indent=2), encoding="utf-8")
        temp.replace(self.root / "ledger.json")

    def _commit(self, name: str, content: str, source_ids: list[str], key: str,
                artifact_id: str | None = None, facts: dict | None = None) -> dict:
        artifact_id = artifact_id or "a-" + digest(key.encode())[:12]
        raw = content.encode("utf-8")
        path = self.root / (artifact_id + ".md")
        path.write_bytes(raw)
        receipt = {"status": "ok", "artifact_id": artifact_id, "source_id": "artifact:" + artifact_id,
                   "name": name, "sha256": digest(raw), "source_ids": source_ids,
                   "facts": facts or {}, "verified": True, "idempotency_key": key}
        self.receipts[artifact_id] = receipt
        self.key_index[key] = artifact_id
        self.new_writes += 1
        self._save()
        return copy.deepcopy(receipt)

    def call(self, name: str, arguments: dict[str, Any]) -> dict:
        if name not in SPECS:
            result = {"status": "error", "code": "unknown_tool"}
        else:
            try:
                validate(arguments, SPECS[name][1])
                result = self._dispatch(name, arguments)
            except ValidationError:
                result = {"status": "error", "code": "schema_error", "detail": "Arguments do not match the tool schema."}
        self.trace.append({"index": len(self.trace), "tool": name,
                           "arguments": copy.deepcopy(arguments), "result": copy.deepcopy(result)})
        if result.get("status") == "ok" and result.get("source_id"):
            self.observed[result["source_id"]] = copy.deepcopy(result)
        return result

    def _dispatch(self, name: str, args: dict) -> dict:
        if name == "list_sources":
            return {"status": "ok", "sources": [
                {"source_id": sid, **{k: s[k] for k in ("title", "scope", "authority", "revision", "supersedes", "truncated") if k in s}}
                for sid, s in self.spec.get("sources", {}).items()]}
        if name == "read_source":
            sid = args["source_id"]
            source = self.spec.get("sources", {}).get(sid)
            if source is None:
                return {"status": "error", "code": "not_found", "source_id": sid}
            self.calls[sid] = self.calls.get(sid, 0) + 1
            errors = source.get("errors", [])
            index = self.calls[sid] - 1
            code = errors[index] if index < len(errors) else source.get("persistent_error")
            if code:
                return {"status": "error", "code": code, "source_id": sid, "retryable": code in ("timeout", "schema_error")}
            return {"status": "ok", "source_id": sid,
                    **{k: copy.deepcopy(v) for k, v in source.items() if k not in ("errors", "persistent_error")}}
        if name in ("get_job", "start_job"):
            jid = args["job_id"]
            job = self.spec.get("jobs", {}).get(jid)
            if name == "start_job":
                self.started_jobs += 1
            if job is None:
                return {"status": "error", "code": "not_found", "source_id": "job:" + jid}
            return {"status": "ok", "source_id": "job:" + jid, **copy.deepcopy(job)}
        if name == "inspect_artifact":
            return self._inspect(args["artifact_id"])
        if name == "lookup_write":
            aid = self.key_index.get(args["idempotency_key"])
            if not aid:
                return {"status": "error", "code": "not_found"}
            return self._inspect(aid)
        if name == "write_artifact":
            key, content = args["idempotency_key"], args["content"]
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", args["name"]) or not args["name"].endswith(".md"):
                return {"status": "error", "code": "invalid_name"}
            if len(content.encode("utf-8")) > 100000 or not key or len(key) > 200:
                return {"status": "error", "code": "invalid_size_or_key"}
            if key in self.key_index:
                old = self.receipts[self.key_index[key]]
                if (old["sha256"] != digest(content.encode()) or old["source_ids"] != args["source_ids"]
                        or old["name"] != args["name"]):
                    return {"status": "error", "code": "idempotency_conflict", "artifact_id": old["artifact_id"]}
                return self._inspect(old["artifact_id"])
            if not args["source_ids"] or any(sid not in self.observed for sid in args["source_ids"]):
                return {"status": "error", "code": "unread_source"}
            if self.spec.get("write_error") == "permission_denied":
                return {"status": "error", "code": "permission_denied"}
            receipt = self._commit(args["name"], content, args["source_ids"], key)
            if self.spec.get("write_error") == "commit_then_timeout":
                return {"status": "error", "code": "timeout", "commit_state": "unknown", "idempotency_key": key}
            return receipt
        raise AssertionError("Unhandled registered tool")

    def _inspect(self, aid: str) -> dict:
        receipt = self.receipts.get(aid)
        if not receipt:
            return {"status": "error", "code": "not_found", "artifact_id": aid}
        path = self.root / (aid + ".md")
        if not path.exists() or digest(path.read_bytes()) != receipt["sha256"]:
            return {"status": "error", "code": "integrity_error", "artifact_id": aid}
        return {**copy.deepcopy(receipt), "content": path.read_text(encoding="utf-8"), "verified": True}
