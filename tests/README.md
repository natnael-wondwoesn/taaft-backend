# TAAFT Backend Tests

This directory contains tests for the TAAFT backend.

## Running Tests

To run all tests:

```bash
python -m pytest
```

To run specific test files:

```bash
python -m pytest tests/test_llm_service.py
```

To run tests with verbose output:

```bash
python -m pytest -v
```

## Test Dependencies

The tests require `pytest` and `pytest-asyncio` which are added to the main `requirements.txt` file.

## Test Structure

- `test_llm_service.py`: Tests for the LLM service including OpenAI model integration

## Writing Tests

- Use the `@pytest.mark.asyncio` decorator for async tests
- Mock external API calls using `unittest.mock` to avoid making real API calls
- Fixtures are defined in test files or `conftest.py` 