---
name: security-audit
description: OWASP Top 10, dependency scanning, secrets detection, auth patterns, input validation. Use when reviewing code for security or hardening an application.
version: 1.0.0
tags:
  - security
  - owasp
  - auth
  - validation
---

# Security Audit

## OWASP Top 10 Checklist
1. **Injection** — parameterized queries, never string concat SQL
2. **Broken auth** — JWT with expiry, refresh tokens, bcrypt passwords
3. **Sensitive data exposure** — no secrets in code, env vars only
4. **XXE** — disable XML external entities
5. **Broken access control** — check permissions per endpoint
6. **Misconfiguration** — no debug mode in prod, CORS restricted
7. **XSS** — escape output, CSP headers
8. **Insecure deserialization** — validate all input with Pydantic
9. **Known vulnerabilities** — `pip audit`, `npm audit`
10. **Insufficient logging** — log auth failures, access denied

## Secrets Detection
```bash
# Check for hardcoded secrets
grep -rn "password\|secret\|api_key\|token" --include="*.py" . | grep -v ".env" | grep -v "test"

# Never commit
.env
*.pem
*_key
```

## Input Validation (Pydantic)
```python
class UserInput(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150)

# Always validate before processing
@router.post("/users")
async def create_user(data: UserInput):  # Pydantic validates automatically
    ...
```

## Database Security
```python
# GOOD: parameterized query
await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

# BAD: string interpolation (SQL injection)
await conn.fetchrow(f"SELECT * FROM users WHERE id = {user_id}")
```

## Auth Patterns
- API keys in headers: `Authorization: Bearer <token>`
- JWT with short expiry (15min access, 7d refresh)
- Rate limiting per IP and per user
- CORS: restrict to known origins in production

## Do NOT
- Hardcode secrets in source code
- Use MD5 or SHA1 for passwords (use bcrypt)
- Trust client-side validation alone
- Log sensitive data (passwords, tokens, PII)
- Disable HTTPS in production
