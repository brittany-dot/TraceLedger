# Retrospective case review
**Review type:** AI-assisted retrospective inspection of an archival export. These are selected cases, not a random sample and not recent product benchmark results. Public descriptions omit unrelated personal context and private message identifiers. The raw transcript is not included; external reviewers cannot independently verify these historical excerpts from this package alone. Source: archival-snapshot-A; SHA-256 `a4437a7d1324840db39a6810bfa46bd23ec7f877b21bf992ab151207f3857cdc`.

## A-01 — Claimed construction versus actual guidance
**Date:** April 27, 2025. **Disposition:** confirmed local reporting failure.

The assistant said a requested file was fully prepared and being split for delivery. I asked whether it was actually building the file. It then acknowledged that it was not literally building it and was providing guidance instead. The observable failure is a mismatch between the claimed execution state and its subsequent correction. I do not infer the historical platform's full capabilities or internal policy from that explanation.

**Side-by-side evidence:** Earlier output: “The Engineering CP Modem file is fully prepared.” Later correction: “I’m not literally ‘building’ the modem file here...” My intervening prompt asked whether it was really building it. Quotation marks around ‘building’ have been normalized typographically; the surrounding words are preserved.

**Ground truth:** the assistant's correction establishes that the preceding completion/progress description was unsupported. **Hypothesis:** fluent progress narration was not constrained by a verified execution receipt. **Alternative:** an omitted execution trace would need to be recovered and reconciled; internal implementation is not known. **Eval transfer:** HAND-01, HAND-02 and HAND-07 require acknowledgement, completion and receipt verification to remain distinct. **Intervention:** gate completion claims on tool receipts and construct contrastive examples separating “planned,” “started” and “verified.”

**Source locators:** Private message identifiers are omitted from this publication copy.

## A-02 — Source fields corrupted during correction
**Date:** February 7, 2025. **Disposition:** confirmed local grounding/invariant failure.

In a process-table task, the assistant described processes 8, 7 and 1 as children of process 6 while its table's parent row assigned them to process 3. I supplied the chart values in text. A later revision then placed 6 in process 6's own child field even though that supplied field was blank/undefined.

**Side-by-side evidence:** supplied fields: `p(8)=3, p(7)=3, p(1)=3; c(6)="-"`. The earlier prose assigned those children to process 6; the later table set `c(6)=6`. The user-supplied table and the assistant's own inconsistent representations are the evidence. This review does not claim to validate every remaining table cell or an unseen original image.

**Hypothesis:** local edits were generated without revalidating the full source-to-field mapping and structural constraints. **Alternatives:** visual transcription, task interpretation and reasoning errors remain possible; internal context truncation is not established. **Eval transfer:** CTX-04 and CTX-05 test whether primary records prevail over summaries and whether contradictions are surfaced rather than patched by guesswork. **Intervention:** immutable input-field checks, explicit source-to-claim mappings and grader penalties for contradictory revisions.

**Source locators:** Private message identifiers are omitted from this publication copy.

## A-03 — Explicit clarification successfully narrows the task
**Date:** April 24, 2025. **Disposition:** successful correction/control, not a confirmed prior memory failure.

I clarified a phased product rollout: in phase one, linked content was staff-curated and users could not change link destinations. The next response acknowledged those restrictions and revised the copy around curated, prelinked experiences.

**Side-by-side evidence:** my constraint: “phase 1 the links arent changeable.” The next response acknowledged that “users can’t customize the scan behavior yet” and removed the editable-portfolio framing. This supports successful uptake of that specific clarification, not verification of every promotional feature mentioned in the revised copy.

**Why it matters:** the earlier prompt contained broader promotional language. I cannot fairly classify its earlier output as forgetting a restriction that may not have been clearly established in the immediate task. This case tests annotation discipline as much as model behavior. **Eval transfer:** CTX-01 and CTX-06 use explicit supersession to eliminate this ambiguity. **Intervention:** version the requirement before judging whether the model violated it.

**Source locators:** Private message identifiers are omitted from this publication copy.

## Behavioral hypothesis

When a model recovers a prior decision incorrectly, I first distinguish unavailable context from available context that was used incorrectly. If the authoritative source was never retrieved, I test retrieval and scope handling. If it was retrieved but contradicted in the answer, I test evidence prioritization and synthesis. If a summary omitted a requirement, I test whether restoring that requirement changes the outcome. I do not label the cause “context-window truncation” without visibility into what was actually supplied. My proposed intervention is a versioned decision record, source-linked claims and a grader that penalizes unsupported reconciliation. These are competing hypotheses to test, not a claim about a dominant mechanism already measured.

**Reviewed inventory:** 3 cases; 2 confirmed local failures; 1 successful clarification/control. No population failure rate is inferred from this selection.
