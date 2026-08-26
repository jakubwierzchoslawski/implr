# packages/implr_validate/implr_validate/checks.py
"""Validation checks. Standard library only."""
import json
import os
import re

from .frontmatter import parse_frontmatter, FrontmatterError
from .fingerprint import contradiction_fingerprint


class Finding(object):
    def __init__(self, level, path, message):
        self.level = level
        self.path = path
        self.message = message

    def __repr__(self):
        return "%s: %s: %s" % (self.level, self.path, self.message)

    def __eq__(self, other):
        return (self.level, self.path, self.message) == (other.level, other.path, other.message)


def check_artefact_file(path, atype, contracts):
    spec = contracts.artefact_types[atype]
    findings = []
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        fm = parse_frontmatter(text)
    except FrontmatterError as e:
        return [Finding("error", path, "frontmatter parse error: %s" % e)]
    for field in spec["required"]:
        if field not in fm or fm[field] == "":
            findings.append(Finding("error", path, "missing required field: %s" % field))
    idf = spec["id_field"]
    if idf in fm and not re.match(spec["id_pattern"], str(fm[idf])):
        findings.append(Finding("error", path, "%s %r does not match %s" % (idf, fm[idf], spec["id_pattern"])))
    if "status" in fm and fm["status"] != "":
        legal = contracts.states_for(spec["status_machine"])
        if fm["status"] not in legal:
            findings.append(Finding("error", path, "illegal status %r (legal: %s)" % (fm["status"], sorted(legal))))
    for rule in spec.get("conditional_required", []):
        if fm.get("status") == rule["when_status"]:
            for req_field in rule["require"]:
                if req_field not in fm or fm[req_field] == "":
                    findings.append(Finding("error", path, "status %s requires field %s" % (rule["when_status"], req_field)))
    return findings


# --- Task 7: workspace discovery + cross-reference + index agreement ---
import glob


def _frontmatter_or_none(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return parse_frontmatter(text)
    except FrontmatterError:
        return None


def check_workspace(root, contracts):
    findings = []
    ids_by_type = {}          # atype -> set of ids found on disk
    plans = []                # (path, fm)
    requirements = []         # (path, fm)
    crs = []                  # (path, fm)
    for atype, spec in contracts.artefact_types.items():
        found = set()
        for pattern in spec["path_globs"]:
            for path in glob.glob(os.path.join(root, pattern.replace("/", os.sep))):
                findings.extend(check_artefact_file(path, atype, contracts))
                fm = _frontmatter_or_none(path)
                if fm is None:
                    continue
                idv = fm.get(spec["id_field"], "")
                if idv:
                    found.add(idv)
                if atype == "plan":
                    plans.append((path, fm))
                if atype == "requirement":
                    requirements.append((path, fm))
                if atype == "cr":
                    crs.append((path, fm))
        ids_by_type[atype] = found

    req_ids = ids_by_type.get("requirement", set())

    # (a)/(b) plan linkage + numbering
    for path, fm in plans:
        linked = fm.get("linked_requirement", "")
        if linked and linked not in req_ids:
            findings.append(Finding("error", path, "linked_requirement %s does not exist" % linked))
        pid = fm.get("plan_id", "")
        if linked and pid[-3:].isdigit() and linked[-3:].isdigit() and pid[-3:] != linked[-3:]:
            findings.append(Finding("error", path, "plan %s number does not match linked %s" % (pid, linked)))

    # (c) superseded_by resolution
    for path, fm in requirements:
        sb = fm.get("superseded_by", "")
        if sb and sb not in req_ids:
            findings.append(Finding("error", path, "superseded_by %s does not exist" % sb))

    # CR targets resolve to existing requirements
    for path, fm in crs:
        for tgt in fm.get("targets", []) or []:
            if tgt not in req_ids:
                findings.append(Finding("error", path, "CR target %s does not exist" % tgt))

    # (d) index agreement
    for atype, spec in contracts.artefact_types.items():
        index_rel = spec.get("index_file")
        if not index_rel:
            continue
        index_path = os.path.join(root, index_rel.replace("/", os.sep))
        if not os.path.isfile(index_path):
            if ids_by_type.get(atype):
                findings.append(Finding("error", index_rel, "index file missing but %d %s artefact(s) exist" % (len(ids_by_type[atype]), atype)))
            continue
        with open(index_path, encoding="utf-8") as f:
            index_text = f.read()
        indexed = set(re.findall(spec["id_pattern"].strip("^$"), index_text))
        disk = ids_by_type.get(atype, set())
        for missing in sorted(disk - indexed):
            findings.append(Finding("error", index_rel, "%s exists on disk but is not in the index" % missing))
        for phantom in sorted(indexed - disk):
            findings.append(Finding("error", index_rel, "%s is in the index but has no file" % phantom))

    # (e) contradiction fingerprint verification — recompute stored fingerprints in the
    # domain-synthesis "Contradictions Detected" and master "Cross-Domain Contradictions"
    # tables (both carry the five raw fields as named columns). This is what makes the
    # "LLM-can't-hash" guarantee real: a hand-written or hallucinated hash no longer passes.
    findings.extend(_check_synthesis_fingerprints(root))
    return findings


_CONTRA_REQUIRED_COLS = ("Fingerprint", "FP-Ver", "Statement A", "Source A", "Statement B", "Source B", "Type")


def _parse_md_table(lines, header_idx):
    """Return (colmap, data_rows) for the pipe table whose header is lines[header_idx].
    colmap maps column name -> index; separator rows (|---|) are skipped."""
    header = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    colmap = {name: i for i, name in enumerate(header)}
    rows = []
    j = header_idx + 1
    while j < len(lines):
        ln = lines[j].strip()
        if not ln.startswith("|"):
            break
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):  # separator row
            j += 1
            continue
        rows.append(cells)
        j += 1
    return colmap, rows


def _check_synthesis_fingerprints(root):
    findings = []
    kb = os.path.join(root, "docs", "implr", "kb-index")
    paths = glob.glob(os.path.join(kb, "domains", "*-synthesis.md"))
    master = os.path.join(kb, "master-synthesis.md")
    if os.path.isfile(master):
        paths.append(master)
    for path in paths:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        for i, ln in enumerate(lines):
            s = ln.strip()
            if not (s.startswith("|") and "Fingerprint" in s and "Statement A" in s):
                continue
            colmap, rows = _parse_md_table(lines, i)
            if not all(c in colmap for c in _CONTRA_REQUIRED_COLS):
                continue
            for cells in rows:
                if max(colmap.values()) >= len(cells):
                    continue  # malformed / short row
                stored_fp = cells[colmap["Fingerprint"]]
                stored_ver = cells[colmap["FP-Ver"]]
                if not stored_fp:
                    continue
                fields = {
                    "source_a": cells[colmap["Source A"]],
                    "statement_a": cells[colmap["Statement A"]],
                    "source_b": cells[colmap["Source B"]],
                    "statement_b": cells[colmap["Statement B"]],
                    "type": cells[colmap["Type"]],
                }
                expected = contradiction_fingerprint(fields)
                if stored_fp != expected:
                    findings.append(Finding("error", rel, "contradiction fingerprint %r does not match recomputed %r" % (stored_fp, expected)))
                    continue
                expected_ver = expected.split(":", 1)[0]
                if stored_ver != expected_ver:
                    findings.append(Finding("error", rel, "contradiction FP-Ver %r does not match fingerprint version %r" % (stored_ver, expected_ver)))
    return findings


# --- Task 8: repo prose checks (banned tokens, divergent enums, cache/format drift) ---
ENUM_COMMENT_RE = re.compile(r"status:\s*[\w-]+\s*#\s*([\w-]+(?:\s*\|\s*[\w-]+)+)")


def _is_exempt(rel, exempt_prefixes):
    rel = rel.replace(os.sep, "/")
    return any(rel == p or rel.startswith(p) for p in exempt_prefixes)


CACHE_MD_RE = re.compile(r"cache/\{slug\}\.md|cache/[\w-]+\.md|cache_path:\s*\S+\.md")
FORMATS_RE = re.compile(r"kb_supported_formats:\s*\[([^\]]*)\]")
# `changes-required` used as a plan lifecycle transition (misuse), not the review verdict noun
TRANSITION_MISUSE_RE_TMPL = r"(?:->|-->|→|—>)\s*%s|%s\s*(?:->|-->|→|—>)"


def _matches_surface(rel, surfaces):
    return any(rel == s or rel.startswith(s) for s in surfaces)


def check_repo_prose(root, contracts):
    cfg = contracts.repo_prose_checks
    findings = []
    banned = cfg["banned_tokens"]
    exempt = cfg["exempt_paths"]
    banned_surfaces = cfg["banned_token_surfaces"]
    enum_surfaces = cfg["enum_comment_surfaces"]
    enum_exempt = cfg["enum_check_exempt"]
    cache_surfaces = cfg["cache_path_surfaces"]
    misuse_tokens = cfg.get("plan_status_misuse_tokens", [])
    canonical = list(cfg["canonical_formats"])
    machine_map = contracts.schema_machine_map

    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".md"):
                continue
            abspath = os.path.join(dirpath, name)
            rel = os.path.relpath(abspath, root).replace(os.sep, "/")
            with open(abspath, encoding="utf-8") as f:
                text = f.read()

            # (a) retired tokens — broad surface (README/WORKFLOW/skills/agents/scaffold)
            if _matches_surface(rel, banned_surfaces) and not _is_exempt(rel, exempt):
                for b in banned:
                    if b["token"] in text:
                        findings.append(Finding("error", rel, "banned token %r (%s)" % (b["token"], b["reason"])))
                # (a2) transition-context misuse of an otherwise-legal token
                for tok in misuse_tokens:
                    pat = TRANSITION_MISUSE_RE_TMPL % (re.escape(tok), re.escape(tok))
                    if re.search(pat, text):
                        findings.append(Finding("error", rel, "%r used as a plan-lifecycle transition; it is a review status, not a plan status" % tok))

            # (b) divergent enum comments — narrow surface (schemas/templates)
            if name in machine_map and _matches_surface(rel, enum_surfaces) and not _is_exempt(rel, enum_exempt):
                legal = contracts.states_for(machine_map[name])
                for m in ENUM_COMMENT_RE.finditer(text):
                    for v in [x.strip() for x in m.group(1).split("|")]:
                        if v not in legal:
                            findings.append(Finding("error", rel, "enum comment lists %r, illegal for %s machine" % (v, machine_map[name])))

            # (c) cache-path drift — the retired .md cache extension
            if _matches_surface(rel, cache_surfaces) and CACHE_MD_RE.search(text):
                findings.append(Finding("error", rel, "cache path uses retired .md extension; cache files are cache/{slug}.txt"))

    # (d) format-list drift — EVERY kb_supported_formats array anywhere must equal canonical
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not (name.endswith(".md") or name.endswith(".yaml") or name.endswith(".yml")):
                continue
            abspath = os.path.join(dirpath, name)
            rel = os.path.relpath(abspath, root).replace(os.sep, "/")
            if _is_exempt(rel, exempt):
                continue
            with open(abspath, encoding="utf-8") as f:
                for m in FORMATS_RE.finditer(f.read()):
                    listed = [x.strip() for x in m.group(1).split(",") if x.strip()]
                    if listed != canonical:
                        findings.append(Finding("error", rel, "kb_supported_formats %s != canonical %s" % (listed, canonical)))

    # (e) format presence — every canonical format must appear on each presence surface
    for rel in cfg.get("format_presence_surfaces", []):
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            text = f.read()
        for fmt in canonical:
            if not re.search(r"\b%s\b" % re.escape(fmt), text):
                findings.append(Finding("error", rel, "canonical format %r not mentioned on this surface" % fmt))
    return findings


# --- step registry (implr Studio) ---

_REGISTRY_PHASES = ("discovery", "design", "requirements", "planning", "build", "verify")
_REGISTRY_KINDS = ("skill", "agent")
_REGISTRY_FIELDS = (
    "id", "kind", "label", "phase", "skill",
    "args_allowed", "args_default", "interactive",
    "agents", "consumes", "produces", "produces_artefact", "description",
)


def check_step_registry(root, contracts):
    """Validate plugin/schemas/step-registry.json against the plugin payload.

    A registered step whose skill does not exist yet is reported at level "info",
    never "error": designing a pipeline ahead of implementing its steps is the
    workflow the registry exists to support. Everything else - a malformed arg
    spec, an agent with no definition, an unknown artefact type - is an error,
    because each one produces a UI control that configures nothing.

    Deliberately re-implements the loader's rules rather than importing
    implr_studio: implr-validate must keep working in a project that has never
    installed the studio backend, and stays standard library only.
    """
    rel = os.path.join("plugin", "schemas", "step-registry.json")
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return []

    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except ValueError as e:
        return [Finding("error", rel, "invalid JSON: %s" % e)]

    findings = []
    seen = set()
    for entry in raw.get("steps", []):
        step_id = entry.get("id", "<no id>")

        missing = [f for f in _REGISTRY_FIELDS if f not in entry]
        if missing:
            findings.append(Finding(
                "error", rel,
                "step %s missing required field(s): %s" % (step_id, ", ".join(missing))))
            continue

        if step_id in seen:
            findings.append(Finding("error", rel, "duplicate step id: %s" % step_id))
            continue
        seen.add(step_id)

        if entry["kind"] not in _REGISTRY_KINDS:
            findings.append(Finding(
                "error", rel,
                "step %s has unknown kind %r (legal: %s)"
                % (step_id, entry["kind"], list(_REGISTRY_KINDS))))

        if entry["phase"] not in _REGISTRY_PHASES:
            findings.append(Finding(
                "error", rel,
                "step %s has unknown phase %r (legal: %s)"
                % (step_id, entry["phase"], list(_REGISTRY_PHASES))))

        specs = {}
        for spec in entry["args_allowed"]:
            if not isinstance(spec, dict) or "flag" not in spec:
                findings.append(Finding(
                    "error", rel,
                    "step %s args_allowed entries must be objects with a 'flag'" % step_id))
                continue
            if spec["flag"] in specs:
                findings.append(Finding(
                    "error", rel,
                    "step %s has duplicate flag %r in args_allowed" % (step_id, spec["flag"])))
                continue
            specs[spec["flag"]] = spec
            if spec.get("takes_value"):
                pattern = spec.get("value_pattern")
                if not pattern:
                    findings.append(Finding(
                        "error", rel,
                        "step %s arg %r takes a value but has no value_pattern"
                        % (step_id, spec["flag"])))
                else:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        findings.append(Finding(
                            "error", rel,
                            "step %s arg %r has an invalid value_pattern: %s"
                            % (step_id, spec["flag"], e)))

        for arg in entry["args_default"]:
            spec = specs.get(arg)
            if spec is None:
                findings.append(Finding(
                    "error", rel,
                    "step %s args_default entry %r is not in args_allowed" % (step_id, arg)))
            elif spec.get("takes_value"):
                findings.append(Finding(
                    "error", rel,
                    "step %s args_default entry %r takes a value, so it cannot be a default"
                    % (step_id, arg)))

        for agent in entry["agents"]:
            name = agent.get("name") if isinstance(agent, dict) else None
            if not name:
                findings.append(Finding(
                    "error", rel, "step %s has an agent entry with no name" % step_id))
                continue
            if not os.path.isfile(
                    os.path.join(root, "plugin", "agents", "%s.md" % name)):
                findings.append(Finding(
                    "error", rel,
                    "step %s dispatches agent %r, which has no plugin/agents/%s.md"
                    % (step_id, name, name)))

        artefact = entry["produces_artefact"]
        if artefact is not None and artefact not in contracts.artefact_types:
            findings.append(Finding(
                "error", rel,
                "step %s produces_artefact %r is not a known artefact type (known: %s)"
                % (step_id, artefact, sorted(contracts.artefact_types))))

        if not os.path.isfile(
                os.path.join(root, "plugin", "skills", entry["skill"], "SKILL.md")):
            findings.append(Finding(
                "info", rel,
                "step %s is planned: plugin/skills/%s/SKILL.md does not exist yet"
                % (step_id, entry["skill"])))

    return findings
