---
name: api-design
description: REST API design patterns, OpenAPI spec, endpoint naming, request/response schemas. Use when creating or refactoring APIs.
version: 1.0.0
tags:
  - api
  - rest
  - openapi
  - fastapi
---

# API Design

## Endpoint Naming
- Nouns, not verbs: `/users`, not `/getUsers`
- Plural: `/tasks`, `/agents`, `/sessions`
- Nested resources: `/agents/{id}/runs`
- Actions as sub-resources: `POST /tasks/{id}/cancel`

## HTTP Methods
| Method | Purpose | Idempotent |
|--------|---------|-----------|
| GET | Read | Yes |
| POST | Create | No |
| PUT | Full replace | Yes |
| PATCH | Partial update | Yes |
| DELETE | Remove | Yes |

## Response Patterns
```python
# Success
{"data": {...}, "meta": {"total": 42}}

# Error
{"detail": "Not found", "status_code": 404}

# List with pagination
{"items": [...], "total": 100, "page": 1, "per_page": 20}
```

## FastAPI Conventions
```python
@router.post("/tasks/code", response_model=CodeTaskResponse)
async def run_code_task(request: CodeTaskRequest) -> CodeTaskResponse:
    """Docstring becomes OpenAPI description."""

# Use Pydantic models for request/response
class CodeTaskRequest(BaseModel):
    repo_url: str = Field(..., description="Git repository URL")
    task: str = Field(..., description="Task description")

# Use HTTPException for errors
raise HTTPException(status_code=400, detail="Invalid repo URL")

# Use APIRouter for grouping
router = APIRouter(prefix="/tasks", tags=["tasks"])
```

## Status Codes
- 200: Success (GET, PATCH)
- 201: Created (POST)
- 204: No content (DELETE)
- 400: Bad request (validation error)
- 404: Not found
- 422: Unprocessable entity (Pydantic validation)
- 500: Internal server error

## Do NOT
- Use verbs in URLs (`/getUser`, `/deleteTask`)
- Return 200 for errors
- Nest more than 2 levels deep (`/a/{id}/b/{id}/c` is too deep)
- Mix singular and plural (`/user` vs `/users`)
