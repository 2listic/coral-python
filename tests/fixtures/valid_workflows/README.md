# Valid Workflow Fixtures

This directory contains test workflow fixtures used throughout the test suite.

## Workflow Files

- `network-from-fe-obstacle.json` - PhiFlow obstacle workflow
- `network-from-fe-smoke_plume.json` - PhiFlow smoke plume workflow
- `network-from-fe-math.json` - Math operations workflow
- `network-from-fe-classes.json` - Calculator class workflow
- `network-from-fe-functions.json` - Function calls workflow
- `network-from-fe.json` - Full PhiFlow workflow (the `"default"` fixture key; mirrors `examples/phiflow/network-from-fe.json`)

These files are referenced via fixtures in `tests/conftest.py`.

Additional test-specific workflows can be added here as needed.