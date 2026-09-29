import sys
import re

with open(r"c:\SecEra\dashboard.py", "r", encoding="utf-8") as f:
    code = f.read()

# Replace import
code = code.replace(
    "from backend.core.eraser import EraserService",
    "from backend.core.eraser import EraserService\nfrom backend.core.sanitization_service import DriveSanitizationService, StorageTarget, SanitizationMethod"
)

# Find old SanitizeWorker
old_worker = """class SanitizeWorker(QThread):
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
        )"""

new_worker = """class SanitizeWorker(QThread):
    progress_updated = Signal(int)
    stage_updated = Signal(str)
    result_ready = Signal(str, str, str)
    error_occurred = Signal(str)

    def __init__(self, target_file, ui_method):
        super().__init__()
        self.target_file = target_file
        self.ui_method = ui_method
        self.service = DriveSanitizationService()

    def request_cancel(self):
        self.service.request_cancel()

    def run(self):
        try:
            target = self.service.validate_target(self.target_file)
            method = self.service.select_method(target, self.ui_method)
            
            class Callbacks:
                def __init__(self, worker):
                    self.w = worker
                def progress(self, val):
                    self.w.progress_updated.emit(val)
                def stage(self, stg):
                    self.w.stage_updated.emit(stg)
            
            cb = Callbacks(self)
            
            self.service.execute_sanitization(target, method, cb)
            status, details, rhash = self.service.verify_sanitization(target, method, cb)
            self.result_ready.emit(status, details, rhash)
            
        except Exception as e:
            self.error_occurred.emit(str(e))"""

code = code.replace(old_worker, new_worker)


old_start = """    def start_demo(self):
        self.progress_value = 0
        self.progress.setValue(0)
        self.status.setText("Sanitizing...")
        self.start_btn.setEnabled(False)
        self.worker = SanitizeWorker(self.target.text(), self.method.currentText())
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.status_updated.connect(self._on_status)
        self.worker.finished.connect(lambda: self._on_finish(self.target.text(), self.method.currentText()))
        self.worker.start()

    def _on_progress(self, val):
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


new_start = """    def start_demo(self):
        if self.start_btn.text() == "Cancel":
            if hasattr(self, 'worker') and self.worker.isRunning():
                self.worker.request_cancel()
                self.start_btn.setEnabled(False)
                self.status.setText("Cancelling...")
            return

        self.progress.setValue(0)
        self.status.setText("Initializing...")
        self.start_btn.setText("Cancel")
        self.worker = SanitizeWorker(self.target.text(), self.method.currentText())
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.stage_updated.connect(self._on_status)
        self.worker.result_ready.connect(lambda s, d, h: self._on_result(self.target.text(), self.method.currentText(), s, d, h))
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, val):
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

    def _on_error(self, err):
        self.start_btn.setText("Start Demo Sanitization")
        self.start_btn.setEnabled(True)
        self.status.setText(f"Error: {err}")
        QMessageBox.warning(self, "Sanitization Error", str(err))
        self.add_audit("Drive Sanitization", os.path.basename(self.target.text()), self.method.currentText(), "FAIL")

    def _on_result(self, target, method, status, details, rhash):
        self.progress.setValue(100)
        self.hex_view.setPlainText(self._make_hex_preview(before=False))
        self.start_btn.setText("Start Demo Sanitization")
        self.start_btn.setEnabled(True)
        self.status.setText(f"Completed - Verification: {status}")
        self.add_audit(
            "Drive Sanitization",
            os.path.basename(target) if target else "demo_drive.img",
            method,
            f"SUCCESS (Hash: {rhash[:8]}...)" if status == "PASS" else "VERIFY FAIL"
        )
        QMessageBox.information(self, "Sanitization Complete", f"Status: {status}\\nDetails: {details}\\nHash: {rhash}")"""

code = code.replace(old_start, new_start)

# Add clear target info display to UI
# We need to insert a label in the controls box
controls_replace_1 = """        cl.addWidget(self.method, 1, 1, 1, 2)
        layout.addWidget(controls)"""

controls_replace_2 = """        cl.addWidget(self.method, 1, 1, 1, 2)
        self.target_info = QLabel("Storage Type: Unknown")
        cl.addWidget(self.target_info, 2, 0, 1, 3)
        layout.addWidget(controls)"""

code = code.replace(controls_replace_1, controls_replace_2)

# Update choose_image to update label
choose_image_old = """    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Test Image", "", "Disk Images (*.img *.dd);;All Files (*.*)")
        if path:
            self.target.setText(path)"""

choose_image_new = """    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Test Image", "", "Disk Images (*.img *.dd);;All Files (*.*)")
        if path:
            self.target.setText(path)
            if path.lower().endswith(('.img', '.dd', '.raw')):
                self.target_info.setText("Storage Type: DISK_IMAGE (Safe for Demo)")
            else:
                self.target_info.setText("Storage Type: UNKNOWN (Warning: Destructive operations disabled)")"""

code = code.replace(choose_image_old, choose_image_new)

with open(r"c:\SecEra\dashboard.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Dashboard successfully patched with DriveSanitizationService.")
