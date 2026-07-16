# KB Index Schema

Canonical structure for every artefact `doc-ingest` produces. All artefacts live under
`docs/implr/kb-index/`. This file is the authoritative reference — `doc-ingest` must produce
output matching these structures exactly so downstream skills can parse them reliably.

---

## 1. index.md — File Registry

Location: `docs/implr/kb-index/index.md`

A registry of every file discovered in the knowledge base. One YAML list entry per file.

```markdown
# KB Index

> Maintained by doc-ingest. Do not edit manually.
> Last updated: {ISO timestamp}
> Total files: {n} | Supported: {n} | Unsupported: {n}

## Files

```yaml
- filename: auth-flow.md
  original_path: docs/kb/auth/auth-flow.md
  cache_path: docs/implr/kb-index/cache/auth-flow.txt
  digest_path: docs/implr/kb-index/digests/per-doc/auth-flow-digest.md
  format: md                      # md | pdf | docx | xlsx | pptx | odp | odt | ods |
                                  # csv | txt | vtt | png | jpg | jpeg | gif | webp |
                                  # tiff | bmp | other
  format_supported: true
  checksum: abc123de              # md5 of the ORIGINAL file
  last_modified: 2025-01-15T10:32:00Z
  last_digested: 2025-01-15T10:35:00Z
  title: Authentication Flow
  doc_type: business-requirements # business-requirements | technical-spec | architecture |
                                  # data-model | integration | security | operations |
                                  # process-flow | glossary | standards | other
  domain: authentication          # derived from top-level kb subfolder, or "root"
  domains_referenced: [authentication, session-management]
  key_entities: [User, Session, Token, RefreshToken]
  arch_relevant: true             # true | false | auto
  arch_relevant_reason: "explicit tag: implr_tags includes architecture"
  has_contradictions: false
  word_count: 1240
```
```

### Field rules

- `checksum` is computed on the original file bytes. For binary formats (pdf, docx, xlsx) this
  detects content change reliably.
- `domain` is derived from the first subfolder under `docs/kb/`. A file at
  `docs/kb/auth/x.md` has domain `authentication` (folder name normalised). A file directly in
  `docs/kb/` has domain `root`.
- `arch_relevant` is `true` (explicit tag or in `architecture/` folder), `auto` (heuristic
  detection), or `false`.
- `format_supported: false` files are registered but not digested.

---

## 2. cache/{slug}.txt — Normalised Text Cache

Location: `docs/implr/kb-index/cache/{slug}.txt`

Plain-text extraction of each non-trivial source file. Created so digest logic is
format-agnostic — it always reads text. For `.md` and `.txt` the cache may be a direct copy.
For `.pdf`, `.docx`, `.xlsx`, `.csv` it is the extracted text representation.

No frontmatter. Plain text only. Overwritten whenever the source checksum changes.

---

## 3. digests/per-doc/{slug}-digest.md — Per-Document Digest

Location: `docs/implr/kb-index/digests/per-doc/{slug}-digest.md`

A complete, structured enumeration of one source document. Substitutes for reading the raw file
in all downstream cases. Completeness is the invariant — no item may be silently dropped.
Compression is the synthesis's job, not the digest's.

```markdown
---
source_file: docs/kb/auth/auth-flow.md
checksum: abc123de
digested_at: {ISO timestamp}
domain: authentication
doc_type: business-requirements
arch_relevant: true
---

# Digest: auth-flow.md

## Business Rules
1. {Tightly paraphrased rule}
2. {Tightly paraphrased rule}

## System Behaviours Required
- {Behaviour the system must exhibit}

## Data Entities
- EntityName: field, field, field

## Integration Points
- {External system}: {purpose}

## Non-Functional Signals
- {Signal} → {NFR category} NFR candidate

## Ambiguities Detected
- {Ambiguity, with note on what is unclear and where to look}

## Architecture Signals
- {Statement that is architecturally significant}
```

Length: as long as the source requires. One line per item — terse but complete. Never drop an
item to stay within a word budget. No prose narrative.
If a section has no content, write `- None`.

---

## 4. domains/{domain}-synthesis.md — Domain Synthesis

Location: `docs/implr/kb-index/domains/{domain}-synthesis.md`

A consolidated view across all documents in one domain (one top-level kb subfolder).
This is where intra-domain contradiction detection happens.

```markdown
---
domain: authentication
source_digests:
  - { file: auth-flow.md, checksum: abc123de }
  - { file: security-policy.md, checksum: def456gh }
synthesised_at: {ISO timestamp}
synthesis_checksum: {md5 of the concatenated source digest checksums}
---

# Domain Synthesis: Authentication

## Unified Business Rules
Consolidated, deduplicated rules across all docs in this domain.

## Contradictions Detected
| ID | Fingerprint | FP-Ver | Statement A | Source A | Statement B | Source B | Type |
|----|-------------|--------|------------|---------|------------|---------|------|
| C-001 | 1:a1b2c3d4e5f6a7b8 | 1 | Session timeout 15 min | security-policy.md §3 | Session timeout 30 min | auth-flow.md §2 | Hard conflict |

Type is one of: Hard conflict | Soft conflict | Version drift | Scope overlap.
If none: write `None detected.`

`Fingerprint`/`FP-Ver` are the stable identity of the contradiction (see § Contradiction
Fingerprint below); `C-xxx` is a display label only. The synthesizer records the five raw
fields per row and the orchestrator computes the hash — see that section.

## Cross-Domain Dependencies
- Depends on: {domain} ({reason})
- Referenced by: {domain} ({reason})

## NFR Candidates
- {category}: {signal} (seen in {n} docs)

## Architecture-Relevant Files
- {filename} ({explicit|auto})
```

### synthesis_checksum
Computed from the sorted list of source digest checksums. If a source digest changes, this
checksum changes, signalling the synthesis is stale and must be rebuilt. This is the incremental
gate for domain syntheses.

---

## 5. master-synthesis.md — System-Wide Synthesis

Location: `docs/implr/kb-index/master-synthesis.md`

The primary input for `ba-requirements-gen` and `arch-gen`. A bounded, system-wide view that
fits comfortably in a context window regardless of KB size.

```markdown
---
domains_included: [authentication, billing, user-management]
synthesised_at: {ISO timestamp}
kb_total_files: 24
master_checksum: {md5 of sorted domain synthesis_checksums}
---

# Master Synthesis

## System Overview
2–3 paragraph system-wide narrative derived from all domain syntheses.

## Domain Map
| Domain | Files | Key Entities | Contradictions | NFR Signals | Arch Files |
|--------|-------|-------------|---------------|-------------|-----------|
| authentication | 3 | User, Session, Token | 1 | Performance, Compliance | 2 |

## Cross-Domain Contradictions
| ID | Fingerprint | FP-Ver | Description | Domain A | Source A | Domain B | Source B | Type |
|----|-------------|--------|-------------|---------|---------|---------|---------|------|

If none: `None detected.`

## Global NFR Candidates
| Category | Frequency | Domains |
|----------|-----------|---------|
| Performance | 4 | auth, billing, search |

## Architecture-Relevant Files
Complete list across the KB, with explicit/auto marker and domain.

## Open Ambiguities
Unresolved items requiring human input, with source references.
```

---

## 6. digest-log.md — Execution Log

Location: `docs/implr/kb-index/digest-log.md`

Append newest-first. Each entry records one doc-ingest run.

```markdown
# doc-ingest Log

<!-- newest first -->

## Run {n} — {ISO timestamp}

```yaml
run_at: {ISO timestamp}
trigger: manual | chained
mode: default | file | dry-run | no-digest
files_processed:
  - path: docs/kb/auth/auth-flow.md
    checksum: abc123de
    action: new | changed | unchanged | removed | unsupported
    digest_written: true
domains_rebuilt: [authentication]
master_synthesis_rebuilt: true
contradictions_detected:
  - id: C-001
    type: hard-conflict
    domain: authentication
    source_a: auth-flow.md
    source_b: security-policy.md
    summary: "Session timeout 15 min vs 30 min"
warnings:
  - "billing-report.xlsx: unsupported sheet structure, registered without digest"
```
```

The `checksum` and `action` per file is what subsequent runs compare against to decide what to
reprocess.

---

## 7. requirements/resolved-contradictions.md — Contradiction Resolution Log

Location: `docs/implr/requirements/resolved-contradictions.md`

Records human decisions on every C-xxx contradiction detected during synthesis. Consumed by
`ba-requirements-gen` Phase 0 and passed to `requirements-domain-worker` subagents. The file
is append-only — re-running `ba-requirements-gen` adds new rows but never overwrites existing
ones. To change a decision, edit the file manually and re-run `/ba-requirements-gen`.

```markdown
# Resolved Contradictions
> Maintained by ba-requirements-gen. To change a decision, edit this file and re-run `/ba-requirements-gen`.

## Resolved
| C-ID  | Fingerprint          | FP-Ver | Type          | Source A                | Source B                | Problem                          | Decision                      | Resolved   |
|-------|----------------------|--------|---------------|-------------------------|-------------------------|----------------------------------|-------------------------------|------------|
| C-001 | 1:a1b2c3d4e5f6a7b8   | 1      | Hard conflict | docs/kb/spec-v1.md §3.2 | docs/kb/spec-v2.md §1.4 | Auth token TTL: 15 min vs 30 min | Use 30-minute auth token TTL  | 2026-05-31 |

## Deferred
| C-ID  | Fingerprint          | FP-Ver | Type          | Source A            | Source B            | Problem                         | Notes                     | Deferred   |
|-------|----------------------|--------|---------------|---------------------|---------------------|---------------------------------|---------------------------|------------|
| C-003 | 1:9f8e7d6c5b4a3928   | 1      | Scope overlap | docs/kb/roadmap.md  | docs/kb/mvp.md      | Feature X: in MVP scope or not? | Needs product owner input | 2026-05-31 |
```

### Column definitions

**Resolved table**

| Column | Source | Notes |
|--------|--------|-------|
| C-ID | domain/master synthesis | Display label only, assigned at synthesis time; NOT used for matching |
| Fingerprint | computed via `scripts/implr_validate --fingerprint` | Stable identity used to match against this file |
| FP-Ver | fingerprint algorithm version | Bumped when the algorithm changes |
| Type | synthesis Contradictions Detected | Hard conflict / Soft conflict / Version drift / Scope overlap |
| Source A | synthesis | File path + section if available |
| Source B | synthesis | File path + section if available |
| Problem | synthesis contradiction description | Short summary copied verbatim |
| Decision | user input during Phase 0 | Authoritative; passed to workers |
| Resolved | ISO date Phase 0 ran | |

**Deferred table**

Same columns except `Decision` → `Notes` (user's deferral reason) and `Resolved` → `Deferred`.

### Idempotency

`ba-requirements-gen` Phase 0 skips any contradiction whose `(fingerprint_version,
fingerprint)` is already present in either table. Only contradictions with a new fingerprint
trigger prompts; `C-xxx` is a display label and is not used for matching. File is never
truncated or overwritten — only appended.

### Contradiction Fingerprint (stable identity)

Every contradiction row carries a `fingerprint` and `fingerprint_version`. The fingerprint is
the stable identity used to match against `resolved-contradictions.md` — `C-xxx` IDs are display
labels only and are NOT used for matching.

Algorithm (version 1), implemented canonically in `scripts/implr_validate/fingerprint.py`:

1. Normalize every field: trim, collapse internal whitespace, lowercase, strip trailing
   `.,;:!?`.
2. Build the two sides `{source, statement}` for A and B and **sort them** (so swapping A/B does
   not change the identity).
3. Serialize `{version, type, sides}` as canonical JSON (sorted keys, no insignificant
   whitespace).
4. `fingerprint = "1:" + sha256(canonical)[:16]`.

The `Fingerprint` column stores the full `<version>:<hash>` string; `FP-Ver` repeats the
version for human readers.

An LLM must NOT hand-compute this hash. The `doc-ingest` orchestrator computes it by writing the
five fields to a temp JSON file and calling
`python scripts/implr_validate --fingerprint <file>`. `implr-validate --workspace` recomputes
each fingerprint stored in a domain synthesis `Contradictions Detected` table (the only surface
that carries all five raw fields) from its cells and fails on any mismatch — so a hand-written
or hallucinated hash is caught. The master `Cross-Domain Contradictions` and
`resolved-contradictions.md` tables carry copies of the synthesis fingerprint and are not
independently recomputable. To change the algorithm, bump `fingerprint_version`.
