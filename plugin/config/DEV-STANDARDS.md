# DEV-STANDARDS.md

> Development standards for this project.
> Read by dev-planner, dev-executor, and dev-code-review on every run.
> Sections 5 (SOLID), 6 (Testing baseline), and 8 (Security baseline) are PRE-POPULATED and
> enforced by default. Sections marked [FILL IN] need your project specifics before the dev
> skills produce fully accurate output.
> This file is yours to edit. implr will never overwrite it once it exists.

---

## 1. Project Stack

```
Frontend:         REPLACE_ME_FRONTEND
Backend:          REPLACE_ME_BACKEND
Database + ORM:   REPLACE_ME_DB
HTTP client:      [FILL IN] e.g. axios / native fetch
Auth:             [FILL IN] e.g. JWT access + refresh tokens
Cache / Queue:    [FILL IN] e.g. Redis 7 / BullMQ
```

---

## 2. Folder Structure  [FILL IN]

```
src/
  modules/            # one folder per domain
    auth/
      auth.controller.ts
      auth.service.ts
      auth.repository.ts
      auth.types.ts
      auth.test.ts
  shared/             # cross-cutting utilities, base classes, middleware
  config/             # env config and validation
  db/                 # migrations, schema, seeds
tests/
  integration/
  e2e/
```

---

## 3. Naming Conventions  [FILL IN — defaults shown]

| Artefact | Convention | Example |
|----------|-----------|---------|
| Files | kebab-case | user-profile.service.ts |
| Classes | PascalCase | UserProfileService |
| Interfaces | PascalCase, no I-prefix unless project says otherwise | UserProfile |
| Functions | camelCase | getUserById |
| Constants | SCREAMING_SNAKE | MAX_RETRY_COUNT |
| DB tables | snake_case plural | user_profiles |
| DB columns | snake_case | created_at |
| API routes | kebab-case plural nouns | /api/user-profiles/:id |
| Env vars | SCREAMING_SNAKE | DATABASE_URL |

---

## 4. Architecture Patterns  [FILL IN]

### Layering
```
Controller -> Service -> Repository -> Database
```
- Controllers: HTTP only (parse, validate, delegate, respond). No business logic.
- Services: all business logic. No direct DB access.
- Repositories: all DB queries. No business logic.
- Dependencies flow downward only; never skip a layer.

### Dependency Injection
[FILL IN] e.g. "NestJS DI container" or "manual constructor injection".

### Error Handling
[FILL IN] e.g.
- Typed errors (AppError with code + statusCode)
- Services throw; controllers map to HTTP
- Never swallow errors silently
- Wrap external errors in domain errors

### Validation
[FILL IN] e.g.
- All inputs validated at the controller boundary (Zod/Joi)
- Never pass raw DB entities to responses; map to response DTOs

---

## 5. SOLID Principles  (PRE-POPULATED — enforced by default)

These are enforced by dev-planner (at design level) and dev-executor (at code level), and
checked by dev-code-review.

### Single Responsibility
Each class/module has one reason to change. If describing a class needs "and", split it.

### Open/Closed
Extend via composition and interfaces, not by modifying existing classes. Prefer new
implementations over edits. Replace type/kind switch-chains with polymorphism or strategy.

### Liskov Substitution
Subtypes must be substitutable for their base types without breaking correctness. No overrides
that throw NotImplemented or silently no-op.

### Interface Segregation
Prefer small, focused interfaces. Clients must not depend on methods they do not use.

### Dependency Inversion
Depend on abstractions, not concretions. High-level modules must not import low-level modules
directly. Inject dependencies through constructors; no `new ConcreteClass()` for collaborators
that should be injected.

---

## 6. Testing Standards  (PRE-POPULATED baseline — extend as needed)

### TDD (when tdd_required is true)
1. Write a failing test describing expected behaviour (red).
2. Write minimum code to pass (green).
3. Refactor without breaking tests (refactor).
Never write implementation before the test when TDD is required.

### Complexity-to-TDD mapping
XS, S -> tests after implementation acceptable.
M, L, XL -> TDD required (tests first).
(Threshold configurable via default_tdd_threshold in implr.config.yaml.)

### Test structure
```
describe('UserService', () => {
  describe('createUser', () => {
    it('creates a user with a hashed password', ...)
    it('throws ConflictError when email already exists', ...)
  })
})
```

### What to test
- Unit: service methods, pure functions, validators, transformers.
- Integration: repositories against a real test DB, full HTTP endpoints.
- E2E: critical user journeys only.
- Do not unit-test framework internals or migrations.

### Coverage targets  [FILL IN — defaults shown]
- Service layer: 80% line coverage minimum.
- Integration: all happy paths plus primary error paths.

---

## 7. API Design  [FILL IN — defaults shown]

- REST resource naming: /api/{resource}/{id}/{sub-resource}
- Verbs: GET read, POST create, PUT full replace, PATCH partial, DELETE remove
- Success envelope: { "data": ..., "meta": ..., "error": null }
- Error envelope: { "data": null, "error": { "code": "...", "message": "..." } }
- Pagination: cursor-based preferred for large datasets
- Versioning: REPLACE_ME_VERSIONING

---

## 8. Security Standards  (PRE-POPULATED baseline — enforced by default)

- Validate and sanitise all external input at the boundary.
- Never log sensitive data: passwords, tokens, secrets, keys, PII, payment data.
- Parameterised queries only; never interpolate input into SQL.
- Secrets only in environment variables; never in source or committed config.
- Authentication required by default on all endpoints; opt out explicitly.
- Rate limiting on all public mutation endpoints.
- Password hashing with bcrypt or argon2, cost factor >= 10.
- Never return stack traces or internal error detail to clients.
- Verify resource ownership on every lookup (prevent insecure direct object reference).

---

## 9. Logging and Observability  [FILL IN]

- Structured JSON logging (e.g. Pino / Winston).
- Levels: error, warn, info, debug; production at info.
- Each request logged with method, path, status, duration, request_id.
- Each error logged with message, stack, request_id, user_id (if authenticated).
- request_id (UUID per request) propagated for tracing.

---

## 10. Git and PR Conventions  [FILL IN — defaults shown]

- Branch: feat/REQ-F-001-slug, fix/REQ-F-001-slug, chore/description
- Commit: feat(auth): implement password reset flow [REQ-F-001]
- PR title includes requirement id: [REQ-F-001] User password reset
- PR requires: passing CI, dev-code-review output attached, one human approval
- Squash merge to main

---

## 11. Environment Configuration  [FILL IN]

- All config from environment variables; no hardcoded values.
- Validate required env vars at startup; fail fast if missing.
- Maintain a committed .env.example; never commit .env.
- Environments: local, test, staging, production.
