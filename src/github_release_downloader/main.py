import argparse
import dataclasses
import itertools
import json
import logging
import os
import re
import sys
import typing
from pathlib import Path
from typing import Callable

import requests
from semantic_version import Version, SimpleSpec

from github_release_downloader import _meta


def get_args():
    parser = argparse.ArgumentParser(
        "Github Release Downloader",
        "Package to download any release assets from the latest compatible version",
    )
    parser.add_argument('-v', '--version', action='version', version=_meta.__version__)
    parser.add_argument('-u', '--user', action='store', required=True, help="Github repo owner name")
    parser.add_argument('-n', '--repo-name', action='store', required=True, help="Github repo name")
    parser.add_argument('-m', '--mask', action='store', help="Regex mask to select assets by name", default=".*")
    parser.add_argument('-c', '--current-version', action='store', help="Current version installed")
    parser.add_argument('-t', '--token', action='store', help="Github token",
                        default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument('-r', '--require', action='store', required=True,
                        help="Version compatibility specification, e.g. >=1.2.0,~1.3")
    return parser.parse_args()


def main():
    logging.basicConfig(
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt='%H:%M:%S',
        level=logging.INFO
    )
    args = get_args()
    check_and_download_updates(
        GitHubRepo(args.user, args.repo_name, args.token),
        SimpleSpec(args.require),
        assets_mask=re.compile(args.mask),
        current_version=Version(args.current_version) if args.current_version else None
    )


@dataclasses.dataclass
class GitHubRepo:
    user: str
    repo: str
    token: str = ""


@dataclasses.dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int

    @property
    def is_valid(self):
        return not (
            self.name is None
            or not self.name.strip(" ")
            or self.url is None
            or not self.url.strip(" ")
            or self.size is None
            or self.size <= 0
        )


class AuthSession:
    header = dict()

    @classmethod
    def init(cls, repo: GitHubRepo):
        if cls.header or not repo.token:
            return
        cls.header = dict(Authorization=f'Bearer {repo.token}')


class Cache:
    def __init__(self, filename: str = "version.cache"):
        self._filename = Path(filename)
        self._cache = None

    @property
    def version(self):
        if self._cache is None:
            self._load()
        value = self._cache.get("version")
        return Version(value) if value else None

    @version.setter
    def version(self, value: Version):
        if self._cache is None:
            self._cache = {}
        self._cache["version"] = str(value)
        self._save()

    def _load(self):
        if not self._filename.exists() or not self._filename.is_file():
            self._save()
        try:
            with open(self._filename, "r") as file:
                self._cache = json.load(file)
        except Exception as e:
            logging.exception("Unable to load cache:", exc_info=e)
            self._save()

    def _save(self):
        with open(self._filename, "w") as file:
            json.dump(self._cache or {'version': None}, file)


def check_and_download_updates(
    repo: GitHubRepo,
    compatibility_spec: SimpleSpec,
    current_version: Version = None,
    assets_mask=re.compile('.*'),
    downloads_dir=Path(),
    download_callback: Callable[[ReleaseAsset, int], None] = None
):
    if download_callback is None:
        download_callback = default_download_callback
    cache = Cache(f"repo-{repo.user}-{repo.repo}.cache")
    if current_version is None:
        current_version = cache.version
        if current_version is None:
            current_version = Version("0.0.0")
    AuthSession.init(repo)
    logging.info(f"Compatibility requirement: '{compatibility_spec}'")

    versions = list(sorted(compatibility_spec.filter(get_available_versions(repo)))[-10:])
    if not versions:
        logging.warning(f"No newer compatible versions available.")
        return
    logging.info(f"Available versions: {tuple(map(str, versions))}")
    download_version = versions[-1]
    if is_already_installed(download_version, current_version, compatibility_spec):
        return
    tag_name = getattr(download_version, '_origin_tag_name', str(download_version))
    assets = get_assets(repo, tag_name, assets_mask)
    if not assets:
        logging.error(f"No assets found")
        return
    download_assets(assets, out_dir=downloads_dir, callback=download_callback)
    logging.info(f"Done!")
    cache.version = download_version


def download_assets(
    assets: typing.Iterable[ReleaseAsset],
    out_dir=Path(),
    block_size=2**20,
    callback: Callable[[ReleaseAsset, int], None] = lambda _, __: None
):
    logging.info(f"Start downloading assets: {tuple(asset.name for asset in assets)}")
    for asset in assets:
        download_asset(asset, out_dir, block_size,
                       lambda downloaded, _: callback(asset, downloaded))


def download_asset(
    asset: ReleaseAsset,
    out_dir=Path(),
    block_size=2**20,
    callback: Callable[[int, int], None] = lambda _, __: None
):
    logging.info(f"Start downloading asset: '{asset.name}'")
    if out_dir.is_file():
        out_dir = out_dir.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    response = requests.get(asset.url, stream=True, headers=AuthSession.header)
    with open(out_dir.joinpath(asset.name), 'wb') as file:
        for i, data in enumerate(response.iter_content(block_size)):
            file.write(data)
            callback(i*block_size, asset.size)
        callback(asset.size, asset.size)


def default_download_callback(asset: ReleaseAsset, downloaded: int):
    logging.info(
        f"'{asset.name}' downloading progress: "
        f"{downloaded // 2 ** 13}/{asset.size // 2 ** 13}kb "
        f"({100 * downloaded / asset.size:.2f}%)"
    )


def get_available_versions(repo: GitHubRepo, process_tag: Callable[[str], Version] = None):
    if process_tag is None:
        process_tag = parse_tag
    logging.info(f"Searching for releases in 'https://github.com/{repo.user}/{repo.repo}/'...")
    request_url = f"https://api.github.com/repos/{repo.user}/{repo.repo}/releases"
    page_size = 100
    for i in itertools.count(1):
        data = json.loads(requests.get(request_url, dict(page=i, per_page=page_size), headers=AuthSession.header).text)
        if 'message' in data or not isinstance(data, list):
            break
        for release in data:
            tag_name = release.get("tag_name")
            if tag_name is None:
                continue
            version = process_tag(tag_name)
            version._origin_tag_name = tag_name
            yield version
        logging.info(f"Version's page#{i} loaded")
        if len(data) < page_size:
            logging.info(f"No more pages")
            break


def parse_tag(tag_name: str):
    return Version(tag_name.lstrip("v").strip())


def get_assets(repo: GitHubRepo, tag_name: str, assets_mask=re.compile('.*')):
    logging.info(f"Searching for assets by tag '{tag_name}' and mask: '{assets_mask.pattern}'")
    request_url = f"https://api.github.com/repos/{repo.user}/{repo.repo}/releases/tags/{tag_name}"
    data = json.loads(requests.get(request_url, headers=AuthSession.header).text)
    if 'message' in data:
        return []
    assets = data.get('assets')
    if not assets:
        return []
    assets = (ReleaseAsset(
        asset.get("name"),
        asset.get("browser_download_url"),
        asset.get("size"),
    ) for asset in assets)
    return tuple(
        asset for asset in assets
        if asset.is_valid and assets_mask.match(asset.name) is not None
    )


def is_already_installed(latest: Version, current: Version, compatibility_spec: SimpleSpec):
    if current < latest:
        return False
    logging.info(f"Latest version is already installed: {current}")
    if current > latest:
        logging.warning(
            f"Current version newer then latest found ({latest})" + (
                ", but still compatible." if compatibility_spec.match(current)
                else ", and incompatible!"
            )
        )
    return True


if __name__ == '__main__':
    main()
