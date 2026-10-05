# Live measurement protocol and decision log
**Protocol implementation v0.2; live selection and execution pending**

## Fixed comparison

I retain the original 24 scenarios, their 18-development/6-reserved-validation assignment, both prompt
conditions, tool definitions, final schema, environment fixtures and machine grader. v0.2 adds measurement
infrastructure; it does not change these benchmark inputs. Integrity hashes are in `reports/integrity_checks.json`.

The full design is 24 scenarios x 3 repeats x 2 conditions = 144 planned episodes. The pilot is 6 development
scenarios x 1 repeat x 2 conditions = 12 episodes. Pilot IDs: CTX-01, CTX-05, HAND-01, HAND-02, REC-01, REC-05.
Pilot results must not be pooled with the registered full comparison, counted as extra independent scenarios,
or described as the full study. Any changes informed by the pilot require a new full-study freeze.

## Inputs still requiring a real choice

An accessible model/snapshot, installed SDK version, reasoning setting, execution authorization and monetary
budget remain unselected. No live model was called during this revision. `preview` is not a frozen experiment.
`freeze` records exact prompts, fixtures, schemas, runtime code and settings without making an API call.
A source change or SDK/runtime mismatch invalidates execution under that plan.

The default ceilings are 12 model turns, 24 tool calls and 2,500 output tokens per response. A reasoning model
could use the token cap differently and return an incomplete response; the outcome must be retained, not
silently raised and relabeled. A full-study cap of 1,728 API create calls and pilot cap of 144 are worst-case
request bounds, **not prices**. Any smaller cap is documented with the resulting incomplete coverage.

## Ordering and accounting

Each scenario/repeat is a paired block; arm order is randomized with an order seed. Development blocks
precede validation. The order seed is not a model-sampling determinism guarantee. SDK retries are zero.
Task-level retries are governed by the fixture's instructions and recorded in the tool trace.

Before each episode and API request, append a start event. Preserve response metadata, IDs, request errors,
available rate-limit headers, incomplete details and usage. Capture final text even when JSON parsing fails.
Distinguish: completed/schema-valid, invalid schema, invalid JSON, incomplete response, API/transport error,
model/tool/global budget exhaustion, harness error, interruption, and unresolved starts after a hard crash.
Do not infer provider-side nonexecution from a timeout. There is no automatic in-place resumption.

Stop after HTTP 401, 403, 404 or 429; record that attempt and mark later scheduled episodes unattempted.
Do not spend the remaining budget on repeated authentication/model/rate-limit failures. Any later reattempt
belongs to a separately identified execution and must remain distinguishable in reporting.

## Grading and uncertainty

Primary descriptive score: machine passes / all attempted episodes. Secondary: machine passes /
schema-valid completions. Report counts by split, family and condition; keep each error category and
unattempted count visible. Human-confirmed pass is null until actual independent semantic review.

For the paired comparison, average repeats within each scenario and subtract baseline from intervention.
Only fully attempted scenario pairs enter this comparison; disclose excluded/incomplete coverage alongside
it and do not portray a partial comparison as a completed registered result. A 2,000-resample bootstrap
resamples scenarios. Its interval describes this purposive synthetic scenario distribution, not all products
or users. With few validation scenarios, uncertainty may be large or uninformative.

No cherry-picking: retain successful runs, failures, API errors, ceiling effects and negative intervention deltas.
The prompts already state many desired behaviors, so a small or zero intervention gain is plausible.
Use observed failure traces to propose a future benchmark revision, not to retroactively alter this one.

## Release gates

1. Run offline checks and inspect package contents.
2. Install the actual SDK and select the exact model/settings.
3. Freeze and execute a budget-approved pilot; inspect successful and failed traces.
4. Freeze the full comparison before looking at its reserved-validation outcomes.
5. Review all outcomes, document limitations, and publish only scrubbed, reproducible evidence.

These are gates and proposed actions, not completed experiment results. A prompt effect is not a model-weight
update or a demonstration of production post-training.
