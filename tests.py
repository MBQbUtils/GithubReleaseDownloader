import logging
import os
import re
import shutil
import unittest
from glob import glob
from pathlib import Path

from semantic_version import SimpleSpec

from github_release_downloader import check_and_download_updates, GitHubRepo


class DownloadRelease(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.repo = GitHubRepo("MBQbUtils", "BulkStartStop", os.environ.get("GITHUB_TOKEN", ""))
        cls.spec = SimpleSpec("~1.0")
        cls.out_dir = Path("test/out")
        logging.basicConfig(
            format="[%(asctime)s][%(levelname)s] %(message)s",
            datefmt='%H:%M:%S',
            level=logging.INFO
        )

    def tearDown(self):
        shutil.rmtree(self.out_dir, True)
        for path in glob("repo-*-*.cache"):
            Path(path).unlink()

    def test_download_compatible_exe(self):
        check_and_download_updates(
            self.repo,
            self.spec,
            assets_mask=re.compile(".*\\.exe"),
            downloads_dir=self.out_dir
        )
        files = glob(str(self.out_dir.joinpath("*.exe")))
        file_expected = Path(self.out_dir).joinpath("BulkStartStop_setup.exe")
        file_actual = Path(files[0])
        self.assertTrue(file_actual.samefile(file_expected))

    def test_download_latest_zip(self):
        check_and_download_updates(
            self.repo,
            assets_mask=re.compile(".*\\.zip"),
            downloads_dir=self.out_dir
        )
        files = glob(str(self.out_dir.joinpath("*.zip")))
        file_expected = Path(self.out_dir).joinpath("BulkStartStop_portable.zip")
        file_actual = Path(files[0])
        self.assertTrue(file_actual.samefile(file_expected))


if __name__ == '__main__':
    unittest.main()
