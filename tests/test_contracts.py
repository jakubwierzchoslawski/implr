# tests/test_contracts.py
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from implr_validate.contracts import load_contracts

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "scaffold", "schemas")


class TestContracts(unittest.TestCase):
    def setUp(self):
        self.c = load_contracts(SCHEMA_DIR)

    def test_plan_states(self):
        self.assertEqual(
            self.c.states_for("plan"),
            {"ready", "in-progress", "done", "blocked", "needs-rework"},
        )

    def test_requirement_type_has_status_machine(self):
        self.assertEqual(self.c.artefact_types["requirement"]["status_machine"], "requirement")

    def test_banned_tokens_present(self):
        tokens = {b["token"] for b in self.c.repo_prose_checks["banned_tokens"]}
        self.assertIn("replan_required", tokens)
        self.assertIn("impact-analysed", tokens)


if __name__ == "__main__":
    unittest.main()
