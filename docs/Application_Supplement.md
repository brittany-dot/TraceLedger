# TraceLedger | Agent Evaluation & Behavioral Reliability
**Brittany R. Hollingsworth | October 5, 2026**

I turn observed agent workflow failures into falsifiable hypotheses, explicit evidence requirements, executable evaluations and candidate interventions. My focus is the difference between an answer that sounds complete and a workflow that preserves the correct context, maintains ownership and reports its state honestly.

## THREE EVALUATION FAMILIES

I developed TraceLedger as an AI-assisted, 24-scenario work sample. Context and memory provenance tests stale decisions, conflicting sources and missing evidence. Handoff ownership tests queued versus completed work, responsibility and artifact verification. Partial-failure recovery tests retry limits, preserved findings and truthful reporting after a failed step. The environment simulates worker states and tool failures while verifying actual local artifact writes.

## IMPLEMENTATION AND LOCAL VALIDATION

I implemented a Responses API agent interface and comparison runner; live SDK/service integration remains unverified, and no live model episodes have been attempted. The local suite passed 124 checks, including the original 84 checks and 40 added data and measurement checks. The runner records source, prompt and schema hashes, request-level events, errors and partial-run coverage.

## CANDIDATE TRAINING SIGNAL

I constructed 18 synthetic preference contrasts: 14 final-answer comparisons and four next-decision comparisons, with blinded review forms. The authored control checks accepted all 18 preferred candidates and rejected all 18 rejected candidates.

These validate authored controls only; they are not live model results or independently annotated training data.

## BEHAVIORAL HYPOTHESIS

When an agent recovers a decision incorrectly, I first distinguish evidence that was unavailable from evidence that was retrieved but contradicted. I would test retrieval coverage, source authority and summary completeness separately before attributing the failure to context loss. The candidate intervention makes provenance, ownership and recovery constraints explicit; the grader checks whether behavior satisfies the task contract.

## PREDECLARED COMPARISON

My planned comparison retains 18 development and six reserved-validation scenarios, three repeats and two prompt conditions: 144 task episodes. A separate 12-episode development pilot checks integration first. Before execution, I will freeze the model, SDK, prompts and settings; report all attempts, valid completions, errors and per-family scores; and group repeated outcomes by scenario. API requests and task episodes are counted separately.

## CURRENT SCOPE

Live benchmarking, independent semantic review and public hosting remain pending. I have not performed fine-tuning, reinforcement learning or RLAIF, and I do not claim an intervention benefit. This work sample demonstrates how I convert qualitative workflow friction into explicit evaluation criteria, inspectable implementation and candidate training signals.

Source archive: TraceLedger_v0.2_Public_Source.zip | Public repository: not yet published.

Local evidence: reports/test_results.xml; reports/release_status.json; reports/recheck_2026-10-05.json.
