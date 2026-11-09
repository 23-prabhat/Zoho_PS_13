"""Check publication boundaries with temporary files and a simulated Git index."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import check_public_files
import package_submission


class ReleaseBoundaryTests(unittest.TestCase):
    def test_local_keys_and_runtime_artifacts_are_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ("README.md","src/main.cpp","scripts/.env","guides/private.pem","guides/secret.key","guides/PRIVATE.PEM","configs/credentials",
                         ".aws/credentials","models/qwen2.5-1.5b/int4/model.bin","output/report.pdf","build/shikai"):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text("fixture")
            selected=package_submission.source_files(root)
            self.assertEqual(set(selected),{"README.md","src/main.cpp"})

    def test_root_source_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"private.txt").write_text("local data")
            (root/"README.md").symlink_to(root/"private.txt")
            self.assertNotIn("README.md",package_submission.source_files(root))

    def test_already_tracked_ignored_material_is_flagged(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/".env").write_text("fixture");(root/"README.md").write_text("Readme")
            with patch.object(check_public_files,"git_paths",side_effect=[["README.md",".env"],[]]):
                result=check_public_files.audit(root)
            self.assertFalse(result["passed"])
            self.assertEqual(result["tracked_paths_to_review"],[".env"])

    def test_deleted_placeholders_are_reported_without_being_published(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(check_public_files,"git_paths",side_effect=[["packaging/Containerfile"],[]]):
                result=check_public_files.audit(root)
            self.assertTrue(result["passed"])
            self.assertEqual(result["pending_deletions"],["packaging/Containerfile"])

    def test_possible_secret_in_an_allowed_source_file_blocks_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"src").mkdir()
            (root/"src/accidental.txt").write_text("-----BEGIN "+"PRIVATE KEY-----\nfixture")
            result=check_public_files.audit(root)
            self.assertFalse(result["passed"])
            self.assertEqual(result["secret_findings"][0]["path"],"src/accidental.txt")

    def test_new_public_sources_are_included_without_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"scripts").mkdir();(root/"scripts/new.py").write_text("pass\n")
            with patch.object(check_public_files,"git_paths",side_effect=[[],["scripts/new.py"]]):
                result=check_public_files.audit(root)
            self.assertTrue(result["passed"])
            self.assertEqual(result["new_public_files"],["scripts/new.py"])


if __name__=="__main__":unittest.main()
