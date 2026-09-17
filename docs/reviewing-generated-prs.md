# Reviewing an AI-generated PR

Written from the reviews in this repo — [PR #24](../issues/23-refactor-executor/pr-24-review.md),
[PR #28](../issues/25-add-lists-sets-and-dictionaries-to-the-base-type/review/) and
[PR #29](../issues/27-refactor-test/review/) — where the code, the plan, the deviation notes and the
tests all arrived together, produced by the same process. Most of this applies to any review; the
section on generated work is the part that does not.

## The one rule that matters most

**Judge the code against the rest of the system, not against its own documents.**

A generated PR arrives with a plan that argues for it, deviation notes that explain it, and docstrings
that defend it. Auditing that prose is easy and mostly worthless: an inconsistency between two
arguments changes nothing for anyone. What changes things is how the code behaves next to the parts it
has to live with — here, the DealiiX editor and the C++ `coral` backend. PR #28's most valuable
finding came from loading a fixture in the editor; the next from reading the *other* backend and
finding it models the same feature a completely different way.

**The plan is a map, not evidence.** Read it first — you need to know what changed and where — but
never let it verify anything. So check a claim in the documents **only when someone would re-derive a
decision from it.** A wrong count in `CLAUDE.md` qualifies: the next person budgets from it. A false
premise qualifies: it forecloses an option that is actually open. "This paragraph argues X while that
one argues Y" does not.

## Order of work

1. **Orient from the documents.** Plan, desiderata, the issue — enough to know what moved and where.
   If the change is large or hard to follow, this is where an aid earns its keep, and the options are
   interchangeable: a debugger walkthrough, a few prints, or a written "read these files in this
   order" from an assistant. Pick by cost, not by ceremony. A debugger walkthrough here means
   `.vscode/launch.json` plus a `debug-walkthrough.md` beside the review, since `.vscode/` is
   gitignored and would not survive a clone.
2. **Take the artifact through its real consumer.** Not the test suite, not the CLI — the thing that
   will actually open the file. Both blocking findings in the PR #28 review were invisible to the
   Python suite and obvious in the editor.
3. **Evaluate the design**, decision by decision: what was chosen, what it costs, what is still
   unverified. Before the line-by-line audit, because it tells you which parts are worth the time.
4. **Audit implementation against plan**, scripting anything countable.
5. **Read the tests, then mutate them.** Two different jobs — see below.
6. **Write the findings as you go**, in a document separate from any earlier round the author is
   working from. A review the author is reading should not move under them.

A default, not a checklist to run in full. For a small, self-contained PR a step can be skipped or
reordered on judgement — say which, and why.

## Specific to generated work

- **Checkboxes are claims. "Verified" is a claim.** Produced by the same process as the code.
- **Prose defending a mechanism is a reason to look at the mechanism.** 177 lines for 15 one-line
  functions means most of the file is justification, and that is where a wrong assumption hides
  comfortably.
- **Expect coherent incorrectness.** Sequential decisions build an internally consistent design on top
  of the first misunderstanding. Everything agrees with everything, and the disagreement with reality
  is outside the documents.
- **Errors cluster in the essential complexity, and arrive as the idiomatic answer.** The mechanical
  parts are usually right; the judgement calls come out as whatever is most represented in training
  data, which may be wrong for this system.
- **Don't approve code you cannot explain**, and treat "the AI wrote it" as the red flag it is.

## The tests: read them *and* mutate them

The two find **different defects, and neither finds the other's.** PR #29 is the demonstration: 37
mutants killed 34, and all 3 survivors traced to one cause. Reading the same suite found three more
findings, with zero overlap.

**Mutation asks: would a wrong answer be noticed?** Coverage says a line ran, not that anyone checked
the result.

- Pick mutants from the **design decisions**, not mechanically. Each asks one question: is purity
  pinned? is fail-loud pinned? is the precedence rule pinned?
- Change one line, run the fastest relevant subset, revert. Script it, and assert the tree is clean
  at the end (`git diff --quiet`).
- **fails** = pinned. **passes** = a gap or an equivalent mutant, and establish which before
  reporting. **half the suite fails** = over-coupled tests.
- A survivor often points at something *deleted*: all three of PR #29's came from a refactor that
  dropped three test classes without recording it. And sometimes it means nobody ever decided the
  behaviour, which is more useful to say.

**Reading asks: is this test carrying its weight?** Mutation is blind here by construction — a
redundant test is one whose every mutant some *other* test also kills, so it can never survive
anything. PR #29's sharpest case was a test re-implementing a check the test three lines above it
already ran: unfalsifiable, and only reading finds it. Look for redundancy (two tests pinning one
fact, or a unit test dominated by a byte-compared golden), tautology (the expected value derived from
the code under test), assertions that assert nothing (`is not None` where a real value was
available), and names or docstrings that promise more than the body checks.

A suite can score perfectly on mutation and still be full of these.

## Returning a review unread

Legitimate, and sometimes right: if the artifact fails at its own purpose — it does not work in the
consumer it exists for — hand it back with the reproduction and let the author scope the fix. Doing
the scoping yourself means reviewing your own decision. Say plainly what was *not* reviewed.

## Writing it down

- **Findings first, evidence second**, and the verdict — blocking, worth fixing here, follow-up —
  where it is seen first. A long review does not get read, so provenance goes at the end.
- **Record the scope**: what was examined, by what method, and what was not. A reader cannot tell a
  thorough review from a shallow one otherwise, and it is what makes "this blocks" credible rather
  than assertive. Overstating and understating coverage are both failures.
- **Separate what blocks from what does not**, and say when something is not this PR's code at all.
- **File follow-ups as issues**; a review is not a backlog.
- **Cross-reference only when it earns its place**, and do not narrate your own corrections — if a
  note turns out to be wrong, fix the note.
- **Tone:** the findings are about the artifact, not the author. "This looks like an oversight from
  the generated suggestion; let's fix it" is the register that works.

## Repo conventions

- A review lives in `issues/<n>-<slug>/review/`, one file per round — `pr-<n>-review.md`,
  `pr-<n>-review-round-2.md`. Add a `README.md` summary once there is more than one round.
- Counted claims get recomputed, and the reproduction goes in the review.
- `docs/` and `CLAUDE.md` are checked against the code, not the plan. This file included.

## Reading

| resource | for |
| --- | --- |
| [Google's Code Review Developer Guide](https://google.github.io/eng-practices/review/) | the canonical ordering: design first, then complexity, then tests |
| Addy Osmani, *Beyond Vibe Coding* (O'Reilly, 2025) | Ch 5, Ch 8's "Code Review Strategies", Ch 10's "Challenges and Limitations" — the only book aimed squarely at this |
| Fowler, *Refactoring* (2nd ed.) | judging whether a behaviour-preserving change preserved behaviour |
| Feathers, *Working Effectively with Legacy Code* | characterization tests, and telling a real one from a decorative one |
| [Simon Willison on AI-assisted programming](https://simonwillison.net/tags/ai-assisted-programming/) | taking responsibility for generated output |
| METR 2025 RCT | measured a slowdown where participants predicted a speedup — calibration against your own sense of pace |
