# GitHub Release Downloader
[![PyPI version shields.io](https://img.shields.io/pypi/v/github_release_downloader.svg)](https://pypi.org/project/github_release_downloader/)
[![GitHub license](https://img.shields.io/github/license/MBQbUtils/GithubReleaseDownloader.svg)](https://github.com/MaxBQb/github_release_downloader/blob/master/LICENSE.md)
![Python versions](https://img.shields.io/pypi/pyversions/github_release_downloader.svg)
---
Python package to download/filter any release assets from the latest compatible version.

## Installation
```cmd
pip install github-release-downloader
```

## Usage

This tool can be used as library:
```py
from semantic_version import SimpleSpec
from github_release_downloader import check_and_download_updates, GitHubRepo
from pathlib import Path
import re


check_and_download_updates(
    GitHubRepo("OwnerName", "RepoName", "OptionallyToken"),  # Releases source
    SimpleSpec("~1.1"),  # Search 1.1.0 compatible version
    assets_mask=re.compile(".*\\.exe"),  # Download *.exe only
    downloads_dir=Path("downloads"),  # Where to download
)
```
Or either it can be used as cli-tool:
```cmd
python -m github_release_downloader -u OwnerName -n RepoName -r ~1.1 -m .*\.exe -o .\downloads
```

## Features
1. Downloads compatible releases (or latest if no requirements set)
2. Filters assets using regex
3. Has optional download_callback
4. CLI tool can be used in CI
5. Handles token from GITHUB_TOKEN env
6. Loads updates only when it's needed (caches last version used)
7. Loggs own actions
8. Uses only few GitHub API endpoints (don't download code, you've never needed)
