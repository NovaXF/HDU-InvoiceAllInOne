"""GitHub Releases update checks and verified portable executable downloads."""

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from app_version import APP_VERSION


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    notes: str
    asset: dict | None


def normalize_repository(value: str) -> str:
    value = value.strip().removesuffix("/").removesuffix(".git")
    if value.startswith("https://github.com/"):
        value = value[len("https://github.com/"):]
    if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", value):
        raise ValueError("请填写 GitHub 仓库地址，例如 https://github.com/用户名/HDU-InvoiceAllInOne")
    if value.split("/")[1] in (".", ".."):
        raise ValueError("GitHub 仓库名称无效")
    return value


def version_tuple(value: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        raise ValueError("正式版本号应为 v1.0.0 格式")
    return tuple(int(part) for part in match.groups())


def _portable_asset(asset: dict, repository: str) -> bool:
    name = asset.get("name", "")
    if Path(name).name != name or "\\" in name:
        return False
    if not name.lower().endswith("-portable.exe"):
        return False
    url = urlsplit(asset.get("browser_download_url", ""))
    return (url.scheme == "https" and url.netloc == "github.com"
            and unquote(url.path).startswith(f"/{repository}/releases/download/")
            and bool(re.fullmatch(r"sha256:[a-fA-F0-9]{64}", asset.get("digest") or "")))


def check_latest_release(repository: str) -> Release:
    repository = normalize_repository(repository)
    request = Request(f"https://api.github.com/repos/{repository}/releases/latest", headers={
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"HDU-InvoiceAllInOne/{APP_VERSION}",
    })
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read(2 * 1024 * 1024))
    except HTTPError as error:
        if error.code == 404:
            raise ValueError("尚未找到正式 Release，请确认仓库公开且已发布正式版本。") from error
        if error.code in (403, 429):
            raise ValueError("GitHub 暂时限制了访问，请稍后重试。") from error
        raise ValueError(f"GitHub 请求失败（{error.code}）") from error
    except (URLError, TimeoutError) as error:
        raise ValueError("无法连接 GitHub，请检查网络后重试。") from error
    version = data.get("tag_name", "")
    version_tuple(version)
    if data.get("draft") or data.get("prerelease"):
        raise ValueError("当前没有可用的正式版本。")
    return Release(version, f"https://github.com/{repository}/releases/latest", data.get("body") or "",
                   next((asset for asset in data.get("assets", []) if _portable_asset(asset, repository)), None))


def download_release(release: Release, repository: str, progress=lambda value: None) -> Path:
    repository = normalize_repository(repository)
    asset = release.asset
    if not asset or not _portable_asset(asset, repository):
        raise ValueError("此版本未提供可校验的单文件便携版，请前往发布页下载。")
    size = asset.get("size", 0)
    if not isinstance(size, int) or not 0 < size <= 2 * 1024**3:
        raise ValueError("更新文件大小无效。")
    folder = Path(tempfile.mkdtemp(prefix="hdu-invoice-update-"))
    target = folder / asset["name"]
    digest = hashlib.sha256()
    request = Request(asset["browser_download_url"], headers={"User-Agent": f"HDU-InvoiceAllInOne/{APP_VERSION}"})
    try:
        with urlopen(request, timeout=30) as response, target.open("wb") as output:
            final_url = urlsplit(response.geturl())
            if final_url.scheme != "https" or not (
                final_url.hostname == "github.com" or (final_url.hostname or "").endswith(".githubusercontent.com")
            ):
                raise ValueError("更新文件下载地址无效。")
            received = 0
            while chunk := response.read(256 * 1024):
                received += len(chunk)
                if received > size:
                    raise ValueError("更新文件大小与发布信息不一致。")
                output.write(chunk)
                digest.update(chunk)
                progress(int(received * 100 / size))
        if received != size or digest.hexdigest().lower() != asset["digest"].split(":", 1)[1].lower():
            raise ValueError("更新文件校验失败，已取消更新，请重新检查。")
        return target
    except Exception:
        target.unlink(missing_ok=True)
        folder.rmdir()
        raise
