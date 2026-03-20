from __future__ import annotations

import os
import shutil
import stat
import sys
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devbroom.cleanup import delete_tree


TEST_ROOT = Path(__file__).resolve().parent / ".tmp"


class RepoTempDirTestCase(unittest.TestCase):
    def setUp(self) -> None:
        TEST_ROOT.mkdir(exist_ok=True)
        self.workdir = TEST_ROOT / uuid.uuid4().hex
        self.workdir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


class CleanupTests(RepoTempDirTestCase):
    def test_delete_tree_removes_directory(self) -> None:
        path = self.workdir / "sample"
        path.mkdir()
        (path / "file.txt").write_text("data", encoding="ascii")

        delete_tree(path)

        self.assertFalse(path.exists())

    def test_delete_tree_allows_missing_directory(self) -> None:
        path = self.workdir / "missing"
        delete_tree(path)
        self.assertFalse(path.exists())

    def test_delete_tree_refuses_symlink(self) -> None:
        target = self.workdir / "target"
        target.mkdir()
        link = self.workdir / "link"

        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable in this environment")

        with self.assertRaises(OSError):
            delete_tree(link)

    def test_delete_tree_removes_read_only_files(self) -> None:
        path = self.workdir / "readonly"
        path.mkdir()
        file_path = path / "file.txt"
        file_path.write_text("data", encoding="ascii")
        os.chmod(file_path, stat.S_IREAD)

        delete_tree(path)

        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
