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
