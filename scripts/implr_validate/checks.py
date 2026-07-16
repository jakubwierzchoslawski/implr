# scripts/implr_validate/checks.py
"""Validation checks. Standard library only."""
import os
import re

from .frontmatter import parse_frontmatter, FrontmatterError


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
    return findings
