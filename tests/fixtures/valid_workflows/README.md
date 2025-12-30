# Valid Workflow Fixtures

This directory is reserved for test-specific valid workflow fixtures.

The main workflow files used for testing are located in the project root:
- `network-from-fe-obstacle.json` - PhiFlow obstacle workflow
- `network-from-fe-smoke_plume.json` - PhiFlow smoke plume workflow
- `network-from-fe-math.json` - Math operations workflow
- `network-from-fe-classes.json` - Calculator class workflow
- `network-from-fe-functions.json` - Function calls workflow
- `network-from-fe.json` - Default workflow

These files are referenced via fixtures in `conftest.py`.

Additional test-specific workflows can be added here as needed.