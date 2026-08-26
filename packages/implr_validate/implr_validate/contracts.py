# packages/implr_validate/implr_validate/contracts.py
"""Load the JSON contract files (standard library only)."""
import json
import os


class Contracts(object):
    def __init__(self, vocab, rules):
        self.machines = vocab["machines"]
        self.artefact_types = rules["artefact_types"]
        self.schema_machine_map = rules["schema_machine_map"]
        self.repo_prose_checks = rules["repo_prose_checks"]

    def states_for(self, machine):
        return set(self.machines[machine]["states"])


def load_contracts(schema_dir):
    with open(os.path.join(schema_dir, "status-vocabulary.json"), encoding="utf-8") as f:
        vocab = json.load(f)
    with open(os.path.join(schema_dir, "frontmatter-rules.json"), encoding="utf-8") as f:
        rules = json.load(f)
    return Contracts(vocab, rules)
