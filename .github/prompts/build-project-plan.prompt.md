---
description: "Inspect the current state and produce a structured execution plan with phases, tasks, follow-up work, verification checkpoints, and staggered commit guidance."
name: "Build Project Plan"
argument-hint: "Describe the feature, refactor, migration, investigation, or documentation effort to plan"
agent: "agent"
---

# Build Project Plan

Build or update an execution plan for the requested work.

Requirements:

- Inspect the current repository state, relevant source, tests, docs, and git status before proposing the plan.
- Structure the plan with explicit phases and tasks inside each phase.
- Keep phases outcome-oriented rather than file-oriented.
- For each phase, call out dependencies, scope boundaries, verification steps, likely follow-up work, and risks when
  they matter.
- Include commit guidance after each major task or phase using a staggered approach.
- Commits should be reviewable and coherent: not so small that they create noisy history, and not so large that
  debugging or blame becomes difficult later.
- Commit guidance should assume the branch may contain unrelated edits. Explicitly describe what should be staged for
  each slice and what should stay out of that commit.
- Do not collapse all planned work into one commit unless the requested change is genuinely small.
- When a phase includes mixed concerns, call out whether `git add -p`, a follow-up cleanup commit, or a separate docs
  commit is appropriate.
- Preserve repository constraints when the work touches persisted identities, change detection, configuration loading,
  database operations, security-sensitive code, or integration workers.
- When user-visible behavior changes, include the corresponding test and documentation work in the same phase or as
  the immediate next step.
- Prefer measurable verification and acceptance criteria where practical, such as command output, schema expectations,
  passing checks, or operator-visible behavior.
- Include rollback or fallback notes for high-risk changes when realistic. If rollback would be manual or operational,
  say that clearly.
- Include a short review checkpoint after major phases when the plan should be re-evaluated based on what was learned.
- When the work is substantial enough to deserve an implementation plan, make the output suitable for a committed plan
  file under `.github/plans/`.
- Do not describe future work as already implemented.

Plan structure:

1. Goal: short statement of the desired end state.
2. Constraints: repository rules, safety constraints, and known boundaries that matter.
3. Phase list: each phase should include:
   - phase objective,
   - intended outcome,
   - dependencies,
   - in-scope items,
   - out-of-scope items when useful,
   - risks or blockers,
   - tasks,
   - expected outputs or artifacts,
   - review checkpoint,
   - verification and acceptance criteria,
   - commit checkpoint guidance,
   - out-of-commit scope when relevant,
   - likely follow-up items required before the next phase.
4. Risks and open questions.
5. Suggested commit series: recommended commit groupings and messages.

Commit guidance rules:

- Prefer one commit per completed major task or tightly related task bundle.
- Use `git add -p` when a file mixes multiple concerns and the plan should land in separate commits.
- Call out when a phase is too large and should be split before implementation starts.
- Mention when follow-up cleanup should be its own later commit instead of being bundled into the main behavior change.
- Mention when docs, tests, or workflow files should land in the same commit as the behavior change versus a separate
  follow-up slice.
- If the working tree is already dirty, remind the user to stage only the files for the current slice.

User request:

"$ARGUMENTS"
