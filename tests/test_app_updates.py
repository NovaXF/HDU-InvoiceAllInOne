import hashlib
import io
import json
import shutil
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from core.app_updates import Release, check_latest_release, download_installer, normalize_repository, version_tuple


class Response(io.BytesIO):
    def geturl(self):
        return "https://release-assets.githubusercontent.com/release/setup.exe"


class UpdateTests(unittest.TestCase):
    def release_data(self, payload=b"verified installer"):
        asset = {"name": "HDU-Setup.exe", "size": len(payload),
                 "browser_download_url": "https://github.com/test/app/releases/download/v1.1.0/HDU-Setup.exe",
                 "digest": "sha256:" + hashlib.sha256(payload).hexdigest()}
        return {"tag_name": "v1.1.0", "body": "Changes", "assets": [asset]}

    def test_repository_and_version_validation(self):
        self.assertEqual(normalize_repository("https://github.com/test/app.git"), "test/app")
        self.assertGreater(version_tuple("v1.10.0"), version_tuple("1.9.9"))
        for value in ("", "https://gitee.com/test/app", "test/app/extra", "../app"):
            with self.assertRaises(ValueError):
                normalize_repository(value)
        with self.assertRaises(ValueError):
            version_tuple("v1.0.0-beta")

    def test_latest_release_and_verified_installer(self):
        data = self.release_data()
        with patch("core.app_updates.urlopen", return_value=Response(json.dumps(data).encode())):
            release = check_latest_release("test/app")
        self.assertEqual(release.version, "v1.1.0")
        self.assertEqual(release.asset, data["assets"][0])
        progress = []
        with patch("core.app_updates.urlopen", return_value=Response(b"verified installer")):
            path = download_installer(release, "test/app", progress.append)
        try:
            self.assertEqual(path.read_bytes(), b"verified installer")
            self.assertEqual(progress[-1], 100)
        finally:
            shutil.rmtree(path.parent)

    def test_no_installer_for_unverified_or_foreign_asset(self):
        for change in ({"digest": None}, {"browser_download_url": "https://example.com/HDU-Setup.exe"},
                       {"name": "../HDU-Setup.exe"}, {"name": "portable.exe"}):
            data = self.release_data()
            data["assets"][0].update(change)
            with patch("core.app_updates.urlopen", return_value=Response(json.dumps(data).encode())):
                self.assertIsNone(check_latest_release("test/app").asset)

    def test_corrupt_download_is_rejected_and_removed(self):
        data = self.release_data(b"good")
        release = Release("v1.1.0", "", "", data["assets"][0])
        with patch("core.app_updates.urlopen", return_value=Response(b"evil")):
            with self.assertRaisesRegex(ValueError, "校验失败"):
                download_installer(release, "test/app")

    def test_unpublished_repository_has_useful_error(self):
        with patch("core.app_updates.urlopen", side_effect=HTTPError("", 404, "Not Found", None, None)):
            with self.assertRaisesRegex(ValueError, "正式 Release"):
                check_latest_release("test/app")


if __name__ == "__main__":
    unittest.main()
