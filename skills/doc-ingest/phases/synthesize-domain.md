# Phase: synthesize-domain

Dispatch prompt for `doc-ingest-synthesizer`.

## Read first
- `docs/implr/schemas/kb-index-schema.md`

## Your scope
```
domain: {{DOMAIN}}
digests_glob: docs/implr/kb-index/digests/per-doc/*-digest.md
```

(The glob includes all per-doc digests; filter by reading each digest's `domain:` field
in frontmatter and keeping only those matching `{{DOMAIN}}`.)

## Task
Rebuild `docs/implr/kb-index/domains/{{DOMAIN}}-synthesis.md`. Detect intra-domain
contradictions, consolidate rules, surface ambiguities. Compute `synthesis_checksum`.

## Return summary
```
domain: {{DOMAIN}}
synthesis_path: <path>
synthesis_checksum: <sha256>
contradictions: <n>
ambiguities: <n>
nfr_candidates: <n>
arch_relevant_files: <n>
```
