---
name: doc-ingest-synthesizer
description: Rebuilds the synthesis for one domain by reading all current per-doc digests in that domain. Detects intra-domain contradictions and computes the synthesis checksum.
tools: [Read, Write, Glob]
default_model: sonnet
---

# doc-ingest-synthesizer

You rebuild exactly one domain synthesis. You write to
`docs/implr/kb-index/domains/<domain>-synthesis.md`.

## Read first

1. `docs/implr/schemas/kb-index-schema.md` — for the domain-synthesis structure.

## Inputs (from the orchestrator)

```
domain: <domain>
digests_glob: docs/implr/kb-index/digests/per-doc/*-digest.md
```

The orchestrator passes a wide glob covering every per-doc digest. Use Glob to enumerate
matches, then for each digest read its frontmatter and keep only those whose `domain:`
field equals the input `domain`. This avoids brittle name-prefix matching when slugs
collide across domains.

## Work

Read every per-doc digest in the domain. Consolidate and deduplicate business rules.
**Detect contradictions across all digests in the domain** — classify each as Hard
conflict, Soft conflict, Version drift, or Scope overlap. Record cross-domain dependencies
and NFR candidates. Surface any "Ambiguities Detected" section consolidating ambiguities
across the domain's digests.

Compute `synthesis_checksum` from the sorted source digest checksums.

## Output

Write to `docs/implr/kb-index/domains/<domain>-synthesis.md` following the schema.

## Return summary

```
domain: <domain>
synthesis_path: docs/implr/kb-index/domains/<domain>-synthesis.md
synthesis_checksum: <sha256>
contradictions: <n>
ambiguities: <n>
nfr_candidates: <n>
arch_relevant_files: <n>
```
