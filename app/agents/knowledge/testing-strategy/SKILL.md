---
name: testing-strategy
description: When to use unit vs integration vs e2e tests, mocking patterns, coverage targets, pytest best practices. Use when writing or planning tests.
version: 1.0.0
tags:
  - testing
  - pytest
  - coverage
  - mocking
---

# Testing Strategy

## Test Pyramid
```
        /  E2E  \        Few, slow, expensive
       / Integr. \       Some, medium speed
      /   Unit    \      Many, fast, cheap
```

## When to Use Each

**Unit tests** (80% of tests):
- Pure functions, data transformations, validators
- Fast, no I/O, no network, no database
- Mock external dependencies

**Integration tests** (15%):
- API endpoints with real DB (test container)
- Service-to-service communication
- Database queries with real schema

**E2E tests** (5%):
- Critical user flows only
- Browser automation (Playwright)
- Full stack: frontend -> API -> DB

## pytest Patterns
```python
# Fixtures for setup/teardown
@pytest.fixture
async def db_pool():
    pool = await asyncpg.create_pool(TEST_DSN)
    yield pool
    await pool.close()

# Parametrize for multiple cases
@pytest.mark.parametrize("input,expected", [
    (0, 1), (1, 1), (5, 120), (10, 3628800),
])
def test_factorial(input, expected):
    assert factorial(input) == expected

# Mock external services
def test_api_call(mocker):
    mocker.patch("app.client.fetch", return_value={"status": "ok"})
    result = process_data()
    assert result.status == "ok"
```

## Coverage Targets
- New code: 90%+ coverage
- Critical paths (auth, payments): 100%
- Utilities/helpers: 80%+
- Don't test framework code (FastAPI routing, Pydantic validation)

## Naming
```
tests/
  test_sessions.py      # matches app/sessions.py
  test_tasks.py         # matches app/tasks.py
  conftest.py           # shared fixtures
```

- `test_<function>_<scenario>`: `test_create_session_returns_id`
- `test_<function>_<edge_case>`: `test_divide_by_zero_raises`

## Do NOT
- Test implementation details (private methods)
- Write tests that depend on execution order
- Use `time.sleep()` in tests (use async fixtures)
- Skip tests without a reason comment
