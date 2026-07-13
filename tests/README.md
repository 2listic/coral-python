# Coral Python Test Suite

Comprehensive test suite for the coral-python workflow execution system.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Pytest fixtures and configuration
├── test_executor.py            # Core WorkflowExecutor tests
├── test_registry.py            # Registry generation tests
├── test_modules.py             # Module loading tests
├── test_integration.py         # End-to-end workflow tests
└── fixtures/
    ├── valid_workflows/        # Valid workflow test files (lean: nodes keyed by id, identified by type)
    └── valid_nodes/            # Registry fixtures (node-type definitions)
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Files
```bash
pytest tests/test_executor.py
pytest tests/test_integration.py
```

### Run Tests by Category (Markers)
```bash
# Run only integration tests
pytest -m integration

# Run only unit tests
pytest -m unit

# Run only math module tests
pytest -m math

# Run only phiflow tests (requires PhiFlow installed)
pytest -m phiflow

# Skip slow tests
pytest -m "not slow"
```

### Run Specific Test Class or Function
```bash
pytest tests/test_executor.py::TestPrimitiveNodeExecution
pytest tests/test_executor.py::TestPrimitiveNodeExecution::test_int_primitive
```

### Verbose Output
```bash
pytest -v
pytest -vv  # Extra verbose
```

### Show Print Statements
```bash
pytest -s
```

### Code Coverage
```bash
# Run with coverage report
pytest --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Run in Parallel (if pytest-xdist installed)
```bash
pip install pytest-xdist
pytest -n auto
```

## Test Categories

### Unit Tests (`test_executor.py`, `test_registry.py`, `test_modules.py`)
- Test individual components in isolation
- Fast execution
- No external dependencies (except PhiFlow for some module tests)

### Integration Tests (`test_integration.py`)
- Test complete workflows using real JSON files
- Tests the entire execution pipeline
- Uses actual workflow files from project root:
  - **PhiFlow workflows**: `network-from-fe-obstacle.json`, `network-from-fe-smoke_plume.json`
  - **Math workflows**: `network-from-fe-math.json`, `network-from-fe-classes.json`, `network-from-fe-functions.json`

## Test Fixtures

### Available Fixtures (from `conftest.py`)

- **`project_root`**: Path to project root directory
- **`workflow_files`**: Dictionary mapping workflow names to file paths
- **`registry_files`**: Dictionary mapping registry names to file paths
- **`load_workflow`**: Factory to load workflow JSON by name
- **`load_registry`**: Factory to load registry JSON by name
- **`simple_workflow_dict`**: Simple valid workflow for testing
- **`circular_workflow_dict`**: Workflow with circular dependency
- **`temp_workflow_file`**: Factory to create temporary workflow files
- **`mock_print`**: Mock print function to capture output

### Example Usage
```python
def test_example(workflow_files, load_workflow):
    # Get path to workflow file
    math_workflow_path = workflow_files["math"]

    # Load workflow data
    workflow_data = load_workflow("math")

    # Execute workflow
    executor = WorkflowExecutor(str(math_workflow_path), modules=['math'])
    results = executor.execute()
```

## Writing New Tests

### Test Naming Convention
- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Test
```python
import pytest
from executor import WorkflowExecutor

class TestMyFeature:
    """Test description."""

    @pytest.mark.unit
    def test_my_specific_case(self, temp_workflow_file):
        """Test specific behavior."""
        workflow = {
            "workflow": {
                "nodes": [...],
                "edges": [...]
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), modules=['math'])
        results = executor.execute()

        assert "expected_node" in results
        assert results["expected_node"] == expected_value
```

### Using Markers
```python
@pytest.mark.integration  # Integration test
@pytest.mark.unit        # Unit test
@pytest.mark.phiflow     # Requires PhiFlow
@pytest.mark.math        # Uses math module
@pytest.mark.string      # Uses string module
@pytest.mark.slow        # Slow-running test
```

## Test Coverage

The test suite covers:

1. **Primitive Node Execution**: int, float, str, bool types
2. **Function Node Execution**: Math operations, chaining
3. **Constructor Node Execution**: Class instantiation
4. **Method Node Execution**: Instance method calls
5. **Topological Sorting**: DAG ordering, cycle detection
6. **Edge Ordering**: Parameter order via `target_input`
7. **Module Loading**: Dynamic function/class map building
8. **Registry Generation**: Schema creation, type conversion
9. **Integration**: Real workflow execution
10. **Error Handling**: Missing nodes, invalid functions, cycles

## Continuous Integration

To set up CI/CD with GitHub Actions, create `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install uv
          uv pip sync requirements.txt
      - name: Run tests
        run: pytest --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### PhiFlow Tests Skipped
If PhiFlow tests are skipped, install PhiFlow:
```bash
uv pip install phiflow
```

### Import Errors
Ensure you're running tests from the project root:
```bash
cd /path/to/coral-python
pytest
```

### Test Discovery Issues
Check that test files follow naming conventions:
- Files: `test_*.py`
- Functions: `test_*()`
- Classes: `Test*`

## Adding New Test Cases

When adding new features to coral-python:

1. Add unit tests in appropriate `test_*.py` file
2. Add integration test with a real workflow JSON
3. Update fixtures if needed
4. Mark tests appropriately (`@pytest.mark.unit`, etc.)
5. Ensure tests are independent and can run in any order
6. Use descriptive test names that explain what's being tested

## Performance Testing

For performance-critical tests:

```python
@pytest.mark.slow
def test_performance(workflow_files):
    import time
    start = time.time()

    executor = WorkflowExecutor(str(workflow_files["math"]), modules=['math'])
    results = executor.execute()

    elapsed = time.time() - start
    assert elapsed < 1.0, f"Execution too slow: {elapsed:.2f}s"
```
