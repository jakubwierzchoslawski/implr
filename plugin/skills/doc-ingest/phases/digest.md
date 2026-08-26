# Phase: digest

Dispatch prompt for `doc-ingest-digester`.

## Read first
- `docs/implr/schemas/kb-index-schema.md`
- `docs/implr/config/implr.config.yaml`

## Your scope
```
slug: {{SLUG}}
cache_path: {{CACHE_PATH}}
source_path: {{SOURCE_PATH}}
domain: {{DOMAIN}}
```

## Task
Read `{{CACHE_PATH}}` and produce a per-doc digest at
`docs/implr/kb-index/digests/per-doc/{{SLUG}}-digest.md` per the schema. Determine
`arch_relevant` per the rules in your system prompt.

## Return summary
```
slug: {{SLUG}}
digest_path: <path>
digest_checksum: <sha256>
arch_relevant: true | auto | false
ambiguities_count: <n>
contradiction_signals: <n>
```
