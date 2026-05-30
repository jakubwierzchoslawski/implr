# Phase: draft

Dispatch prompt for `arch-drafter`.

## Read first
- `docs/implr/kb-index/master-synthesis.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Your scope
```
mode: {{MODE}}              # create | update
existing_path: {{EXISTING_PATH}}   # only when mode=update; else omit
confirmed_decisions:
{{DECISIONS_BLOCK}}
```

## Task
Produce a complete `docs/ARCHITECTURE.md` per the rules in your system prompt. Treat
confirmed decisions as authoritative.

## Return summary
```
arch_path: docs/ARCHITECTURE.md
mode: {{MODE}}
sections_written: <n>
decisions_applied: <n>
traceability_entries: <n>
```
