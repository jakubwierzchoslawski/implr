# Phase: domain

Dispatch prompt for `requirements-domain-worker`.

## Read first
- `docs/implr/schemas/requirement-schema.md`
- `docs/implr/config/implr.config.yaml`
- `docs/implr/config/DEV-STANDARDS.md`

## Your scope
```
domain: {{DOMAIN}}
synthesis_path: docs/implr/kb-index/domains/{{DOMAIN}}-synthesis.md
master_synthesis_path: docs/implr/kb-index/master-synthesis.md
cache_dir: docs/implr/kb-index/cache/
staging_dir: docs/implr/requirements/.staging/{{DOMAIN}}/
existing_reqs_index: docs/implr/requirements/requirements-index.md
mode: {{MODE}}                                # create | reprocess
reprocess_target: {{REPROCESS_TARGET}}        # only when mode=reprocess
```

## Task
Generate REQ files in the `staging_dir` path from scope, with slug-only filenames (no
IDs). Leave `req_id` empty — the orchestrator will fill it after all domain workers
return.

## Return summary
```
domain: {{DOMAIN}}
files_written:
  - <staging path> (type: functional | non-functional, complexity: <X>)
functional_count: <n>
non_functional_count: <n>
open_questions: <n>
contradictions_flagged: <n>
```
