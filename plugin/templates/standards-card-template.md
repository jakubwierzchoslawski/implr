# Standards Card

> AUTO-GENERATED from docs/implr/config/DEV-STANDARDS.md by /implr-init.
> Do not edit by hand — run `/implr-init --refresh-card` to regenerate.
> Read by: task-executor, code-review-worker.
> Full standards (with rationale and [FILL IN] hints) live in DEV-STANDARDS.md.

## Stack
Frontend: {{FRONTEND}}
Backend:  {{BACKEND}}
Database: {{DB}}

## Naming
files=kebab-case · classes=PascalCase · fns=camelCase · const=SCREAMING_SNAKE
db.tables=snake_plural · db.cols=snake · routes=kebab-plural · env=SCREAMING_SNAKE

## Layering
Controller → Service → Repository → DB. No layer-skipping.
Controllers: HTTP-only (parse, validate, delegate, respond). Services: business logic.
Repositories: queries only. No business logic in repos.

## SOLID
SRP — one reason to change per class.
OCP — extend via composition; replace switch-chains with polymorphism / strategy.
LSP — subtypes substitutable; no NotImplemented overrides.
ISP — small focused interfaces; no fat dependencies.
DIP — depend on abstractions; constructor injection; no `new Concrete()` for collaborators.

## Testing
TDD when `tdd_required: true` on a task: red → green → refactor (strict).
Unit: services, validators, transformers. Integration: repos + endpoints.
E2E: critical user journeys only. Do not unit-test framework internals or migrations.

## Security (enforced)
- Validate and sanitise external input at the boundary.
- Never log secrets / tokens / PII / payment data.
- Parameterised queries only. Never interpolate input into SQL.
- Secrets only via env vars. Never in source or committed config.
- Auth required by default on all endpoints; opt out explicitly.
- Rate-limit public mutation endpoints.
- bcrypt or argon2 cost ≥ 10.
- No stack traces returned to clients.
- Verify resource ownership on every lookup (prevent IDOR).

## API
REST: `/api/{resource}/{id}/{sub}`. Verbs: GET / POST / PUT / PATCH / DELETE.
Success envelope: `{ "data": ..., "meta": ..., "error": null }`.
Error envelope: `{ "data": null, "error": { "code": "...", "message": "..." } }`.
Cursor pagination preferred for large sets.
Versioning: {{VERSIONING}}

## Git
Branch: `feat/REQ-F-NNN-slug` / `fix/REQ-F-NNN-slug` / `chore/description`.
Commit: `feat(scope): subject [REQ-F-NNN]`. PR title: `[REQ-F-NNN] {summary}`.
Squash merge to main.
