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
        cls.repo = GitHubRepo("MBQbUtils", "BulkStartStop")
        cls.spec = SimpleSpec("~1")
        cls.out_dir = Path("test/out")

    def tearDown(self):
        shutil.rmtree(self.out_dir, True)

    def test_run_and_stop(self):
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


if __name__ == '__main__':
    unittest.main()
