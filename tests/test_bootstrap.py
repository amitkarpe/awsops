from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BootstrapContractTests(unittest.TestCase):
    def test_required_control_files_exist(self):
        for name in ("AGENTS.md", "CONTEXT.md", "SPEC.md", "ROADMAP.md", "docs/architecture/MIGRATION.md"):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_clean_layers_exist(self):
        for name in ("domain", "aws", "controls", "approval", "execution", "runtime"):
            self.assertTrue((ROOT / "src" / "awsops" / name / "__init__.py").is_file(), name)

    def test_legacy_catch_all_not_present(self):
        self.assertFalse((ROOT / "pilot_v1").exists())
        self.assertFalse((ROOT / "experiments").exists())

    def test_current_docs_do_not_claim_old_repo_as_product(self):
        context = (ROOT / "CONTEXT.md").read_text()
        spec = (ROOT / "SPEC.md").read_text()
        self.assertIn("amitkarpe/awsops", context)
        self.assertIn("reference/archive", context)
        self.assertNotIn("pilot_v1", spec)


if __name__ == "__main__":
    unittest.main()
