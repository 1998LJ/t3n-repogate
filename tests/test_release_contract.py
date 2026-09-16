"""Release workflow and artifact layout contract validation tests."""

import unittest
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestReleaseWorkflowContract(unittest.TestCase):
    def setUp(self):
        self.workflow_path = PROJECT_ROOT / ".github" / "workflows" / "release.yml"
        self.assertTrue(self.workflow_path.is_file(), "release.yml must exist")
        with open(self.workflow_path, "r", encoding="utf-8") as f:
            self.workflow = yaml.safe_load(f)

    def test_pypi_packages_dir_does_not_contain_sha256sums(self):
        """Ensure PyPI publishing job does not look in the directory containing SHA256SUMS."""
        jobs = self.workflow.get("jobs", {})
        pypi_job = jobs.get("pypi-publish", {})
        steps = pypi_job.get("steps", [])

        # Find pypa/gh-action-pypi-publish step
        publish_step = None
        for step in steps:
            uses = step.get("uses", "")
            if "pypa/gh-action-pypi-publish" in uses:
                publish_step = step
                break

        self.assertIsNotNone(publish_step, "pypi-publish job must use pypa/gh-action-pypi-publish")
        with_args = publish_step.get("with", {})
        packages_dir = with_args.get("packages-dir", "")

        # packages-dir must be explicitly pointed to dists/ subfolder, not root bundle
        self.assertEqual(packages_dir, "release-bundle/dists/")
        self.assertNotIn("SHA256SUMS", packages_dir)

    def test_release_build_uploads_release_bundle(self):
        """Ensure release-build uploads the release-bundle artifact."""
        jobs = self.workflow.get("jobs", {})
        build_job = jobs.get("release-build", {})
        steps = build_job.get("steps", [])

        upload_step = None
        for step in steps:
            uses = step.get("uses", "")
            if "actions/upload-artifact" in uses:
                upload_step = step
                break

        self.assertIsNotNone(upload_step, "release-build must upload artifact")
        with_args = upload_step.get("with", {})
        self.assertEqual(with_args.get("name"), "release-bundle")
        self.assertEqual(with_args.get("path"), "release-bundle/")

    def test_provenance_attests_dists_only(self):
        """Ensure provenance job attests wheels and sdists, not SHA256SUMS."""
        jobs = self.workflow.get("jobs", {})
        prov_job = jobs.get("provenance", {})
        steps = prov_job.get("steps", [])

        attest_step = None
        for step in steps:
            uses = step.get("uses", "")
            if "actions/attest" in uses:
                attest_step = step
                break

        self.assertIsNotNone(attest_step, "provenance job must use actions/attest")
        with_args = attest_step.get("with", {})
        subject_path = with_args.get("subject-path", "")
        self.assertIn("release-bundle/dists/*.whl", subject_path)
        self.assertIn("release-bundle/dists/*.tar.gz", subject_path)
        self.assertNotIn("SHA256SUMS", subject_path)


if __name__ == "__main__":
    unittest.main()
