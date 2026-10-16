import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.app_paths import load_settings, relocate_data_directory, settings_path


class AppPathsTests(unittest.TestCase):
    def test_source_preferences_stay_in_project(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "frozen", False, create=True), \
             patch("core.app_paths.RESOURCE_ROOT", Path(folder)):
            self.assertEqual(settings_path(), Path(folder) / "settings.json")

    def test_frozen_preferences_survive_temporary_extraction_path_changes(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "frozen", True, create=True), \
             patch.dict(os.environ, {"LOCALAPPDATA": folder}):
            with patch("core.app_paths.RESOURCE_ROOT", Path(folder) / "_MEI-one"):
                first = settings_path()
                first.parent.mkdir(parents=True)
                first.write_text(json.dumps({"theme": "minimal_bw"}), encoding="utf-8")
            with patch("core.app_paths.RESOURCE_ROOT", Path(folder) / "_MEI-two"):
                self.assertEqual(settings_path(), first)
                self.assertEqual(load_settings()["theme"], "minimal_bw")

    def test_legacy_settings_are_loaded_without_modifying_the_original(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "frozen", True, create=True), \
             patch.dict(os.environ, {"LOCALAPPDATA": str(Path(folder) / "user")}), \
             patch.object(sys, "executable", str(Path(folder) / "app.exe")), \
             patch("core.app_paths.RESOURCE_ROOT", Path(folder) / "bundle"):
            legacy = Path(folder) / "settings.json"
            legacy.write_text('{"theme": "minimal_bw"}', encoding="utf-8")
            self.assertEqual(load_settings()["theme"], "minimal_bw")
            self.assertFalse(settings_path().exists())

    def test_invalid_settings_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "frozen", False, create=True):
            path = Path(folder) / "settings.json"
            for content in ("invalid", "[]", "null"):
                path.write_text(content, encoding="utf-8")
                self.assertEqual(load_settings(path), {})

    def test_relocate_preserves_preferences_across_restart_and_keeps_original(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "frozen", False, create=True), \
             patch("core.app_paths.RESOURCE_ROOT", Path(folder) / "source"):
            original = settings_path()
            original.parent.mkdir(parents=True)
            data = {"theme": "minimal_bw", "common_remarks": ["test"]}
            original.write_text(json.dumps(data), encoding="utf-8")
            target = Path(folder) / "chosen-data"
            actual = relocate_data_directory(target, data)
            self.assertEqual(actual, target / "settings.json")
            self.assertTrue(original.exists())
            self.assertEqual(settings_path(), actual)
            self.assertEqual(load_settings(), data)

    def test_relocate_does_not_overwrite_different_preferences(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "frozen", False, create=True), \
             patch("core.app_paths.RESOURCE_ROOT", Path(folder) / "source"):
            target = Path(folder) / "existing"
            target.mkdir()
            (target / "settings.json").write_text('{"theme":"other"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                relocate_data_directory(target, {"theme": "minimal_bw"})
            self.assertEqual(load_settings(target / "settings.json"), {"theme": "other"})
            self.assertEqual(settings_path(), Path(folder) / "source" / "settings.json")
