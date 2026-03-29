---
description: "Inspect a referenced plan and review it for structure, scope, verification quality, repository constraints, and staged commit guidance."
name: "Review Project Plan"
argument-hint: "Provide a plan reference and any specific review concerns or acceptance bar"
agent: "agent"
---

Review Project Plan
===================================

Review an implementation plan that the user references.

Requirements:

- Treat the user-provided plan reference as the primary review target. Inspect the referenced plan first.
- Inspect the current repository state, relevant source, tests, docs, and git status before finalizing the review.
- Review whether the plan is structured with explicit phases and concrete tasks inside each phase.
- Check whether phases are outcome-oriented rather than file-oriented.
- Check whether each phase clearly states dependencies, scope boundaries, risks, verification steps, review
  checkpoints, and likely follow-up work.
- Check whether tasks are concrete enough to execute, verify, and review without guesswork.
- Check whether commit guidance promotes staged, reviewable slices instead of one oversized commit.
- Check whether commit guidance explicitly describes what should be staged for each slice and what should stay out when
  the branch may contain unrelated edits.
- Check whether docs, tests, workflow updates, and user-visible behavior changes are attached to the correct phase or
  immediate next step.
- Check whether verification steps are measurable and realistic for the affected area.
- Call out missing rollback or fallback guidance for high-risk changes when that omission matters.
- Do not describe plan items as implemented. Keep the review focused on plan quality, execution readiness, and reviewability.

Review structure:

1. Plan summary: short statement of the plan's intended goal and current review status.
2. Findings: ordered by severity or impact.
3. Strengths: what is already solid and should be preserved.
4. Open questions: ambiguities or decisions the plan still leaves unresolved.
5. Recommended revisions: concrete changes needed to make the plan execution-ready.
6. Suggested commit guidance adjustments: only when the current plan's slicing is weak, risky, or incomplete.

Finding rules:

- For each finding, explain what is missing, vague, risky, or difficult to review.
- Tie each finding to the affected phase, task, or section when possible.
- Prefer actionable revision guidance over generic criticism.
- If the plan is solid, say that explicitly and note any residual risks or testing gaps rather than inventing issues.
- Keep the review concise but specific enough that the plan author can revise the plan directly from your feedback.

When useful, provide a revised outline for a weak phase or section, but do not rewrite the entire plan unless the user
explicitly asks for that.

User request:

"$ARGUMENTS"
