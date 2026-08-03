# Valid Workflow Fixtures

This directory contains test workflow fixtures used throughout the test suite.

## Workflow Files

- `network-from-fe-obstacle.json` - PhiFlow obstacle workflow
- `network-from-fe-smoke_plume.json` - PhiFlow smoke plume workflow
- `network-from-fe-math.json` - Math operations workflow
- `network-from-fe-classes.json` - Calculator class workflow
- `network-from-fe-functions.json` - Function calls workflow
- `network-from-fe.json` - Full PhiFlow workflow (the `"default"` fixture key; mirrors `examples/phiflow/network-from-fe.json`)

Collection graphs, built from the host's builtin `list_*` / `set_*` / `dict_*` nodes. The first three
need **no plugin at all** and are executed with `plugins=[]`, which is the property they exist to
assert; they are hand-written rather than exported from the editor, so they carry no `position` keys.

- `network-collections-list.json` - build a list, measure it, index it, remove an element
- `network-collections-dict.json` - set two keys, read one, delete the other
- `network-collections-set.json` - add a duplicate and observe deduplication, then sort to a list
- `network-collections-math.json` - a list feeding the math plugin's `add` (the only one needing a
  plugin; mirrors `examples/collections/list.json`'s builder half)

These files are referenced via fixtures in `tests/conftest.py`.

Additional test-specific workflows can be added here as needed.