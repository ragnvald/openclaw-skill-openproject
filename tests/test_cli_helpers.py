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

    def test_to_api_path(self) -> None:
        self.assertEqual(cli.to_api_path("/api/v3/work_packages/1"), "/work_packages/1")
        self.assertEqual(cli.to_api_path("https://example.org/api/v3/projects/8"), "/projects/8")
        self.assertEqual(cli.to_api_path("work_packages/1"), "/work_packages/1")

    def test_ensure_iso_date(self) -> None:
        self.assertEqual(cli.ensure_iso_date("2026-02-24", "--start-date"), "2026-02-24")
        with self.assertRaises(cli.OpenProjectError):
            cli.ensure_iso_date("24.02.2026", "--start-date")

    def test_extract_numeric_id_from_href(self) -> None:
        self.assertEqual(
            cli.extract_numeric_id_from_href("/api/v3/projects/42", "projects"),
            42,
        )
        self.assertIsNone(
            cli.extract_numeric_id_from_href("/api/v3/projects/demo-project", "projects")
        )

    def test_user_helpers(self) -> None:
        users = [
            {"id": 1, "name": "Alice Admin", "login": "alice"},
            {"id": 2, "firstName": "Bob", "lastName": "Builder", "login": "bob"},
        ]
        self.assertEqual(cli.user_display_name(users[0]), "Alice Admin")
        self.assertEqual(cli.user_display_name(users[1]), "Bob Builder")
        self.assertEqual(len(cli.filter_users(users, "bob")), 1)
        self.assertEqual(cli.filter_users(users, "3"), [])

    def test_wiki_helpers(self) -> None:
        self.assertEqual(cli.encode_wiki_title("Project Home"), "Project%20Home")

        wrapped = {"wiki_page": {"title": "Home", "text": "hello"}}
        self.assertEqual(cli.extract_legacy_wiki_page(wrapped)["title"], "Home")
        self.assertEqual(cli.extract_wiki_text({"text": {"raw": "abc"}}), "abc")
        self.assertEqual(cli.extract_wiki_text({"text": "def"}), "def")


if __name__ == "__main__":
    unittest.main()
