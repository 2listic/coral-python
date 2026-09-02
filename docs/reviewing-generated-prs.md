# Reviewing an AI-generated PR

Written from two reviews in this repo — [PR #24](../issues/23-refactor-executor/pr-24-review.md) and
[PR #28](../issues/25-add-lists-sets-and-dictionaries-to-the-base-type/review/) — where the code, the
plan, the deviation notes and the tests all arrived together, produced by the same process. That is
the situation this checklist is for. Most of it applies to any review; the parts that are specific to
generated work are marked.

## The one rule that matters most

**Judge the code against the rest of the system, not against its own documents.**

A generated PR arrives with a plan that argues for it, deviation notes that explain it, and docstrings
that defend it. Auditing that prose is easy and mostly worthless: an inconsistency between two
arguments changes nothing for anyone. What changes things is how the code behaves next to the parts it
has to live with — here, the DealiiX editor and the C++ `coral` backend.

The most valuable finding in the PR #28 review came from loading a fixture in the editor, not from
reading anything. The second most valuable came from reading the *other* backend and discovering it
models the same feature a completely different way.

So: check a claim in the documents **only when someone would re-derive a decision from it.** A wrong
count in `CLAUDE.md` qualifies (the next person budgets from it). A premise that turns out to be false
qualifies (it forecloses an option that is actually open). "This paragraph argues X while that one
argues Y" does not.

## Order of work

1. **Run it before reading it.** Instrument the debugger first — a launch config per entry point, and
   a written list of breakpoints with what to inspect at each. In this repo that is
   `.vscode/launch.json` plus a `debug-walkthrough.md` next to the review, because `.vscode/` is
   gitignored and would not survive a clone.
2. **Take the artifact through its real consumer.** Not the test suite, not the CLI — the thing that
   will actually open the file. Both blocking findings in the PR #28 review were invisible to the
   Python suite and obvious in the editor.
3. **Then evaluate the design**, decision by decision: what was chosen, what it costs, what is still
   unverified. Do this *before* the line-by-line audit; it tells you which parts of the audit are
   worth the time.
4. **Then audit implementation against plan**, scripting anything countable.
5. **Then mutate the tests** (below).
6. **Write the findings as you go**, in a document separate from any earlier round the author is
   already working from. A review the author is reading should not move under them.

This ordering is a default, not a checklist to run in full every time. For a small, self-contained PR
— one file's worth of behaviour, one bug — a step can be skipped or reordered on the reviewer's
judgement in the moment: the debugger step is the one most often worth deferring, since a real-consumer
run or a mutation pass frequently exercises the same execution path already. Say what was skipped and
why, the same as [Returning a review unread](#returning-a-review-unread) asks.

## Specific to generated work

- **The plan and the notes are part of the artifact, not evidence about it.** Checkboxes are claims.
  "Verified" is a claim. They were produced by the same process as the code, so they corroborate
  nothing.
- **Prose defending a mechanism is a reason to look at the mechanism.** 177 lines for 15 one-line
  functions means most of the file is justification; the justification is where a wrong assumption
  hides comfortably.
- **Expect coherent incorrectness.** Sequential decisions build an internally consistent design on top
  of the first misunderstanding. Everything agrees with everything, and the disagreement with reality
  is outside the documents.
- **Errors cluster in the essential complexity, and arrive as the idiomatic answer.** The mechanical
  parts are usually right. The judgement calls come out as whatever is most represented in training
  data — which may be the wrong answer for this system.
- **Don't approve code you cannot explain**, and treat "the AI wrote it" as the red flag it is.

## Mutation testing, briefly

Coverage says a line ran, not that a wrong answer would be noticed. Generated tests often assert the
implementation back at itself.

- Pick mutants from the **design decisions**, not mechanically. Each should ask one question: is purity
  pinned? is fail-loud pinned? is the precedence rule pinned?
- Change one line, run the fastest relevant subset, revert. Script it, and assert the tree is clean at
  the end (`git diff --quiet`).
- Reading the result: **fails** = pinned. **passes** = a gap, or an equivalent mutant — check which
  before reporting it. **half the suite fails** = over-coupled tests.
- A survivor is not always a missing test. Sometimes it means nobody ever decided the behaviour, which
  is more useful to say.

## Returning a review unread

Legitimate, and sometimes the right call: if the artifact fails at its own purpose — it does not work
in the consumer it exists for — hand it back with the reproduction and let the author scope the fix.
Doing the scoping yourself means you end up reviewing your own decision.

Say plainly what was *not* reviewed when you do this.

## Writing it down

- **Findings first, evidence second.** Lead each with the defect and the reproduction; keep the
  reasoning short. State what was run to establish it.
- **One summary page.** A long review does not get read. Put the verdict — blocking, worth fixing here,
  follow-up — where it is seen first.
- **Separate what blocks from what does not**, explicitly, and say when something is not this PR's code
  at all.
- **File follow-ups as issues** and keep them out of the review body; a review is not a backlog.
- **Cross-reference only when it earns its place.** A link the reader does not need is a tax.
- **Do not narrate your own corrections.** If a review note turns out to be wrong, fix the note. The
  reader does not need both versions.
- **Tone:** the findings are about the artifact, not the author. "This looks like an oversight from the
  generated suggestion; let's fix it" is the register that works.

## Repo conventions

- A review lives in `issues/<n>-<slug>/review/`, with a `README.md` summary and one file per round.
- Counted claims get recomputed, and the reproduction goes in the review.
- `docs/` and `CLAUDE.md` are checked against the code, not the plan.

## Reading

| resource | for |
| --- | --- |
| [Google's Code Review Developer Guide](https://google.github.io/eng-practices/review/) | the canonical ordering: design first, then complexity, then tests |
| Addy Osmani, *Beyond Vibe Coding* (O'Reilly, 2025) | Ch 5, Ch 8's "Code Review Strategies", Ch 10's "Challenges and Limitations" — the only book aimed squarely at this |
| Fowler, *Refactoring* (2nd ed.) | judging whether a behaviour-preserving change preserved behaviour |
| Feathers, *Working Effectively with Legacy Code* | characterization tests, and telling a real one from a decorative one |
| [Simon Willison on AI-assisted programming](https://simonwillison.net/tags/ai-assisted-programming/) | taking responsibility for generated output |
| METR 2025 RCT | measured a slowdown where participants predicted a speedup — calibration against your own sense of pace |
