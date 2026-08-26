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
contradictions_for_fingerprinting:
  - c_id: C-001
    source_a: <source A>
    statement_a: <statement A>
    source_b: <source B>
    statement_b: <statement B>
    type: <Hard conflict | Soft conflict | Version drift | Scope overlap>
```

Emit one `contradictions_for_fingerprinting` entry per detected contradiction with its five
raw fields. **Do not compute the fingerprint hash yourself** — the orchestrator computes it
via `implr-validate --fingerprint` and writes it into the synthesis table.
