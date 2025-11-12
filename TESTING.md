# Testing Guide

## Overview

This project uses `pytest` for unit and integration testing. Tests are located in the `tests/` directory with the following structure:

```
tests/
├── __init__.py
├── conftest.py          # Pytest configuration and shared fixtures
├── unit/                # Unit tests for individual modules
│   ├── __init__.py
│   ├── test_audio_capture.py
│   └── test_translator.py
└── integration/         # Integration tests
    └── __init__.py
```

## Prerequisites

Install testing dependencies:

```bash
pip install pytest pytest-cov pytest-mock
```

## Running Tests

### Run all tests

```bash
pytest
```

### Run specific test file

```bash
pytest tests/unit/test_audio_capture.py
```

### Run specific test class

```bash
pytest tests/unit/test_audio_capture.py::TestAudioCapture
```

### Run specific test method

```bash
pytest tests/unit/test_audio_capture.py::TestAudioCapture::test_init_with_specific_device
```

### Run tests by marker

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run slow tests
pytest -m slow
```

### Run with coverage report

```bash
# Terminal report
pytest --cov=. --cov-report=term

# HTML report
pytest --cov=. --cov-report=html
# Open htmlcov/index.html in browser
```

### Run with verbose output

```bash
pytest -v
```

### Run with detailed output

```bash
pytest -vv
```

## Test Categories

### Unit Tests (`tests/unit/`)

Test individual functions and classes in isolation using mocks.

**Markers:** `@pytest.mark.unit`

**Example:**
```python
@pytest.mark.unit
def test_audio_callback_puts_data_in_queue(self):
    # Test implementation
    pass
```

### Integration Tests (`tests/integration/`)

Test interaction between multiple components.

**Markers:** `@pytest.mark.integration`

**Example:**
```python
@pytest.mark.integration
def test_full_audio_pipeline(self):
    # Test implementation
    pass
```

### Slow Tests

Tests that take significant time to run.

**Markers:** `@pytest.mark.slow`

**Skip slow tests:**
```bash
pytest -m "not slow"
```

### Hardware-Dependent Tests

Tests requiring specific hardware (audio devices, GPU, etc.).

**Markers:**
- `@pytest.mark.requires_audio` - Requires audio hardware
- `@pytest.mark.requires_model` - Requires ML models

**Skip hardware tests:**
```bash
pytest -m "not requires_audio and not requires_model"
```

## Writing Tests

### Test Structure

```python
import unittest
from unittest.mock import Mock, patch

class TestMyComponent(unittest.TestCase):
    """Test cases for MyComponent class"""

    def setUp(self):
        """Set up test fixtures"""
        # Initialize test data
        pass

    def tearDown(self):
        """Clean up after tests"""
        # Cleanup code
        pass

    def test_specific_behavior(self):
        """Test description"""
        # Arrange
        expected = "result"

        # Act
        actual = my_function()

        # Assert
        self.assertEqual(actual, expected)
```

### Using Mocks

```python
from unittest.mock import Mock, patch, MagicMock

# Mock an object
mock_obj = Mock()
mock_obj.method.return_value = "mocked value"

# Mock a function call
with patch('module.function') as mock_func:
    mock_func.return_value = 42
    # Test code
```

### Using Fixtures (pytest)

```python
@pytest.fixture
def my_fixture():
    """Fixture description"""
    # Setup
    data = create_test_data()
    yield data
    # Teardown
    cleanup(data)

def test_with_fixture(my_fixture):
    """Test using fixture"""
    result = process(my_fixture)
    assert result is not None
```

## Best Practices

1. **Test Naming**: Use descriptive names starting with `test_`
   - Good: `test_audio_callback_puts_data_in_queue`
   - Bad: `test1`

2. **One Assertion Per Test**: Focus each test on a single behavior
   ```python
   # Good
   def test_returns_correct_value(self):
       self.assertEqual(func(), expected)

   def test_raises_on_invalid_input(self):
       with self.assertRaises(ValueError):
           func(invalid_input)
   ```

3. **Use Arrange-Act-Assert**: Structure tests clearly
   ```python
   def test_example(self):
       # Arrange
       input_data = create_input()

       # Act
       result = process(input_data)

       # Assert
       self.assertEqual(result, expected)
   ```

4. **Mock External Dependencies**: Don't rely on network, filesystem, or hardware
   ```python
   @patch('module.external_api_call')
   def test_with_mocked_api(self, mock_api):
       mock_api.return_value = {'status': 'ok'}
       # Test code
   ```

5. **Test Edge Cases**: Cover boundary conditions
   - Empty inputs
   - None values
   - Maximum values
   - Error conditions

## Continuous Integration

Tests should be run automatically in CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest --cov=. --cov-report=xml
```

## Coverage Goals

- **Minimum coverage**: 60%
- **Target coverage**: 80%
- **Critical modules**: 90%+ (audio/, translation/)

View current coverage:
```bash
pytest --cov=. --cov-report=term-missing
```

## Troubleshooting

### ImportError: No module named 'X'

Add project root to PYTHONPATH:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Tests fail with "No audio device found"

Skip hardware-dependent tests:
```bash
pytest -m "not requires_audio"
```

### Slow test execution

Run only fast tests:
```bash
pytest -m "not slow"
```

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [unittest documentation](https://docs.python.org/3/library/unittest.html)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
