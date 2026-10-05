# Candidate preference data: a thin, inspectable training-signal slice
**Brittany R. Hollingsworth | TraceLedger v0.2 | October 4, 2026**

## What I constructed

I expanded the original six status-flip examples into 18 synthetic contrastive examples: six for context
provenance, six for handoff ownership/completion, and six for partial-failure recovery. Fourteen compare
final answers; four compare the next decision after a partial tool trace. Their purpose is to make the
behavioral distinction explicit, not to represent feedback I have already collected from users or models.

Each row includes the original task, the shared instruction and output contract, the visible tool-trace
prefix, chosen and rejected candidates, an explicit failure label, a rationale, and label/review provenance.
Examples are rule-authored with AI assistance. `human_review=pending`, `model_generated_trace=false`,
and `training_status=not_used_for_training` prevent the artifact from being mistaken for measured preferences.

## Example distinction

A read has timed out. When the task allows one retry, the preferred next decision is the permitted read.
When the task forbids retries, the preferred decision is an honest partial result without a guessed value.
The rejected alternative repeats the read despite the constraint. These examples are intentionally not
collapsed into a generic rule to always retry or always refuse. Ownership examples likewise distinguish a
queued acknowledgement from a verified deliverable, and a rejected handoff from a transferred obligation.

## Construction and measured controls

All 18 examples derive from the **development** split; none of the six reserved-validation scenarios appears
in `data/preference_pairs.jsonl`. The input contains only the observed prefix, not the eventual successful
tool result. Final-answer candidates are checked against the existing environment and machine grader.
Next-action controls compare the proposed next action with the authored protocol step; this is a narrow
rule-based control, not a general semantic action evaluator.

The local control pass accepted 18/18 chosen candidates and rejected 18/18 rejected candidates. These are
construction checks: the same specifications generated the candidates and their labels. They do not measure
reward-model accuracy, independent label quality, agent behavior, or learning. These checks are represented
by 18 parameterized cases within the 124-test suite; they are not an additional 36 model runs.

## Independent annotation protocol

The companion review file randomizes A/B order and omits the intended label, case ID and author rationale.
Reviewers receive the input contract, observed evidence, both candidates, and blank fields for selection,
reason, confidence and identity. The mapping is in a separate key file. Give only the blinded file to a reviewer;
the repository is public-ready, not a mechanism for enforcing reviewer blinding after publication.

Reviewers should distinguish a factual or instruction-following error from mere writing preference. They
should mark an example ambiguous rather than manufacture a preference when both candidates are acceptable.
For final answers, apply evidence fidelity, state truthfulness, constraint preservation and recovery usefulness.
For next actions, judge whether the choice is authorized and justified by the visible prefix. Preserve both
independent labels and any adjudication instead of silently replacing disagreements. No reviewer agreement
or human annotation is reported in this release.

## Proposed use in a preference mixture

After independent review, I would retain accepted examples as a small, explicitly labeled candidate slice,
balanced across the three failure families. I would keep synthetic origins distinguishable from future
model-generated traces and human judgments. Hard negatives should remain minimally different but plausible:
wrong provenance, premature completion, discarded partial findings, or retries that violate the task.

Before training, I would deduplicate at the scenario/template level, create a new unexposed validation set,
and compare a baseline mixture against one augmented with this slice while holding training settings fixed.
I would report targeted improvements, regressions on ordinary tasks, label disagreement, and null results.
Any mixture proportion, objective and model would be predeclared for that later experiment; none is presented
as empirically optimal here. No fine-tune, RLHF, RLAIF, DPO or learned reward-model experiment has been run.

## Leakage and representativeness

The v0.1 archived preference file contained a HAND-07 example, which is a reserved-validation task.
It is not used by the new slice. However, the current validation scenarios are visible and authored alongside
the benchmark; neither visibility nor that historical overlap should be hidden behind the phrase "clean holdout."
A future trained model needs fresh validation scenarios not used for demonstrations, annotation or tuning.

This small slice is an annotation artifact, not a representative data distribution. It is not suitable for claiming
production-scale post-training experience or a training benefit without executing the proposed comparison.
