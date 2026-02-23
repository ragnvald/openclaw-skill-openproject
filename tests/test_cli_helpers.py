"""Unit tests for helper functions in scripts/openproject_cli.py."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_cli_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "scripts" / "openproject_cli.py"
    spec = importlib.util.spec_from_file_location("openproject_cli", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load scripts/openproject_cli.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = load_cli_module()


class HelperTests(unittest.TestCase):
    def test_slugify(self) -> None:
        self.assertEqual(cli.slugify("Use OpenProject as PM source of truth"), "use-openproject-as-pm-source-of-truth")
        self.assertEqual(cli.slugify("***"), "decision")

    def test_status_bucket(self) -> None:
        self.assertEqual(cli.status_bucket("Closed"), "completed")
        self.assertEqual(cli.status_bucket("In progress"), "in_progress")
        self.assertEqual(cli.status_bucket("On hold / blocker"), "blockers")

    def test_build_decision_markdown(self) -> None:
        content = cli.build_decision_markdown(
            date_text="2026-02-23",
            project="know-malawi",
            title="Adopt CLI",
            decision="Proceed with alpha",
            context="Current flow is manual",
            impact="Faster updates",
            followup="Review after sprint",
        )
        self.assertIn("# Decision: Adopt CLI", content)
        self.assertIn("Project: know-malawi", content)
        self.assertIn("## Follow-up", content)

    def test_write_text_file_and_unique_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "decision.md"
            cli.write_text_file(base, "first")
            next_path = cli.unique_path(base)
            self.assertNotEqual(base, next_path)
            self.assertEqual(next_path.name, "decision-2.md")


if __name__ == "__main__":
    unittest.main()
