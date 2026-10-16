import os
import unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QMessageBox, QStyleOptionViewItem
from PySide6.QtTest import QTest

from models.invoice import Invoice, OrderScreenshot, Stack, DateGroup
from ui.main_window import MainWindow, ParseWorker
from core.pdf_parser import InvoiceParseResult, _parse_invoice_number
from core.app_updates import Release
from app_version import APP_VERSION


class TestWindow(MainWindow):
    def _load_settings(self):
        return {}

    def _save_settings(self):
        pass


class StackWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.window = TestWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def add_invoices(self, amounts):
        invoices = [Invoice(Path(f"{i}.pdf"), amount=amount) for i, amount in enumerate(amounts)]
        self.window.invoices.extend(invoices)
        return invoices

    def assert_unique_assignments(self):
        stacks = [stack for group in self.window.date_groups for stack in group.stacks]
        self.assertEqual(len(stacks), len({id(stack) for stack in stacks}))
        ids = [invoice.invoice_id for stack in stacks for invoice in stack.invoices]
        self.assertEqual(len(ids), len(set(ids)))
        for group in self.window.date_groups:
            self.assertEqual([stack.index for stack in group.stacks], list(range(1, len(group.stacks) + 1)))
            for stack in group.stacks:
                self.assertTrue(all(invoice.stack_index == stack.index for invoice in stack.invoices))

    def test_return_each_invoice_and_split_again_keeps_one_stack(self):
        invoices = self.add_invoices([80] * 16)
        self.window._split_left_invoices_into_stacks()
        group = self.window.date_groups[0]
        original = group.stacks[0]
        for invoice in invoices:
            self.window._return_invoices_to_left([invoice.invoice_id])
            self.assertIs(self.window.stacks, group.stacks)
            self.assertEqual(original.count, 15)
            self.window._split_left_invoices_into_stacks()
            self.assertEqual(len(group.stacks), 1)
            self.assertIs(group.stacks[0], original)
            self.assertEqual(original.count, 16)
            self.assert_unique_assignments()

    def test_return_all_then_split_again(self):
        invoices = self.add_invoices([80] * 16)
        self.window._split_left_invoices_into_stacks()
        group = self.window.date_groups[0]
        self.window._return_invoices_to_left([invoice.invoice_id for invoice in invoices])
        self.assertIs(self.window.stacks, group.stacks)
        self.assertEqual(group.stacks, [])
        self.window._split_left_invoices_into_stacks()
        self.assertEqual(len(group.stacks), 1)
        self.assertEqual(group.stacks[0].count, 16)
        self.assert_unique_assignments()

    def test_new_stack_only_when_no_existing_stack_fits(self):
        self.window.spin_max_count.setValue(2)
        self.window.spin_max_amount.setValue(100)
        invoices = self.add_invoices([60, 40, 30, 20, 70])
        self.window._split_left_invoices_into_stacks()
        group = self.window.date_groups[0]
        self.assertEqual([stack.total for stack in group.stacks], [100, 50, 70])
        self.window._return_invoices_to_left([invoices[3].invoice_id])
        self.window._split_left_invoices_into_stacks()
        self.assertEqual([stack.total for stack in group.stacks], [100, 50, 70])
        self.assert_unique_assignments()

    def test_stale_list_does_not_reimport_existing_stack(self):
        self.add_invoices([10])
        self.window._split_left_invoices_into_stacks()
        group = self.window.date_groups[0]
        self.window.stacks = list(group.stacks)
        self.window._ensure_current_date_group()
        self.assertEqual(len(group.stacks), 1)
        self.assertIs(self.window.stacks, group.stacks)
        self.assert_unique_assignments()

    def test_date_row_height_accommodates_large_font(self):
        self.add_invoices([10])
        self.window._split_left_invoices_into_stacks()
        tree = self.window.tree
        index = tree.indexFromItem(tree.topLevelItem(0))
        self.assertEqual(index.data(Qt.UserRole)[0], "date")
        option = QStyleOptionViewItem()
        option.font.setPointSize(24)
        option.fontMetrics = QFontMetrics(option.font)
        hint = tree.itemDelegate().sizeHint(option, index)
        self.assertGreaterEqual(hint.height(), option.fontMetrics.height() + 28)

    def test_number_alone_detects_renamed_duplicate_in_existing_stack(self):
        existing = self.add_invoices([16])[0]
        existing.invoice_number = "10000000000000000001"  # Synthetic test number.
        self.window._split_left_invoices_into_stacks()
        renamed = Invoice(Path("1111.pdf"), amount=16, invoice_number=existing.invoice_number)
        self.window.invoices.append(renamed)
        self.assertIs(self.window._find_duplicate_invoice(renamed), existing)
        renamed.invoice_code = "different-code"
        self.assertIs(self.window._find_duplicate_invoice(renamed), existing)
        self.assertEqual(Invoice.from_dict(existing.to_dict()).unique_key, existing.unique_key)

    def test_bulk_results_remain_attached_to_invoice_after_duplicates_removed(self):
        existing = self.add_invoices([16])[0]
        existing.invoice_number = "12345678"
        incoming = [Invoice(Path(f"new-{i}.pdf")) for i in range(4)]
        self.window.invoices.extend(incoming)
        results = [InvoiceParseResult(amount, invoice_number=number) for amount, number in
                   [(16, "12345678"), (20, "87654321"), (16, "12345678"), (30, "11223344")]]
        worker = ParseWorker(incoming)
        worker.result.connect(self.window._on_result)
        with patch("ui.main_window.extract_invoice_data", side_effect=results), \
             patch.object(self.window, "_show_duplicate_invoice_dialog") as dialog:
            worker.run()
        self.assertEqual(dialog.call_count, 2)
        self.assertEqual(self.window.invoices, [existing, incoming[1], incoming[3]])
        self.assertEqual((incoming[1].amount, incoming[1].invoice_number), (20, "87654321"))
        self.assertEqual((incoming[3].amount, incoming[3].invoice_number), (30, "11223344"))

    def test_duplicate_dialog_delete_targets_only_new_pdf(self):
        existing = self.add_invoices([16])[0]
        existing.invoice_number = "12345678"
        imported = Invoice(Path("renamed.pdf"), amount=16, invoice_number="12345678")
        def click_delete():
            dialog = self.app.activeModalWidget()
            button = next(button for button in dialog.buttons() if button.text() == "删除新增的重复发票")
            self.assertTrue(button.isEnabled())
            button.click()
        QTimer.singleShot(0, click_delete)
        with patch("ui.main_window.recycle_file") as recycle:
            self.window._show_duplicate_invoice_dialog(imported, existing)
        recycle.assert_called_once_with(imported.source_path)
        self.assertIn(existing, self.window.invoices)

    def test_duplicate_number_checked_even_when_amount_is_unrecognized(self):
        existing = self.add_invoices([16])[0]
        existing.invoice_number = "12345678"
        imported = Invoice(Path("renamed-no-amount.pdf"))
        self.window.invoices.append(imported)
        worker = ParseWorker([imported])
        worker.result.connect(self.window._on_result)
        with patch("ui.main_window.extract_invoice_data", return_value=InvoiceParseResult(None, invoice_number="12345678")), \
             patch.object(self.window, "_show_duplicate_invoice_dialog") as dialog:
            worker.run()
        dialog.assert_called_once_with(imported, existing)
        self.assertEqual(self.window.invoices, [existing])

    def test_duplicate_dialog_protects_existing_file_path(self):
        existing = self.add_invoices([16])[0]
        imported = Invoice(existing.source_path)
        def click_ok():
            dialog = self.app.activeModalWidget()
            button = next(button for button in dialog.buttons() if button.text() == "删除新增的重复发票")
            self.assertFalse(button.isEnabled())
            dialog.button(QMessageBox.Ok).click()
        QTimer.singleShot(0, click_ok)
        with patch("ui.main_window.recycle_file") as recycle:
            self.window._show_duplicate_invoice_dialog(imported, existing)
        recycle.assert_not_called()

    def test_duplicate_dialog_is_on_top_and_restores_minimized_workspace(self):
        existing = self.add_invoices([16])[0]
        existing.invoice_number = "12345678"
        imported = Invoice(Path("renamed.pdf"), invoice_number="12345678")
        self.window.showMinimized()
        self.app.processEvents()
        observed = {}
        def close_dialog():
            dialog = self.app.activeModalWidget()
            observed["on_top"] = bool(dialog.windowFlags() & Qt.WindowStaysOnTopHint)
            observed["modal"] = dialog.windowModality()
            observed["minimized"] = self.window.isMinimized()
            observed["main_on_top"] = bool(self.window.windowFlags() & Qt.WindowStaysOnTopHint)
            dialog.button(QMessageBox.Ok).click()
        QTimer.singleShot(0, close_dialog)
        self.window._show_duplicate_invoice_dialog(imported, existing)
        self.assertTrue(observed["on_top"])
        self.assertEqual(observed["modal"], Qt.WindowModal)
        self.assertFalse(observed["minimized"])
        self.assertFalse(observed["main_on_top"])
        self.assertIsNone(self.app.activeModalWidget())

    def test_invoice_number_extraction_and_normalization(self):
        number = "10000000000000000001"
        for text in (f"发票号码：{number}", f"发 票 号 码 :\n{number}",
                     "发票号码：１００００００００００００００００００１", f"发票号码：{' '.join(number)}"):
            self.assertEqual(_parse_invoice_number(text), number)
        self.assertEqual(_parse_invoice_number("票据号码：00123456\n开票日期：2026年10月15日"), "00123456")
        self.assertIsNone(_parse_invoice_number("金额 ¥16.00"))
        self.assertEqual(Invoice(Path("x.pdf"), invoice_number=" ００１２ ３４５６ ").unique_key, "00123456")

    def focus_view(self, view):
        self.window.activateWindow()
        view.setFocus()
        self.app.processEvents()

    def test_left_delete_and_keyboard_undo_redo_keep_source_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.pdf"
            path.write_bytes(b"test source")
            invoice = Invoice(path, amount=16)
            self.window.invoices = [invoice]
            self.window._render_all()
            self.window.table.selectRow(0)
            self.focus_view(self.window.table)
            QTest.keyClick(self.window.table, Qt.Key_Delete)
            self.assertEqual(self.window.invoices, [])
            self.assertTrue(path.is_file())
            self.assertTrue(self.window.btn_undo.isEnabled())
            QTest.keyClick(self.window.table, Qt.Key_Z, Qt.ControlModifier)
            self.assertEqual([item.invoice_id for item in self.window.invoices], [invoice.invoice_id])
            QTest.keyClick(self.window.table, Qt.Key_Y, Qt.ControlModifier)
            self.assertEqual(self.window.invoices, [])
            self.assertTrue(path.is_file())

    def test_tree_delete_returns_invoice_and_screenshot_and_is_undoable(self):
        invoice = self.add_invoices([16])[0]
        screenshot = OrderScreenshot(Path("shot.png"), amount=16)
        self.window.screenshots = [screenshot]
        self.window._split_left_invoices_into_stacks()
        self.window._bind_screenshot_to_invoice(screenshot.screenshot_id, invoice.invoice_id)
        self.assertEqual(self.window.screenshot_table.rowCount(), 0)
        self.assertEqual(len(self.window.date_groups[0].screenshots), 1)
        tree = self.window.tree
        item = tree.topLevelItem(0).child(0).child(0)
        tree.setCurrentItem(item)
        self.focus_view(tree)
        before_history = len(self.window._undo_history)
        QTest.keyClick(tree, Qt.Key_Delete)
        self.assertEqual(len(self.window.invoices), 1)
        self.assertIsNone(self.window.invoices[0].stack_index)
        self.assertIsNone(self.window.invoices[0].matched_screenshot_id)
        self.assertEqual(self.window.table.rowCount(), 1)
        self.assertEqual(self.window.screenshot_table.rowCount(), 1)
        self.assertEqual(len(self.window._undo_history), before_history + 1)
        self.window._undo_workspace()
        self.assertEqual(self.window.invoices[0].stack_index, 1)
        self.assertEqual(self.window.invoices[0].matched_screenshot_id, screenshot.screenshot_id)
        group = self.window.date_groups[0]
        self.assertIs(self.window.stacks, group.stacks)
        self.assertIs(group.stacks[0].invoices[0], self.window.invoices[0])
        self.assertIs(group.screenshots[0], self.window.screenshots[0])
        self.window._redo_workspace()
        self.assertEqual(self.window.screenshot_table.rowCount(), 1)
        self.assertIsNone(self.window.invoices[0].stack_index)

    def test_left_screenshot_delete_unbinds_and_can_be_restored(self):
        invoice = self.add_invoices([16])[0]
        screenshot = OrderScreenshot(Path("wrong.png"), amount=16,
                                     matched_invoice_id=invoice.invoice_id)
        self.window.screenshots = [screenshot]
        # Unmatched/error screenshots are displayed on the left.
        screenshot.error = "test"
        self.window._render_all()
        self.window.screenshot_table.selectRow(0)
        self.focus_view(self.window.screenshot_table)
        QTest.keyClick(self.window.screenshot_table, Qt.Key_Delete)
        self.assertEqual(self.window.screenshots, [])
        self.assertIsNone(self.window.invoices[0].matched_screenshot_id)
        self.window._undo_workspace()
        self.assertEqual(self.window.screenshots[0].screenshot_id, screenshot.screenshot_id)
        self.assertEqual(self.window.invoices[0].matched_screenshot_id, screenshot.screenshot_id)

    def test_redo_branch_is_discarded_after_new_edit(self):
        self.add_invoices([10, 20])
        self.window._split_left_invoices_into_stacks()
        self.focus_view(self.window.tree)
        self.window._undo_workspace()
        self.assertTrue(self.window._redo_history)
        self.window.table.selectRow(0)
        self.window._delete_selected_left_invoices()
        self.assertEqual(self.window._redo_history, [])
        self.assertFalse(self.window.btn_redo.isEnabled())

    def test_import_is_one_undo_step_after_background_results(self):
        with patch("ui.main_window.extract_invoice_data", return_value=InvoiceParseResult(16, invoice_number="12345678")):
            self.window._on_drop([Path("new.pdf")])
            for _ in range(100):
                QTest.qWait(10)
                if not self.window._workspace_busy():
                    break
        self.assertFalse(self.window._workspace_busy())
        self.assertEqual(len(self.window._undo_history), 1)
        self.assertEqual(self.window.invoices[0].invoice_number, "12345678")
        self.focus_view(self.window.table)
        self.window._undo_workspace()
        self.assertEqual(self.window.invoices, [])
        self.window._redo_workspace()
        self.assertEqual(self.window.invoices[0].invoice_number, "12345678")

    def test_delete_in_text_input_does_not_delete_old_table_selection(self):
        self.add_invoices([16])
        self.window._render_all()
        self.window.table.selectRow(0)
        self.window.edit_output.setText("abc")
        self.window.edit_output.selectAll()
        self.focus_view(self.window.edit_output)
        QTest.keyClick(self.window.edit_output, Qt.Key_Delete)
        self.assertEqual(self.window.edit_output.text(), "")
        self.assertEqual(len(self.window.invoices), 1)

    def test_return_from_later_date_after_first_date_is_empty(self):
        invoice = self.add_invoices([16])[0]
        invoice.stack_index = 1
        self.window.date_groups = [
            DateGroup("2026年10月14日", Path("."), [], locked=False),
            DateGroup("2026年10月15日", Path("."), [Stack(1, [invoice])], locked=False),
        ]
        self.window.stacks = self.window.date_groups[1].stacks
        self.window._return_invoices_to_left([invoice.invoice_id])
        self.assertTrue(all(not group.stacks for group in self.window.date_groups))
        self.assertIsNone(self.window.invoices[0].stack_index)
        self.focus_view(self.window.tree)
        self.window._undo_workspace()
        self.assertIs(self.window.date_groups[1].stacks[0].invoices[0], self.window.invoices[0])
        self.assertEqual(self.window.invoices[0].stack_index, 1)

    def test_locked_return_makes_no_history_entry(self):
        invoice = self.add_invoices([16])[0]
        self.window._split_left_invoices_into_stacks()
        self.window.date_groups[0].locked = True
        before = len(self.window._undo_history)
        with patch("ui.main_window.QMessageBox.information"):
            self.window._return_invoices_to_left([invoice.invoice_id])
        self.assertEqual(invoice.stack_index, 1)
        self.assertEqual(len(self.window._undo_history), before)

    def test_help_and_settings_share_version_and_subtitle_position(self):
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import QPoint
        from ui.main_window import THEMES
        self.assertEqual(self.window.pages.widget(2).findChild(QLabel, "HelpVersion").text(), f"适用版本 v{APP_VERSION}")
        self.assertEqual(self.window.pages.widget(3).findChild(QLabel, "VersionNumber").text(), f"v{APP_VERSION}")
        for key in THEMES:
            self.window._select_theme(key)
            positions = []
            for page_no, object_name in ((1, "PageSubtitle"), (2, "HelpVersion")):
                self.window._switch_page(page_no)
                self.app.processEvents()
                page = self.window.pages.widget(page_no)
                positions.append(page.findChild(QLabel, object_name).mapTo(page, QPoint(0, 0)))
            self.assertEqual(positions[0], positions[1])
            self.assertTrue(self.window.version_panel._renderer.isValid())

    def test_update_ui_only_enables_for_newer_installable_release(self):
        for release, expected in (
            (Release(APP_VERSION, "", "", {"name": "Setup.exe"}), False),
            (Release("9.0.0", "", "", None), False),
            (Release("9.0.0", "", "", {"name": "Setup.exe"}), True),
        ):
            self.window._on_update_checked(release)
            self.assertEqual(self.window.btn_install_update.isEnabled(), expected)

    def test_update_installer_does_not_launch_with_unsaved_edits(self):
        self.add_invoices([16])
        self.window._split_left_invoices_into_stacks()
        with patch("ui.main_window.subprocess.Popen") as launch:
            self.window._on_installer_ready(Path("Setup.exe"))
        launch.assert_not_called()

    def test_source_update_download_is_kept_without_overwriting_source(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "HDU-Portable.exe"
            source.write_bytes(b"verified download")
            self.window.settings_path = root / "data" / "settings.json"
            with patch("ui.main_window.sys.frozen", False, create=True), patch("ui.main_window.QDesktopServices.openUrl") as open_url:
                self.window._on_installer_ready(source)
            self.assertEqual((root / "data" / "updates" / source.name).read_bytes(), source.read_bytes())
            open_url.assert_called_once()

    def test_frozen_update_starts_helper_then_closes(self):
        source = Path("HDU-Portable.exe")
        with patch("ui.main_window.sys.frozen", True, create=True), patch("ui.main_window.prepare_update", return_value=Path("plan.json")) as prepare, patch("ui.main_window.launch_helper") as launch, patch.object(self.window, "close") as close:
            self.window._on_installer_ready(source)
        prepare.assert_called_once()
        launch.assert_called_once_with(source, Path("plan.json"))
        close.assert_called_once()

    def test_settings_data_location_moves_and_survives_reload(self):
        from core.app_paths import load_settings, settings_path
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.window.settings_path = root / "source" / "settings.json"
            with patch("core.app_paths.RESOURCE_ROOT", root / "source"), patch("core.app_paths.sys.frozen", False, create=True), patch("ui.main_window.QFileDialog.getExistingDirectory", return_value=str(root / "new-data")):
                self.window._change_data_directory()
                self.assertEqual(self.window.settings_path, root / "new-data" / "settings.json")
                self.assertEqual(settings_path(), self.window.settings_path)
                self.assertEqual(self.window.edit_data_directory.text(), str(self.window.settings_path.parent))
                self.assertEqual(load_settings(), self.window.settings)

    def test_splash_uses_bundled_logo_and_shared_version(self):
        from ui.splash_screen import SplashScreen, LOGO_PATH
        splash = SplashScreen()
        self.assertTrue(LOGO_PATH.is_file())
        self.assertEqual(LOGO_PATH.parent.name, "assets")
        self.assertEqual(splash.version_label.text(), f"v{APP_VERSION}")
        self.assertTrue(splash.logo_label.renderer.isValid())
        splash.close()


if __name__ == "__main__":
    unittest.main()
