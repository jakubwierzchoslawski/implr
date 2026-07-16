---
domain: authentication
synthesised_at: 2026-01-01T00:00:00Z
synthesis_checksum: abc123de
---

# Domain Synthesis: Authentication

## Unified Business Rules
Consolidated rules for the login domain.

## Contradictions Detected
| ID | Fingerprint | FP-Ver | Statement A | Source A | Statement B | Source B | Type |
|----|-------------|--------|------------|---------|------------|---------|------|
| C-001 | 1:d5fe836f0aa838fd | 1 | Lockout after 3 failed attempts | login-spec.md §1 | Lockout after 5 failed attempts | login-spec.md §4 | Hard conflict |

## Cross-Domain Dependencies
- None

## NFR Candidates
- None

## Architecture-Relevant Files
- None
