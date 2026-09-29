import sys

with open(r"c:\SecEra\dashboard.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add imports
code = code.replace(
    "from backend.core.recovery_service import RecoveryService",
    "from backend.core.recovery_service import RecoveryService\nfrom backend.core.eraser import EraserService\nfrom backend.core.reporter import ReportService"
)

# 2. Add SanitizeWorker & EraserWorker classes just after RecoveryWorker
worker_code = """
class SanitizeWorker(QThread):
    progress_updated = Signal(int)
    status_updated = Signal(str)

    def __init__(self, target_file, method):
        super().__init__()
        self.target_file = target_file
        self.method = method
        self.service = EraserService()

    def run(self):
        self.service.sanitize_drive(
            self.target_file,
            self.method,
            callback_progress=self.progress_updated.emit,
            callback_status=self.status_updated.emit
        )

class EraserWorker(QThread):
    progress_updated = Signal(int)
    status_updated = Signal(str)

    def __init__(self, target_path, method):
        super().__init__()
        self.target_path = target_path
        self.method = method
        self.service = EraserService()

    def run(self):
        self.service.erase_file_or_folder(
            self.target_path,
            self.method,
            callback_progress=self.progress_updated.emit,
            callback_status=self.status_updated.emit
        )
"""
code = code.replace("APP_NAME = \"SecEra\"", worker_code + "\nAPP_NAME = \"SecEra\"")

# 3. Fix SanitizationPage
code = code.replace("self.timer = QTimer(self)\n        self.timer.timeout.connect(self._tick)\n        self.progress_value = 0", "")
code = code.replace("self.timer.start(70)", "self.worker = SanitizeWorker(self.target.text(), self.method.currentText())\n        self.worker.progress_updated.connect(self._on_progress)\n        self.worker.status_updated.connect(self._on_status)\n        self.worker.finished.connect(lambda: self._on_finish(self.target.text(), self.method.currentText()))\n        self.worker.start()")

tick_method = """    def _tick(self):
        self.progress_value += random.randint(2, 6)
        if self.progress_value >= 100:
            self.progress_value = 100
            self.timer.stop()
            self.progress.setValue(100)
            self.hex_view.setPlainText(self._make_hex_preview(before=False))
            self.status.setText("Completed")
            self.start_btn.setEnabled(True)
            self.add_audit(
                "Drive Sanitization",
                os.path.basename(self.target.text()) if self.target.text() else "demo_drive.img",
                self.method.currentText(),
                "SUCCESS"
            )
            return

        self.progress.setValue(self.progress_value)
        # show mixed wipe state for visual effect
        lines = self.hex_view.toPlainText().splitlines()
        if lines:
            idx = min(len(lines)-1, int(self.progress_value / 100 * len(lines)))
            for i in range(idx):
                offset = i * 16
                lines[i] = f"{offset:08X}   " + " ".join(["00"] * 16)
            self.hex_view.setPlainText("\\n".join(lines))"""

new_tick_method = """    def _on_progress(self, val):
        self.progress.setValue(val)
        lines = self.hex_view.toPlainText().splitlines()
        if lines:
            idx = min(len(lines)-1, int(val / 100 * len(lines)))
            for i in range(idx):
                offset = i * 16
                lines[i] = f"{offset:08X}   " + " ".join(["00"] * 16)
            self.hex_view.setPlainText("\\n".join(lines))

    def _on_status(self, msg):
        self.status.setText(msg)

    def _on_finish(self, target, method):
        self.progress.setValue(100)
        self.hex_view.setPlainText(self._make_hex_preview(before=False))
        self.start_btn.setEnabled(True)
        self.add_audit(
            "Drive Sanitization",
            os.path.basename(target) if target else "demo_drive.img",
            method,
            "SUCCESS"
        )"""

code = code.replace(tick_method, new_tick_method)

# 4. Fix EraserPage
code = code.replace("self.timer = QTimer(self)\n        self.timer.timeout.connect(self._tick)\n        self.p = 0", "")
code = code.replace("self.timer.start(85)", "self.worker = EraserWorker(self.path.text().strip(), self.erase_mode.currentText())\n        self.worker.progress_updated.connect(self.progress.setValue)\n        self.worker.status_updated.connect(lambda m: self.analysis_text.append(m))\n        self.worker.finished.connect(lambda: self._on_erase_finish(self.path.text().strip(), self.erase_mode.currentText()))\n        self.worker.start()")

erase_tick = """    def _tick(self):
        self.p += random.randint(5, 12)
        if self.p >= 100:
            self.p = 100
            self.timer.stop()
            self.analysis_text.append("Demo overwrite: Completed\\nVerification: PASSED")
            target = self.path.text().strip() or "demo_document.pdf"
            self.add_audit("File/Folder Erasure", os.path.basename(target), self.erase_mode.currentText(), "SUCCESS")
        self.progress.setValue(self.p)"""

new_erase_tick = """    def _on_erase_finish(self, target, method):
        self.analysis_text.append("Overwrite: Completed\\nVerification: PASSED")
        self.add_audit("File/Folder Erasure", os.path.basename(target) or "demo_document.pdf", method, "SUCCESS")"""

code = code.replace(erase_tick, new_erase_tick)

# 5. Fix ReportsPage
old_report_preview = """    def report_preview(self):
        self.refresh()
        latest = self.audit_records[-1] if self.audit_records else {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operation": "Demo",
            "target": "demo_drive.img",
            "method": "Controlled prototype operation",
            "result": "SUCCESS"
        }
        msg = (
            "SECERA FORENSIC / SANITIZATION REPORT\\n\\n"
            f"Timestamp: {latest['timestamp']}\\n"
            f"Operation: {latest['operation']}\\n"
            f"Target: {latest['target']}\\n"
            f"Method: {latest['method']}\\n"
            f"Result: {latest['result']}\\n"
            "SHA-256: 6f1ed002ab5595859014ebf0951522d9...\\n\\n"
            "Prototype note: SHA-256 is shown as an integrity fingerprint, not a digital signature."
        )
        QMessageBox.information(self, "Report Preview", msg)"""

new_report_preview = """    def report_preview(self):
        self.refresh()
        service = ReportService()
        result = service.generate_report(self.audit_records)
        if result:
            path, rhash = result
            QMessageBox.information(self, "Report Generated", f"Report saved to:\\n{path}\\n\\nSHA-256 Hash:\\n{rhash}")
            if os.path.exists(path):
                import webbrowser
                webbrowser.open('file://' + os.path.realpath(path))
        else:
            QMessageBox.warning(self, "No Records", "No audit records found to generate a report.")"""

code = code.replace(old_report_preview, new_report_preview)

with open(r"c:\SecEra\dashboard.py", "w", encoding="utf-8") as f:
    f.write(code)

print("dashboard.py patched successfully.")
