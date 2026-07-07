# Valid Node Registry Fixtures

This directory contains registry JSON files used for testing the node type system.

## Registry Files

- `registry-math.json` - Registry for math module (mathematical operations and Calculator class)
- `registry-phiflow.json` - Registry for PhiFlow physics simulation module
- `registry-py.json` - Default/combined registry file

These files are auto-generated using:
```bash
python main.py -p "math" register --output="tests/fixtures/valid_nodes/registry-math.json"
python main.py -p "phiflow" register --output="tests/fixtures/valid_nodes/registry-phiflow.json"
```

## Usage in Tests

These files are referenced via the `registry_files` fixture in `tests/conftest.py` and can be loaded using the `load_registry` fixture:

```python
def test_example(load_registry):
    registry = load_registry("math")
    # Test code here
```

Available registry names: `"math"`, `"phiflow"`, `"default"`