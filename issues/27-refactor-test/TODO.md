# TODO — open problems after issue #27

Everything in [`plan.md`](plan.md) is implemented and verified: nine steps, 450 tests, the layout
restructure included. This file is what is **left**, written to be picked up cold.

Nothing here blocks anything. Each item says what is wrong, why it matters, and what "done" looks
like — so that a future session can take one without re-deriving the context.

State at the time of writing: branch `27-refactor-test`, **nothing committed**, 83 changed paths
(66 pure renames, 6 renames-with-docstring-edits, 11 modified files).

| | |
| --- | --- |
| full suite | 450 passed (~38s) |
| fast lane | 446 passed (~0.8s) |
| `coral-app/tests` + `coral-core/tests`, no plugins installed | 232 passed, **0 skipped** |
| all three plugins uninstalled, whole suite | 250 passed, 13 skipped, 0 errors |
| coverage | 94% overall; phiflow 70%, the lowest |

---

## 1. The source-root list is duplicated three ways, and only one copy is guarded

**Severity: this is the one worth doing first.** It is the only item that can silently *reduce*
coverage of a rule.

Four places must agree on "which directories are this repo's distributions":

| where | form |
| --- | --- |
| `pyproject.toml:22` | `[tool.uv.workspace] members = ["coral-core", "coral-app", "plugins/*"]` |
| `pyproject.toml:30` | `[tool.coverage.run] source = ["coral-core", "coral-app", "plugins"]` |
| `pytest.ini:29` | `testpaths = tests coral-core/tests coral-app/tests plugins/*/tests` |
| `tests/invariants/test_source_rules.py:50` | `source_roots()` → `SOURCE_ROOTS` |

Before step 9 a single glob (`packages/*`) meant "every distribution" and all four read it. Now each
lists three roots. `test_source_roots_cover_every_distribution`
(`tests/invariants/test_source_rules.py:329`) compares `SOURCE_ROOTS` against the manifests actually on
disk, so it catches *"you added a package and forgot the invariants"*. **It does not check
`pytest.ini` or `pyproject.toml`.** Neither uv nor pytest can read a Python constant, which is why the
duplication exists at all; the comments in all three files say so, but a comment is not a guard.

**Measured, so the risk is stated accurately rather than feared:**

- adding a plugin under `plugins/` is **fully automatic** — verified by creating
  `plugins/coral-fake/` with a `pyproject.toml`, a `src/` and a `tests/`: all four globs picked it up
  and its test was collected with **no config edit**. The common case is safe.
- the gap is a **new category of root** — an `apps/`, a `tools/`, a second framework package not at the
  root. Then: three edits, one guarded, and a package whose tests are silently never collected while
  the suite stays green. The `from __future__ import annotations` rule would also stop covering it,
  which is the damaging one (it would collapse every registry socket of that package to `"any"`).

**Done looks like** one of:

- **(a)** a test asserting that `pytest.ini`'s `testpaths` and `pyproject.toml`'s `members`/`source`
  cover every directory in `distributions_on_disk()` — parse the two config files as text/TOML from
  `tests/invariants/`, which already reads files rather than importing code. Closes the gap properly
  and is maybe 30 lines; the awkward part is that `testpaths` is glob-shaped, so the assertion is
  "every distribution is matched by some entry", not string equality.
- **(b)** decide the gap is acceptable — the common case is automatic and a new root is a deliberate,
  reviewed act — and record *that* as the decision, so the next reader stops re-discovering it.

Do not "fix" it by collapsing the three lists into one: that was tried in the design and is
impossible, per the note at the top of `test_source_rules.py`.

---

## 2. A plugin named `fake` would break the build

**Pre-existing, not introduced by step 9** — found while testing item 1. Recorded because the failure
is remote from its cause and would cost someone an hour.

`TestHostTestsNameNoPlugin::test_host_suite_names_no_plugin_in_a_literal`
(`tests/invariants/test_source_rules.py:289`) forbids any string literal under `coral-app/tests`
*equal* to a plugin name. But `coral-app/tests/test_discovery.py:48` legitimately uses `"fake"` as a
bogus entry-point name:

```python
fake = EntryPoint(name="fake", value="builtins:int", group=PLUGIN_GROUP)
```

So installing a real plugin whose entry-point name is `fake` fails the invariants, pointing at the
host's tests, with nothing wrong in either file. The same holds for any word the host suite uses as a
literal.

**The rule therefore constrains the plugin namespace, not only the host suite's discipline.** That is
a real (small) cost of the exact-literal design chosen in step 3 — and the design is still right: a
bare-word grep would trip on `python_type_to_string`, on "a string value" in prose, and on every use
of the stdlib `math`, and would be silenced within a week.

**Done looks like** a decision, not necessarily a change. Options, cheapest first:

- **leave it**, and add one sentence to `tests/README.md`'s description of the rule saying plugin names
  must not collide with literals in the host suite. Recommended.
- rename the test's bogus name to something no plugin would ever be called
  (`"not-a-real-plugin"`), which removes today's collision but not the class of problem.
- narrow the rule to literals in *argument* position (`include=[...]`, `-p` strings) rather than any
  literal. More faithful to the intent, more machinery, and easier to get subtly wrong.

---

## 3. No mechanism stops `uv.lock` picking up unrelated upgrades

**What happened during step 9**, recorded in full under that step's deviation 1: `uv sync` ran while
`members` still said `packages/*`, which matched nothing. A memberless uv workspace is **valid**, so
the command succeeded — it uninstalled all five packages, re-resolved the lock from scratch, and
**silently upgraded `jax` 0.10.2 → 0.11.0** plus `jaxlib` and `matplotlib`.

It was caught, reverted, and the lock's diff is now exactly five `editable` path strings. But it was
caught by *reading the diff*, and nothing in the repo would have objected: a jax minor bump would have
arrived in a commit labelled "move directories".

**Done looks like** `uv lock --check` running somewhere that fails a change, which today means
either:

- a **pre-commit hook** — cheap, immediate, and the repo already has the hook infrastructure
  (`.pre-commit-config.yaml`, installed with `uv run pre-commit install`). It answers "is the lock
  consistent with the manifests?", which is *not* the same question as "did a version change?", so it
  would not have caught this particular bump on its own — the lock was internally consistent
  afterwards. Useful but not sufficient; note this before implementing.
- a **CI job**, which does not exist — there is no CI in this repo at all. The check that would
  actually have caught it is "the lock's non-path lines are unchanged unless a dependency was
  deliberately edited", i.e. a review habit or a diff check, not `uv lock --check`.

Worth deciding what is actually wanted here before writing anything: the honest smallest fix may be a
line in `CLAUDE.md` under Package Management saying *never `uv sync` with a stale `members`*, plus the
existing correction in `plan.md`.

---

## 4. `definitions/` is now an empty directory

It held **only** `__pycache__/*.pyc` (the `.py` files were long gone). Step 9's post-move cache
cleanup — `find . -name __pycache__ -type d -not -path "./.venv/*" -exec rm -rf {} +`, needed because
pytest's rewritten bytecode was still reporting pre-move paths — deleted them.

No git change: the `.pyc`s were ignored and git does not track empty directories. So `plan.md`'s
"Out of scope, noted — **still present**, deliberately not touched" is now "present and empty".

**Done looks like** `rmdir definitions`. Left undone because deleting it was explicitly out of scope
for #27 and it is not mine to decide.

---

## 5. A plugin's four names now differ three ways

The cost **L3** accepted, now real:

| | value |
| --- | --- |
| directory | `plugins/coral-math` |
| distribution (`pip install`) | `coral-plugin-math` |
| import package | `coral_plugin_math` |
| entry point (`-p`) | `math` |

Consequence: the string `coral-plugin-math` appears in the tree **only** inside that package's own
`pyproject.toml` — it is no longer greppable as a directory. A table in `CLAUDE.md`'s *Package layout*
section documents this.

**Nothing to do** unless the mismatch proves annoying in practice. If it does, the rejected
alternatives and their costs are tabulated in `plan.md` under *Rejected alternatives* — in particular,
renaming the distributions to match would break the documented `pip install --find-links` line and
every `uv add --package` example.

---

## 6. Carried over from `plan.md`'s *Left for another issue*, unchanged

Not touched by step 9; restated here so this file is the single entry point.

- **`test_tuple_return` is a poor node-type name.** `plugins/coral-math/src/coral_plugin_math/__init__.py:78`
  declares a node type starting with `test_`, so pytest collects it as a test and errors on a missing
  fixture. Worked around with an aliased import at
  `plugins/coral-math/tests/unit/test_functions.py:23` (**D13**). Renaming a node type is
  platform-facing, hence deferred.
- **phiflow's 13 `Any` slots of 21** are pinned as a *number*, not fixed, so improving them fails the
  test on purpose. Precise types would let graph check 6 reject a mis-wired simulation at t=0 instead
  of 30 seconds in. A plugin change, belonging to whoever owns the plugin. This is also most of why
  phiflow sits at **70% coverage** — the rest of its body is reachable only through the solver, which
  exactly one `slow` test runs.
- **A plugin declaring a function and a class under one name** cannot be reported by the host: the two
  surfaces are merged separately and the port table silently prefers the function. Each plugin's
  conformance test asserts its own two surfaces are disjoint, which is the only place the check can
  currently live.

---

## Suggested order

1. **Item 1**, option (a) or (b) — it is the only one that can weaken a guard.
2. **Item 2**, the one-sentence version — five minutes, prevents a confusing failure.
3. **Item 3** — decide what is actually wanted; possibly just documentation.
4. **Item 4** — one command, if you want it gone.
5. Items 5 and 6 need no action; they are here so nobody re-derives them.
