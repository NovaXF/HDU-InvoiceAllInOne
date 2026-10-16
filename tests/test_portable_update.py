import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.portable_update import apply_update, launch_helper, prepare_update


class PortableUpdateTests(unittest.TestCase):
    def test_replaces_user_named_executable_and_preserves_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "new-Portable.exe", root / "renamed-app.exe"
            source.write_bytes(b"new executable")
            target.write_bytes(b"old executable")
            plan = prepare_update(source, target, root / "data")
            with patch("core.portable_update.sys.executable", str(source)), \
                 patch("core.portable_update.subprocess.Popen") as launch:
                result = apply_update(plan)
            self.assertTrue(result["success"])
            self.assertEqual(target.read_bytes(), b"new executable")
            self.assertEqual((plan.parent / "previous.exe").read_bytes(), b"old executable")
            self.assertEqual(launch.call_args.args[0], [str(target)])
            self.assertEqual(list(root.glob("*.update")), [])

    def test_corrupt_download_does_not_replace_current_program(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "new.exe", root / "app.exe"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            plan = prepare_update(source, target, root / "data")
            source.write_bytes(b"tampered")
            with patch("core.portable_update.sys.executable", str(source)), \
                 patch("core.portable_update.subprocess.Popen") as launch:
                result = apply_update(plan)
            self.assertFalse(result["success"])
            self.assertEqual(target.read_bytes(), b"old")
            launch.assert_not_called()

    def test_launch_failure_restores_previous_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "new.exe", root / "app.exe"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            plan = prepare_update(source, target, root / "data")
            with patch("core.portable_update.sys.executable", str(source)), \
                 patch("core.portable_update.subprocess.Popen", side_effect=OSError("cannot launch")):
                result = apply_update(plan)
            self.assertFalse(result["success"])
            self.assertTrue(result["restored"])
            self.assertEqual(target.read_bytes(), b"old")

    def test_helper_uses_fresh_pyinstaller_environment(self):
        with patch("core.portable_update.subprocess.Popen") as launch:
            launch_helper(Path("new.exe"), Path("plan.json"))
        self.assertEqual(launch.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")

    def test_waits_for_running_executable_to_release_file(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / "new.exe", root / "app.exe"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            plan = prepare_update(source, target, root / "data")
            replace = os.replace
            attempts = []

            def locked_once(stage, destination):
                if Path(destination) == target:
                    attempts.append(destination)
                    if len(attempts) == 1:
                        raise PermissionError("still running")
                return replace(stage, destination)

            with patch("core.portable_update.sys.executable", str(source)), patch("core.portable_update.os.replace", side_effect=locked_once), patch("core.portable_update.time.sleep") as pause, patch("core.portable_update.subprocess.Popen"):
                result = apply_update(plan)
            self.assertTrue(result["success"])
            self.assertEqual(len(attempts), 2)
            pause.assert_called_once_with(0.25)
