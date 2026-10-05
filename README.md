# TraceLedger

[![Offline tests](https://github.com/brittany-dot/TraceLedger/actions/workflows/tests.yml/badge.svg)](https://github.com/brittany-dot/TraceLedger/actions/workflows/tests.yml)

**Public repository:** https://github.com/brittany-dot/TraceLedger
### Context provenance, handoff ownership, and partial-failure recovery
**Brittany R. Hollingsworth | AI-assisted independent work sample | v0.2 | Publication copy revised October 5, 2026**

```bash
python -m pytest -q
```

Run that command from the repository root after installing the offline dependencies:
`python -m pip install -e ".[dev]"`. It makes **no API calls** and does not require the OpenAI SDK.
The measured result for this release is **124 passed**. The test XML is in `reports/test_results.xml`.
The earlier 84 tests are included in that total, not added to it. A repeat local check on October 5 also passed 124/124; see `reports/recheck_2026-10-05.json` and its XML. This repeat is not 124 additional unique tests.

I study the gap between a plausible answer and a workflow that actually preserves the right context,
uses tools correctly, and reports its state honestly. TraceLedger translates that friction into
three failure taxonomies, a 24-scenario synthetic benchmark, executable grading rules, and an
OpenAI Responses API agent interface. Live SDK/service integration and model measurements remain unverified.

## What is measured—and what is not

| Item | Status in this release |
|---|---|
| Offline engineering suite | **124/124 passed**, including original 84 checks and 40 new checks |
| Candidate preference data | **18 synthetic contrasts**: 6 per family; 14 final-answer pairs and 4 next-decision pairs |
| Preference control validation | 18 chosen candidates accepted; 18 rejected candidates rejected by authored rules |
| Live API model episodes | **0 attempted, 0 completed** in this environment |
| Installed OpenAI SDK/service integration | Unverified; SDK installation did not succeed in this environment |
| Controlled comparison | Runner implemented and locally tested; actual model/SDK/settings freeze and execution pending |
| Independent semantic/preference review | Pending; blinded review forms included |
| Fine-tuning, RL, RLAIF or reward-model training | None performed |
| Public GitHub repository | **Published:** https://github.com/brittany-dot/TraceLedger |

These tests validate authored controls and runner behavior. They are **not** model performance,
independent preference agreement, or evidence that an intervention improves a model.

## Reproduce the offline checks

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m traceledger.selftest
.\.venv\Scripts\python -m traceledger.preferences
.\.venv\Scripts\python -m traceledger.experiment preview --mode pilot
```

For Linux/macOS, use `python3` and `.venv/bin/python`. The self-test repeats the original 24 reference
and 48 mutation controls; it is not another 72 unique model trials. Preference generation repeats
checks included in the pytest suite. `reports/environment.json` records the actual local versions.
The optional `live` dependency separates SDK installation from offline reproducibility.
`requirements-offline.txt` records the installed offline dependency versions; its Windows-only dependency was not exercised in this Linux run.

## The three evaluation families

**CTX — context and memory provenance.** Eight scenarios cover superseded approvals, missing decisions,
wrong-project collisions, primary-vs-summary conflict, revoked decisions and access denial.

**HAND — handoff ownership and completion.** Eight scenarios distinguish acknowledgement, queueing,
unknown execution, verified completion, stale artifacts and uncertain writes.

**REC — instruction preservation under partial failure.** Eight scenarios test retry limits, denied
sources, missing optional evidence, schema faults and truthful reporting after a failed write.

The tools simulate worker states and read failures, and perform actual local artifact writes and
hash verification. Projects, Space and Work describe the workflow problems being modeled; this
harness does not instrument those products or run a live distributed multi-agent service.

## Run the live comparison

First install `python -m pip install -e ".[dev,live]"` on a network-enabled machine. Use the secure
OpenAI Platform API-key setup flow when a credential is needed, and keep the credential local.
Do not paste a key into a transcript, source file, or repository. The runner expects it in the local
`OPENAI_API_KEY` environment. No credential is included in this release.

Select an accessible model supporting Responses, function calls and structured output. Prefer an exact
snapshot when available. Requested and returned identifiers are retained verbatim; an alias is not
misrepresented as a resolved snapshot. No model or dollar budget has been selected for this release.

### A small first pilot: 12 episodes

The fixed pilot uses CTX-01, CTX-05, HAND-01, HAND-02, REC-01 and REC-05: two development scenarios
per family, one repeat, both conditions. It does not consume the reserved-validation split.

```powershell
.\.venv\Scripts\python -m traceledger.experiment freeze --mode pilot --model "EXACT_MODEL_ID_TO_TEST" --out runs/pilot-plan.json
.\.venv\Scripts\python -m traceledger.experiment run --plan runs/pilot-plan.json --out runs/pilot-001 --execute --confirm-max-requests 144
.\.venv\Scripts\python -m traceledger.analyze --run runs/pilot-001
```

`freeze` makes no API calls. It requires an installed SDK so that its version is recorded.
The first `run` command is billable and requires explicit authorization. **Twelve episodes can
require up to 144 API create calls at the default 12-turn cap. A request cap is not a dollar cap.**
A smaller cap may be frozen with `--max-api-requests N`; use that same number when authorizing
execution. Truncated coverage remains visible as not attempted; do not report it as a complete pilot.

### The predeclared full design: 144 episodes

```powershell
.\.venv\Scripts\python -m traceledger.experiment freeze --mode full --model "EXACT_MODEL_ID_TO_TEST" --out runs/full-plan.json
.\.venv\Scripts\python -m traceledger.experiment run --plan runs/full-plan.json --out runs/full-001 --execute --confirm-max-requests 1728
```

There are **18 development + 6 reserved-validation scenarios**, three repeats per scenario,
and two conditions: `(18 + 6) x 3 x 2 = 144 episodes`. At most 12 model turns per episode permits
up to 1,728 API create attempts. Actual use can be smaller. Establish a monetary budget before
executing; these upper bounds do not estimate token charges.

Both conditions use identical fixtures, tools, output schema and graders. The intervention adds
explicit provenance, ownership and recovery instructions. `freeze` hashes source code, cases,
prompts and schemas and records the installed SDK. An unchanged plan and matching runtime are
required to execute. This release contains the protocol and tested freeze mechanism, not a frozen
live model selection or a completed comparison.

Blocks are paired by scenario/repeat, with randomized condition order. Development runs precede
reserved validation. No model determinism seed is claimed. SDK retries are disabled so network
retries do not become hidden calls. Authentication, access, missing-model and rate-limit errors stop
the remaining queue; they remain in the attempted denominator, while later episodes remain not attempted.

## Evidence retained per run

The runner writes a plan and runtime manifest, append-only episode start/finish events, per-call
start/response/error events, local checkpoints, raw final text, structured results, tool receipts
and summary tables. It records request IDs when supplied, HTTP/error codes, available rate-limit
headers, requested/returned model identifiers, token usage when returned, and partial-run coverage.
Raw exceptions and credentials are not serialized. On hard interruption, the analyzer flags started
but unfinished episodes as unresolved rather than silently retrying them.

Primary metric: machine passes / **all attempted episodes**. Secondary metric: passes /
schema-valid completions. Format, incomplete-response, transport/API, budget and harness errors
remain separate. Per-family/per-condition/per-split counts precede rates. Paired differences are
computed only for fully attempted scenarios; the bootstrap resamples scenarios, not repetitions.
Independent semantic pass rates remain null until actual review. Provider-side execution and costs
may be unknown for lost responses; returned usage is not a complete billing statement.

## Candidate training-signal slice

`data/preference_pairs.jsonl` contains **18 rule-authored contrasts from development scenarios only**.
They are not mined from live failures and have not trained a model. Each example retains the input
contract, visible tool-trace prefix, chosen/rejected candidate, failure label, rationale, label provenance
and pending human-review status. Four examples contrast a next tool action with premature completion
or a forbidden retry. Their inputs do not include future tool results.

`review_materials/blinded_preferences.jsonl` hides the intended labels and randomizes A/B order.
Give that file—not `review_key.json`—to an independent reviewer. Human feedback has not yet been
collected. `docs/TRAINING_SIGNAL.md` explains proposed use, label quality and leakage boundaries.

## Corpus scope

The carried-forward audit of one private archival snapshot reports **1,656 conversations, 43,893
unique message IDs, 180 user-active UTC days and 137,911,419 JSON bytes**. The records span
November 7, 2024–May 5, 2025, include branches and non-user roles, and have documented missing
timestamps and duplicate IDs. These are archive inventory counts, not 1,656 formal evaluations.
The raw export is excluded. The separately reported approximately 1.9 GB weekly export-size change
is not verified by this audit. The v0.1 audit JSON is retained unchanged.

## Limitations worth testing, not hiding

The tasks are synthetic and many explicitly describe the desired behavior. The baseline may therefore
score highly. A null or negative intervention effect is a valid finding, not a reason to omit cases.
The fixed path checks do not recognize every semantically equivalent plan. The machine grader does
not fully grade explanation quality. Reference traces, contrasts and graders share authorship, so
agreement is not independent validation. The six validation scenarios are visible, same-author
reserved scenarios—not a secret or independently sourced holdout. The old v0.1 preference examples
included HAND-07; they are archived, excluded from the new training-signal slice and cannot justify
claiming a pristine holdout for a future trained model.

A prompt-level result would describe this prompt-plus-harness system, not weight updates or shipped
product improvement. The ledger is single-process, not a distributed exactly-once implementation.
Automatic resumption after a crashed write is not implemented.

## Package map

- `data/cases.jsonl`, `traceledger/grading.py`: unchanged tasks and machine graders.
- `traceledger/experiment.py`, `traceledger/analyze.py`: frozen paired execution and honest denominators.
- `traceledger/agent.py`, `environment.py`, `schemas.py`: bounded agent loop and tool contracts.
- `data/preference_pairs.jsonl`, `docs/TRAINING_SIGNAL.md`: candidate preference data and methodology.
- `reports/`: measured offline results, carried-forward audit, integrity checks and explicit release status.
- `docs/Application_Supplement.pdf`: current one-page work-sample note.
- `docs/RESUME_INSERTS.md`: first-person, status-qualified application wording.
- `docs/archive/`, `reports/v0.1/`: historical synthetic data and local results, not current release claims.
- `reports/recheck_2026-10-05.json`: repeat local validation and publication-copy change record.

## Publication

This repository is publicly available at **https://github.com/brittany-dot/TraceLedger**. No live-run command is needed to publish or reproduce the offline suite. The source archive is `TraceLedger_v0.2_Public_Source.zip`.


Public repository publication is complete. Hosted CI status is reported by the GitHub Actions badge above.
The package has a `.github/workflows/tests.yml` offline workflow but no green GitHub badge is claimed.
See `docs/PUBLICATION.md`. The public repository URL may be used in application materials: https://github.com/brittany-dot/TraceLedger.

## Implementation references

Official sources checked October 4, 2026:

- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Reasoning state across tool calls](https://developers.openai.com/api/docs/guides/reasoning)
- [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- [OpenAI Python SDK: request IDs and retries](https://github.com/openai/openai-python#request-ids)

This project uses local Python graders, not a hosted Evals or fine-tuning integration. Current service
availability and supported model settings must be checked during the live smoke test. Code, data
construction and documentation were produced with AI assistance; independent review is not implied.



