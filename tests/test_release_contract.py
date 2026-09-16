"""Release workflow and artifact layout contract validation tests."""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestReleaseWorkflowContract(unittest.TestCase):
    def setUp(self):
        self.workflow_path = PROJECT_ROOT / ".github" / "workflows" / "release.yml"
        self.assertTrue(self.workflow_path.is_file(), "release.yml must exist")
        self.content = self.workflow_path.read_text(encoding="utf-8")

    def test_pypi_packages_dir_is_clean_dists(self):
        """Ensure PyPI publishing step points strictly to release-bundle/dists/."""
        self.assertIn("packages-dir: release-bundle/dists/", self.content)
        self.assertNotIn("packages-dir: dist/", self.content)
        self.assertNotIn("packages-dir: release-bundle/\n", self.content)

    def test_sha256sums_not_in_publish_directory(self):
        """Ensure SHA256SUMS is generated in release-bundle root, outside dists/."""
        self.assertIn("sha256sum * > ../SHA256SUMS", self.content)

    def test_provenance_attests_dists_only(self):
        """Ensure provenance subject-path only attests wheel and sdist distributions."""
        self.assertIn("release-bundle/dists/*.whl", self.content)
        self.assertIn("release-bundle/dists/*.tar.gz", self.content)
        # Verify SHA256SUMS is not inside the provenance job block
        prov_block = self.content.split("provenance:")[1].split("pypi-publish:")[0]
        self.assertNotIn("SHA256SUMS", prov_block)

    def test_github_release_includes_checksums(self):
        """Ensure GitHub Release uploads wheel, sdist, and SHA256SUMS."""
        self.assertIn("release-bundle/SHA256SUMS", self.content)


if __name__ == "__main__":
    unittest.main()
