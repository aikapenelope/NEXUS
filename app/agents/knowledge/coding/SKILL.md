---
name: coding
description: Software engineering workflow, code quality standards, and development best practices
version: 1.0.0
tags:
  - coding
  - engineering
  - development
  - testing
---

# Software Engineering Skill

You are writing production code. Follow these standards.

## Development Workflow

### Before Writing Code
1. Read existing code to understand patterns and style
2. Check for project conventions (AGENTS.md, CONTRIBUTING.md, .editorconfig)
3. Understand the test framework and how tests are structured
4. Plan your changes using the todo list for multi-step work

### While Writing Code
1. Match the project's existing style exactly
2. One logical change at a time -- don't mix refactoring with features
3. Write tests alongside implementation, not after
4. Run type checker and linter after every file change
5. Commit frequently with descriptive messages

### After Writing Code
1. Run the full test suite -- fix any failures
2. Run type checking -- fix all errors
3. Run linting -- fix all warnings
4. Review your own diff before committing
5. Write a clear commit message explaining WHY, not WHAT

## Code Quality Checklist

### Every Function
- [ ] Has a docstring explaining purpose, args, returns
- [ ] Has type hints on all parameters and return type
- [ ] Handles errors explicitly (no bare except)
- [ ] Has at least one test

### Every File
- [ ] Imports are organized (stdlib, third-party, local)
- [ ] No unused imports
- [ ] No hardcoded secrets or credentials
- [ ] Module docstring explaining the file's purpose

### Every PR
- [ ] All tests pass
- [ ] Type checker reports 0 errors
- [ ] Linter reports 0 errors
- [ ] Changes are focused on one logical unit

## Error Handling Patterns

```python
# GOOD: Specific exception with context
try:
    result = await db.fetch(query)
except asyncpg.PostgresError as e:
    logger.error(f"Query failed: {e}", exc_info=True)
    raise ServiceError(f"Database query failed: {e}") from e

# BAD: Bare except that swallows everything
try:
    result = await db.fetch(query)
except:
    pass
```

## Testing Patterns

```python
# GOOD: Descriptive test with clear assertion
async def test_create_agent_returns_valid_config():
    """Creating an agent from description produces a valid AgentConfig."""
    config = await build_agent("A research agent")
    assert config.name
    assert config.role in ("worker", "analysis")

# BAD: Vague test name, no docstring
async def test_agent():
    result = await build_agent("test")
    assert result
```

## Git Commit Format

```
<type>: <description>

Types:
  feat:     New feature
  fix:      Bug fix
  refactor: Code change that neither fixes a bug nor adds a feature
  docs:     Documentation only
  test:     Adding or fixing tests
  chore:    Build process, dependencies, CI
```

## When You're Stuck

1. Re-read the error message carefully -- it usually tells you exactly what's wrong
2. Search the codebase for similar patterns (grep, glob)
3. Check the project's test suite for usage examples
4. Search the web for the specific error message
5. If still stuck after 3 attempts, explain what you tried and ask for help
