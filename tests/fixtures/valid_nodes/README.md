# Valid Node Registry Fixtures

This directory contains registry JSON files used for testing the node type system.

## Registry Files

- `registry-math.json` - Registry for the math module (mathematical operations and Calculator class)
- `registry-phiflow.json` - Registry for the PhiFlow physics simulation module
- `registry-py.json` - Combined registry for all modules (math, string, phiflow)

All files use the DealiiX platform registry format: entries are keyed by node `type` and each is
marked `is_valid: true`.

These files are auto-generated using:
```bash
coral -p "math" register --output="tests/fixtures/valid_nodes/registry-math.json"
coral -p "phiflow" register --output="tests/fixtures/valid_nodes/registry-phiflow.json"
coral register --output="tests/fixtures/valid_nodes/registry-py.json"
```

## Usage in Tests

These files are referenced via the `registry_files` fixture in `tests/conftest.py` and can be loaded using the `load_registry` fixture:

```python
def test_example(load_registry):
    registry = load_registry("math")
    # Test code here
```

Available registry names: `"math"`, `"phiflow"`, `"default"`