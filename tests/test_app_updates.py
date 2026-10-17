import hashlib
import io
import json
import shutil
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from core.app_updates import Release, check_latest_release, download_release, normalize_repository, version_tuple


class Response(io.BytesIO):
    def __init__(self, data=b"", url="https://release-assets.githubusercontent.com/release/app-Portable.exe"):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class UpdateTests(unittest.TestCase):
    def release_data(self, payload=b"verified installer"):
        asset = {"name": "HDU-Portable.exe", "size": len(payload),
                 "browser_download_url": "https://github.com/test/app/releases/download/v1.1.0/HDU-Portable.exe",
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
        with patch("core.app_updates.urlopen", side_effect=[URLError("website unavailable"), Response(json.dumps(data).encode())]):
            release = check_latest_release("test/app")
        self.assertEqual(release.version, "v1.1.0")
        self.assertEqual(release.asset, data["assets"][0])
        progress = []
        with patch("core.app_updates.urlopen", return_value=Response(b"verified installer")):
            path = download_release(release, "test/app", progress.append)
        try:
            self.assertEqual(path.read_bytes(), b"verified installer")
            self.assertEqual(progress[-1], 100)
        finally:
            shutil.rmtree(path.parent)

    def test_no_installer_for_unverified_or_foreign_asset(self):
        for change in ({"digest": None}, {"browser_download_url": "https://example.com/HDU-Setup.exe"},
                       {"name": "../HDU-Portable.exe"}, {"name": "HDU-Setup.exe"}, {"name": "portable.exe"}):
            data = self.release_data()
            data["assets"][0].update(change)
            with patch("core.app_updates.urlopen", side_effect=[URLError("website unavailable"), Response(json.dumps(data).encode())]):
                self.assertIsNone(check_latest_release("test/app").asset)

    def test_corrupt_download_is_rejected_and_removed(self):
        data = self.release_data(b"good")
        release = Release("v1.1.0", "", "", data["assets"][0])
        with patch("core.app_updates.urlopen", return_value=Response(b"evil")):
            with self.assertRaisesRegex(ValueError, "校验失败"):
                download_release(release, "test/app")

    def test_unpublished_repository_has_useful_error(self):
        with patch("core.app_updates.urlopen", side_effect=HTTPError("", 404, "Not Found", None, None)):
            with self.assertRaisesRegex(ValueError, "正式 Release"):
                check_latest_release("test/app")

    def test_release_page_succeeds_without_using_rate_limited_api(self):
        with patch("core.app_updates.urlopen", return_value=Response(url="https://github.com/test/app/releases/tag/v1.2.3")) as request:
            release = check_latest_release("test/app")
        self.assertEqual(release.version, "v1.2.3")
        self.assertEqual(release.url, "https://github.com/test/app/releases/latest")
        request.assert_called_once()
        self.assertEqual(request.call_args.args[0].get_method(), "HEAD")
        self.assertEqual(request.call_args.args[0].full_url, "https://github.com/test/app/releases/latest")

    def test_untrusted_or_non_release_redirect_needs_api_confirmation(self):
        for url in (
            "https://example.com/test/app/releases/tag/v9.0.0",
            "https://github.com/other/app/releases/tag/v9.0.0",
            "https://github.com/test/app/releases/tag/v1.2.3-beta",
            "https://github.com/test/app/releases/tag/v1.2.3%2Fother",
            "https://github.com/login",
            "https://github.com/test/app/releases/latest",
        ):
            with self.subTest(url=url), patch("core.app_updates.urlopen", side_effect=[Response(url=url), Response(json.dumps(self.release_data()).encode())]) as request:
                release = check_latest_release("test/app")
            self.assertEqual(release.version, "v1.1.0")
            self.assertEqual(request.call_count, 2)

    def test_both_sources_failing_never_reports_latest(self):
        for error, message in (
            (HTTPError("", 403, "Forbidden", {"X-RateLimit-Remaining": "0"}, None), "限流"),
            (HTTPError("", 403, "Forbidden", {"X-RateLimit-Remaining": "10"}, None), "拒绝"),
            (HTTPError("", 429, "Too Many Requests", {}, None), "限流"),
            (URLError("offline"), "无法连接"),
        ):
            with self.subTest(message=message), patch("core.app_updates.urlopen", side_effect=[URLError("website unavailable"), error]):
                with self.assertRaisesRegex(ValueError, message):
                    check_latest_release("test/app")


if __name__ == "__main__":
    unittest.main()
