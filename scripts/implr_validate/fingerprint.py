# scripts/implr_validate/fingerprint.py
"""Deterministic, versioned, order-independent contradiction fingerprint.
An LLM cannot compute SHA-256 reliably; this is the canonical implementation that
doc-ingest invokes (via `python scripts/implr_validate --fingerprint`) and that
`--workspace` validation recomputes to verify stored fingerprints."""
import hashlib
import json
import re

FINGERPRINT_VERSION = 1


def _normalize(value):
    s = str(value).strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:!?")
    return s


def contradiction_fingerprint(fields):
    for k in ("source_a", "statement_a", "source_b", "statement_b", "type"):
        if k not in fields:
            raise KeyError("missing fingerprint field: %s" % k)
    sides = sorted(
        [
            {"source": _normalize(fields["source_a"]), "statement": _normalize(fields["statement_a"])},
            {"source": _normalize(fields["source_b"]), "statement": _normalize(fields["statement_b"])},
        ],
        key=lambda d: (d["source"], d["statement"]),
    )
    payload = {"version": FINGERPRINT_VERSION, "type": _normalize(fields["type"]), "sides": sides}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return "%d:%s" % (FINGERPRINT_VERSION, digest[:16])


TASK_FINGERPRINT_VERSION = 1

_TASK_FIELDS = [
    "task_body", "ac_ids", "ac_text", "files", "tests_first",
    "requirement_updated_at", "arch_excerpt_hash", "interfaces_contracts",
    "applied_nfrs", "standards_card_hash", "test_runner",
]
_TASK_LIST_FIELDS = {"ac_ids", "ac_text", "files", "tests_first"}
_TASK_PASSTHROUGH = {"arch_excerpt_hash", "standards_card_hash"}


def task_fingerprint(fields):
    for k in _TASK_FIELDS:
        if k not in fields:
            raise KeyError("missing task fingerprint field: %s" % k)
    payload = {"version": TASK_FINGERPRINT_VERSION}
    for k in _TASK_FIELDS:
        v = fields[k]
        if k in _TASK_LIST_FIELDS:
            payload[k] = sorted(_normalize(item) for item in v)
        elif k in _TASK_PASSTHROUGH:
            payload[k] = str(v)
        else:
            payload[k] = _normalize(v)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return "t%d:%s" % (TASK_FINGERPRINT_VERSION, digest[:16])
