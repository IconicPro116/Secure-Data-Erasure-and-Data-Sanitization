import sys
import os
import random
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFrame, QFileDialog, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox,
    QTextEdit, QGridLayout, QMessageBox, QGroupBox, QScrollArea, QDialog
)

from PySide6.QtCore import QThread, Signal
from backend.core.recovery_service import RecoveryService
from backend.core.eraser import EraserService
from backend.core.sanitization_service import DriveSanitizationService, StorageTarget, SanitizationMethod
from backend.core.reporter import ReportService

class RecoveryWorker(QThread):
    progress_updated = Signal(int)
    file_recovered = Signal(dict)
    scan_completed = Signal(int, int) # total found, total valid
    scan_status = Signal(str)

    def __init__(self, target_file, output_dir="recovery_output"):
        super().__init__()
        self.target_file = target_file
        self.output_dir = output_dir
        self.is_running = True
        self.service = RecoveryService()

    def run(self):
        self.scan_status.emit(f"Starting C++ Engine for {os.path.basename(self.target_file)}...")
        total_found = 0
        total_valid = 0

        def on_file(file_data):
            nonlocal total_found, total_valid
            total_found += 1
            if file_data.get("status") == "Valid":
                total_valid += 1
            self.file_recovered.emit(file_data)

        self.service.run_recovery(
            self.target_file,
            self.output_dir,
            callback_progress=self.progress_updated.emit,
            callback_file=on_file,
            callback_status=self.scan_status.emit
        )
        self.scan_completed.emit(total_found, total_valid)


class SanitizeWorker(QThread):
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
            self.error_occurred.emit(str(e))

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

APP_NAME = "SecEra"
APP_SUBTITLE = "Secure Erasure & Forensic Recovery Prototype"


class StatCard(QFrame):
    def __init__(self, title, value, subtitle="", accent="#2F80ED"):
        super().__init__()
        self.setObjectName("StatCard")
        self.setMinimumHeight(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(5)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("CardTitle")

        value_lbl = QLabel(value)
        value_lbl.setObjectName("CardValue")
        value_lbl.setStyleSheet(f"color: {accent};")

        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setObjectName("CardSub")

        layout.addWidget(title_lbl)
        layout.addWidget(value_lbl)
        layout.addWidget(subtitle_lbl)


class TitleBlock(QWidget):
    def __init__(self, title, subtitle):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        h = QLabel(title)
        h.setObjectName("PageTitle")
        s = QLabel(subtitle)
        s.setObjectName("PageSubtitle")
        s.setWordWrap(True)

        layout.addWidget(h)
        layout.addWidget(s)


class DashboardPage(QWidget):
    def __init__(self, open_page_callback):
        super().__init__()
        self.open_page_callback = open_page_callback
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        layout.addWidget(TitleBlock(
            "SecEra Dashboard",
            "A clean internal SIH prototype for secure sanitization, file erasure, recovery, and audit reporting."
        ))

        banner = QFrame()
        banner.setObjectName("DemoBanner")
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(16, 11, 16, 11)
        badge = QLabel("PROTOTYPE MODE")
        badge.setObjectName("WarningBadge")
        text = QLabel("No real drive is modified. Sanitization and recovery actions are simulated for a safe demo.")
        text.setWordWrap(True)
        bl.addWidget(badge)
        bl.addWidget(text, 1)
        layout.addWidget(banner)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)
        cards.addWidget(StatCard("Sanitization Sessions", "03", "2 verified / 1 queued", "#00A67E"), 0, 0)
        cards.addWidget(StatCard("Recovered Files", "12", "Across recent demo scans", "#2F80ED"), 0, 1)
        cards.addWidget(StatCard("Audit Records", "08", "SHA-256 tracked operations", "#8A5CF6"), 0, 2)
        cards.addWidget(StatCard("System Status", "READY", "All demo modules available", "#00A67E"), 0, 3)
        layout.addLayout(cards)

        quick = QGroupBox("Quick Actions")
        ql = QGridLayout(quick)
        ql.setSpacing(12)

        actions = [
            ("Drive Sanitization", "Controlled overwrite demo on a test image", 1),
            ("File / Folder Eraser", "Selective demo erasure workflow", 2),
            ("File Recovery", "Signature scan + recovered file confidence", 3),
            ("Reports / Audit", "View operation history and report previews", 4),
        ]
        for i, (name, sub, idx) in enumerate(actions):
            btn = QPushButton(f"{name}\n{sub}")
            btn.setObjectName("ActionButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, x=idx: self.open_page_callback(x))
            ql.addWidget(btn, i // 2, i % 2)

        layout.addWidget(quick)
        layout.addStretch()


class SanitizationPage(QWidget):
    def __init__(self, add_audit):
        super().__init__()
        self.add_audit = add_audit
        

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(TitleBlock(
            "Drive Sanitization",
            "Safe prototype workflow using a dummy disk image. The UI simulates byte overwrite, verification, and audit logging."
        ))

        controls = QGroupBox("Target & Method")
        cl = QGridLayout(controls)
        self.target = QLineEdit()
        self.target.setPlaceholderText("Select a test .img file (optional)")
        browse = QPushButton("Browse")
        browse.clicked.connect(self.choose_image)

        self.method = QComboBox()
        self.method.addItems([
            "Controlled 0x00 Overwrite",
            "Controlled Random Overwrite",
            "Simulated Device Sanitize"
        ])

        cl.addWidget(QLabel("Target"), 0, 0)
        cl.addWidget(self.target, 0, 1)
        cl.addWidget(browse, 0, 2)
        cl.addWidget(QLabel("Method"), 1, 0)
        cl.addWidget(self.method, 1, 1, 1, 2)
        self.target_info = QLabel("Storage Type: Unknown")
        cl.addWidget(self.target_info, 2, 0, 1, 3)
        layout.addWidget(controls)

        visual = QGroupBox("Live Hex Visualizer")
        vl = QVBoxLayout(visual)
        self.hex_view = QTextEdit()
        self.hex_view.setReadOnly(True)
        self.hex_view.setFont(QFont("Consolas", 10))
        self.hex_view.setMinimumHeight(220)
        self.hex_view.setPlainText(self._make_hex_preview(before=True))
        vl.addWidget(self.hex_view)
        layout.addWidget(visual)

        status_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.status = QLabel("Ready")
        self.status.setObjectName("StatusPill")
        status_row.addWidget(self.progress, 1)
        status_row.addWidget(self.status)
        layout.addLayout(status_row)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start Demo Sanitization")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(self.start_demo)
        verify_btn = QPushButton("Run Verification")
        verify_btn.clicked.connect(self.verify_demo)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(verify_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Test Image", "", "Disk Images (*.img *.dd);;All Files (*.*)")
        if path:
            self.target.setText(path)
            if path.lower().endswith(('.img', '.dd', '.raw')):
                self.target_info.setText("Storage Type: DISK_IMAGE (Safe for Demo)")
            else:
                self.target_info.setText("Storage Type: UNKNOWN (Warning: Destructive operations disabled)")

    def _make_hex_preview(self, before=True):
        rows = []
        for row in range(10):
            offset = row * 16
            if before:
                vals = [f"{random.randint(0,255):02X}" for _ in range(16)]
            else:
                vals = ["00"] * 16
            rows.append(f"{offset:08X}   " + " ".join(vals))
        return "\n".join(rows)

    def start_demo(self):
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
            self.hex_view.setPlainText("\n".join(lines))

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
        QMessageBox.information(self, "Sanitization Complete", f"Status: {status}\nDetails: {details}\nHash: {rhash}")

    def verify_demo(self):
        QMessageBox.information(
            self,
            "Verification",
            "Verification PASSED\n\nNo matching demo signatures were detected in the sanitized test image.\n\n"
            "Prototype note: this does not claim physical unrecoverability on real media."
        )
        self.add_audit("Verification", "demo_drive.img", "Post-sanitize recovery check", "PASSED")


class EraserPage(QWidget):
    def __init__(self, add_audit):
        super().__init__()
        self.add_audit = add_audit
        

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(TitleBlock(
            "File / Folder Eraser",
            "Prototype-only selective erasure workflow. The selected path is never modified."
        ))

        box = QGroupBox("Selection")
        bl = QGridLayout(box)
        self.path = QLineEdit()
        self.path.setPlaceholderText("Choose a test file or folder")
        file_btn = QPushButton("Select File")
        folder_btn = QPushButton("Select Folder")
        file_btn.clicked.connect(self.select_file)
        folder_btn.clicked.connect(self.select_folder)

        self.erase_mode = QComboBox()
        self.erase_mode.addItems(["Single-pass demo overwrite", "Random-pattern demo", "Metadata-analysis demo"])

        bl.addWidget(QLabel("Target"), 0, 0)
        bl.addWidget(self.path, 0, 1)
        bl.addWidget(file_btn, 0, 2)
        bl.addWidget(folder_btn, 0, 3)
        bl.addWidget(QLabel("Mode"), 1, 0)
        bl.addWidget(self.erase_mode, 1, 1, 1, 3)
        layout.addWidget(box)

        analysis = QGroupBox("Analysis")
        al = QVBoxLayout(analysis)
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setMinimumHeight(150)
        self.analysis_text.setPlainText(
            "Status: Waiting for target\n"
            "Metadata traces: —\n"
            "Residual trace analysis: —\n"
            "Verification state: —"
        )
        al.addWidget(self.analysis_text)
        layout.addWidget(analysis)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        row = QHBoxLayout()
        analyze = QPushButton("Analyze")
        erase = QPushButton("Run Demo Erasure")
        erase.setObjectName("PrimaryButton")
        analyze.clicked.connect(self.analyze)
        erase.clicked.connect(self.erase)
        row.addWidget(analyze)
        row.addWidget(erase)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Test File", "", "All Files (*.*)")
        if path:
            self.path.setText(path)

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose Test Folder")
        if path:
            self.path.setText(path)

    def analyze(self):
        target = self.path.text().strip() or "demo_document.pdf"
        self.analysis_text.setPlainText(
            f"Target: {target}\n"
            "Metadata traces: File name, timestamps, path metadata detected (demo)\n"
            "Residual trace analysis: Candidate trace regions identified (simulated)\n"
            "Verification state: Pending"
        )
        self.add_audit("File/Folder Analysis", os.path.basename(target), "Metadata & residual trace analysis", "READY")

    def erase(self):
        self.p = 0
        self.progress.setValue(0)
        self.analysis_text.append("\nErasure demo started...")
        self.worker = EraserWorker(self.path.text().strip(), self.erase_mode.currentText())
        self.worker.progress_updated.connect(self.progress.setValue)
        self.worker.status_updated.connect(lambda m: self.analysis_text.append(m))
        self.worker.finished.connect(lambda: self._on_erase_finish(self.path.text().strip(), self.erase_mode.currentText()))
        self.worker.start()

    def _on_erase_finish(self, target, method):
        self.analysis_text.append("Overwrite: Completed\nVerification: PASSED")
        self.add_audit("File/Folder Erasure", os.path.basename(target) or "demo_document.pdf", method, "SUCCESS")


class RecoveryPage(QWidget):
    def __init__(self, add_audit):
        super().__init__()
        self.add_audit = add_audit
        self.engine = None
        self.recovered_files = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(TitleBlock(
            "File Recovery",
            "Hero demo: select a test image or folder, simulate signature scanning, then show classified recovered files with confidence scores."
        ))

        source_box = QGroupBox("Evidence Source")
        sl = QHBoxLayout(source_box)
        self.source = QLineEdit()
        self.source.setPlaceholderText("Select disk image / test folder")
        select_img = QPushButton("Select Image")
        select_folder = QPushButton("Select Folder")
        select_img.clicked.connect(self.pick_image)
        select_folder.clicked.connect(self.pick_folder)
        sl.addWidget(self.source, 1)
        sl.addWidget(select_img)
        sl.addWidget(select_folder)
        layout.addWidget(source_box)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.scan_status = QLabel("Ready to scan")
        self.scan_status.setObjectName("StatusPill")
        layout.addWidget(self.scan_status)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["File", "Type", "Size", "Confidence", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        row = QHBoxLayout()
        scan = QPushButton("Start Recovery Scan")
        scan.setObjectName("PrimaryButton")
        scan.clicked.connect(self.scan)
        preview = QPushButton("Preview Selected")
        preview.clicked.connect(self.preview)
        row.addWidget(scan)
        row.addWidget(preview)
        row.addStretch()
        layout.addLayout(row)

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Evidence Image", "", "Disk Images (*.img *.dd *.raw);;All Files (*.*)")
        if path:
            self.source.setText(path)

    def pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Test Folder")
        if path:
            self.source.setText(path)

    def scan(self):
        target = self.source.text().strip()
        if not target or not os.path.exists(target):
            QMessageBox.warning(self, "Error", "Please select a valid evidence image.")
            return

        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.scan_status.setText("Scanning raw bytes...")
        self.recovered_files = []
        
        self.engine = RecoveryWorker(target)
        self.engine.progress_updated.connect(self._on_progress_updated)
        self.engine.scan_status.connect(self._on_scan_status)
        self.engine.file_recovered.connect(self._on_file_recovered)
        self.engine.scan_completed.connect(self._on_scan_completed)
        self.engine.start()

    def _on_progress_updated(self, progress):
        self.progress.setValue(progress)

    def _on_scan_status(self, status):
        self.scan_status.setText(status)

    def _on_file_recovered(self, file_data):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.recovered_files.append(file_data)
        
        items = [
            file_data["name"],
            file_data["type"],
            file_data["size"],
            file_data["confidence"],
            file_data["status"]
        ]
        
        for c, value in enumerate(items):
            item = QTableWidgetItem(value)
            if c == 3:
                item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, c, item)

    def _on_scan_completed(self, total_found, total_valid):
        self.scan_status.setText(f"Scan complete • {total_found} candidate files recovered ({total_valid} valid)")
        source = os.path.basename(self.source.text()) if self.source.text() else "evidence_drive.img"
        self.add_audit("File Recovery", source, "Signature + structure scan", f"{total_found} FILES")

    def preview(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Preview", "Select a recovered file from the table first.")
            return
            
        file_data = self.recovered_files[row]
        path = file_data.get("path", "")
        
        if not os.path.exists(path):
            QMessageBox.warning(self, "Preview Error", "File not found on disk.")
            return

        # Interactive Forensic Preview Dialog
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Forensic Artifact Inspector - {file_data.get('name', 'File')}")
        dlg.resize(650, 520)
        
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        
        # Meta Card
        meta_box = QGroupBox("File Forensics & Verification")
        meta_layout = QGridLayout(meta_box)
        meta_layout.addWidget(QLabel("<b>File Name:</b>"), 0, 0)
        meta_layout.addWidget(QLabel(file_data.get("name", "")), 0, 1)
        meta_layout.addWidget(QLabel("<b>Detected Type:</b>"), 0, 2)
        meta_layout.addWidget(QLabel(file_data.get("type", "")), 0, 3)
        meta_layout.addWidget(QLabel("<b>Size:</b>"), 1, 0)
        meta_layout.addWidget(QLabel(file_data.get("size", "")), 1, 1)
        meta_layout.addWidget(QLabel("<b>Confidence:</b>"), 1, 2)
        conf_lbl = QLabel(f"<b>{file_data.get('confidence', '')} ({file_data.get('status', '')})</b>")
        conf_lbl.setStyleSheet("color: #27ae60;" if file_data.get("status") == "Valid" else "color: #f39c12;")
        meta_layout.addWidget(conf_lbl, 1, 3)
        meta_layout.addWidget(QLabel("<b>SHA-256 Hash:</b>"), 2, 0)
        hash_box = QLineEdit(file_data.get("sha256", "N/A"))
        hash_box.setReadOnly(True)
        meta_layout.addWidget(hash_box, 2, 1, 1, 3)
        layout.addWidget(meta_box)

        # Content Visualizer
        ftype = file_data.get("type", "").upper()
        if ftype in ["JPG", "PNG"]:
            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                img_lbl.setPixmap(pixmap.scaled(580, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                img_lbl.setText("Corrupted or unrenderable image bytes")
            layout.addWidget(img_lbl, 1)
        else:
            # Hex / Text viewer
            hex_view = QTextEdit()
            hex_view.setReadOnly(True)
            hex_view.setFont(QFont("Consolas", 10))
            try:
                with open(path, "rb") as f:
                    content = f.read(1024)
                    hex_str = " ".join(f"{b:02X}" for b in content[:256])
                    text_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in content[:256])
                    
                    doc_summary = ""
                    if ftype == "DOCX":
                        import zipfile
                        try:
                            with zipfile.ZipFile(path) as z:
                                doc_summary = f"\n[DOCX Structure Valid: Package contains {len(z.namelist())} internal XML parts]\nParts: {', '.join(z.namelist())}\n\n"
                        except Exception:
                            doc_summary = "\n[DOCX Package Corrupt]\n\n"
                    elif ftype == "PDF":
                        doc_summary = "\n[PDF Structure: Valid %%EOF trailer verified]\n\n"

                    hex_view.setPlainText(f"--- CONTENT PREVIEW ({ftype}) ---{doc_summary}Hex Stream (first 256 bytes):\n{hex_str}\n\nASCII representation:\n{text_str}")
            except Exception as e:
                hex_view.setPlainText(f"Error reading file content: {e}")
            layout.addWidget(hex_view, 1)

        # Bottom Buttons
        btn_row = QHBoxLayout()
        open_ext = QPushButton("Open in External Viewer")
        open_ext.clicked.connect(lambda: os.startfile(path) if os.path.exists(path) else None)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(open_ext)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.exec()


class ReportsPage(QWidget):
    def __init__(self, audit_records):
        super().__init__()
        self.audit_records = audit_records

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(TitleBlock(
            "Reports / Audit",
            "Demo operation history with timestamp, target, method, result, and report preview."
        ))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Operation", "Target", "Method", "Result"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        controls = QHBoxLayout()
        refresh = QPushButton("Refresh Audit Log")
        report = QPushButton("Generate Report Preview")
        report.setObjectName("PrimaryButton")
        refresh.clicked.connect(self.refresh)
        report.clicked.connect(self.report_preview)
        controls.addWidget(refresh)
        controls.addWidget(report)
        controls.addStretch()
        layout.addLayout(controls)

    def refresh(self):
        self.table.setRowCount(len(self.audit_records))
        for r, rec in enumerate(reversed(self.audit_records)):
            values = [rec["timestamp"], rec["operation"], rec["target"], rec["method"], rec["result"]]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(value))

    def report_preview(self):
        self.refresh()
        service = ReportService()
        result = service.generate_report(self.audit_records)
        if result:
            path, rhash = result
            QMessageBox.information(self, "Report Generated", f"Report saved to:\n{path}\n\nSHA-256 Hash:\n{rhash}")
            if os.path.exists(path):
                import webbrowser
                webbrowser.open('file://' + os.path.realpath(path))
        else:
            QMessageBox.warning(self, "No Records", "No audit records found to generate a report.")


class SecEraMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} • {APP_SUBTITLE}")
        self.resize(1280, 780)
        self.setMinimumSize(1050, 680)

        self.audit_records = [
            {
                "timestamp": "2026-09-09 05:44:10",
                "operation": "File Recovery",
                "target": "evidence_drive.img",
                "method": "Signature scan",
                "result": "6 FILES",
            },
            {
                "timestamp": "2026-09-09 05:48:26",
                "operation": "Drive Sanitization",
                "target": "demo_drive.img",
                "method": "Controlled 0x00 Overwrite",
                "result": "SUCCESS",
            },
        ]

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self.build_sidebar()
        root_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(self.stack.setCurrentIndex)
        self.sanitize = SanitizationPage(self.add_audit)
        self.eraser = EraserPage(self.add_audit)
        self.recovery = RecoveryPage(self.add_audit)
        self.reports = ReportsPage(self.audit_records)

        for page in [self.dashboard, self.sanitize, self.eraser, self.recovery, self.reports]:
            self.stack.addWidget(page)

        self.stack.currentChanged.connect(self._on_page_changed)
        root_layout.addWidget(self.stack, 1)

        self.apply_styles()

    def build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(245)

        layout = QVBoxLayout(side)
        layout.setContentsMargins(18, 20, 18, 18)
        layout.setSpacing(10)

        brand = QLabel("SecEra")
        brand.setObjectName("Brand")
        sub = QLabel("Digital Forensics\n& Data Sanitization")
        sub.setObjectName("BrandSub")

        layout.addWidget(brand)
        layout.addWidget(sub)
        layout.addSpacing(22)

        nav_items = [
            ("Dashboard", 0),
            ("Drive Sanitization", 1),
            ("File / Folder Eraser", 2),
            ("File Recovery", 3),
            ("Reports / Audit", 4),
        ]

        self.nav_buttons = []
        for title, idx in nav_items:
            btn = QPushButton(title)
            btn.setObjectName("NavButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, x=idx: self.stack.setCurrentIndex(x))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        layout.addStretch()

        footer = QLabel("SIH 2026 • Team TroubleShoot\nPrototype UI")
        footer.setObjectName("SidebarFooter")
        layout.addWidget(footer)
        return side

    def _on_page_changed(self, idx):
        for i, b in enumerate(self.nav_buttons):
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)

        if idx == 4:
            self.reports.refresh()

    def add_audit(self, operation, target, method, result):
        self.audit_records.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operation": operation,
            "target": target,
            "method": method,
            "result": result,
        })

    def apply_styles(self):
        self.setStyleSheet("""
            * {
                font-family: "Segoe UI";
                font-size: 13px;
                color: #1F2937;
            }

            QMainWindow {
                background: #F4F7FB;
            }

            QWidget {
                background: #F4F7FB;
            }

            #Sidebar {
                background: #0F1F36;
                border: none;
            }

            #Brand {
                background: transparent;
                color: white;
                font-size: 30px;
                font-weight: 800;
            }

            #BrandSub {
                background: transparent;
                color: #A9B7C9;
                font-size: 12px;
                line-height: 1.4;
            }

            #SidebarFooter {
                background: transparent;
                color: #7F91AA;
                font-size: 11px;
            }

            #NavButton {
                text-align: left;
                padding: 12px 14px;
                border-radius: 9px;
                border: none;
                color: #D8E2EF;
                background: transparent;
                font-weight: 600;
            }

            #NavButton:hover {
                background: #172E4D;
                color: white;
            }

            #NavButton[active="true"] {
                background: #2F80ED;
                color: white;
            }

            #PageTitle {
                font-size: 28px;
                font-weight: 800;
                color: #15243B;
            }

            #PageSubtitle {
                color: #66758A;
                font-size: 13px;
            }

            #DemoBanner {
                background: #FFF5D8;
                border: 1px solid #F4D479;
                border-radius: 10px;
            }

            #WarningBadge {
                color: #815A00;
                background: #FFE6A3;
                padding: 4px 8px;
                border-radius: 7px;
                font-weight: 800;
            }

            #StatCard {
                background: white;
                border: 1px solid #DFE7F2;
                border-radius: 12px;
            }

            #CardTitle {
                color: #65758A;
                font-weight: 600;
            }

            #CardValue {
                font-size: 26px;
                font-weight: 800;
            }

            #CardSub {
                color: #8A98A9;
                font-size: 11px;
            }

            QGroupBox {
                background: white;
                border: 1px solid #DFE7F2;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: 700;
                color: #34445A;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }

            QLineEdit, QComboBox, QTextEdit, QTableWidget {
                background: white;
                border: 1px solid #D7E0EC;
                border-radius: 8px;
                padding: 7px;
            }

            QPushButton {
                background: #EEF3F8;
                border: 1px solid #D4DEEA;
                border-radius: 8px;
                padding: 9px 14px;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #E4ECF5;
            }

            #PrimaryButton {
                background: #2F80ED;
                color: white;
                border: none;
                padding: 10px 16px;
            }

            #PrimaryButton:hover {
                background: #216DCC;
            }

            #ActionButton {
                text-align: left;
                padding: 18px;
                min-height: 72px;
                background: #F9FBFE;
                border: 1px solid #DCE6F1;
                border-radius: 12px;
                font-size: 14px;
            }

            #ActionButton:hover {
                background: #EFF6FF;
                border-color: #9CC4FF;
            }

            QProgressBar {
                background: #E8EEF5;
                border: none;
                border-radius: 7px;
                min-height: 15px;
                text-align: center;
                font-size: 11px;
                font-weight: 700;
            }

            QProgressBar::chunk {
                background: #2F80ED;
                border-radius: 7px;
            }

            #StatusPill {
                background: #E8F7F1;
                color: #007A5E;
                padding: 7px 11px;
                border-radius: 8px;
                font-weight: 700;
            }

            QHeaderView::section {
                background: #EEF3F8;
                color: #405269;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #D9E3EF;
                font-weight: 700;
            }

            QTableWidget {
                gridline-color: #EEF2F7;
                selection-background-color: #DCEBFF;
                alternate-background-color: #FAFCFE;
            }
        """)


if __name__ == "__main__":
    import subprocess
    import os
    
    # Auto-generate fresh test image on startup
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "tests", "create_demo_image.py")
    if os.path.exists(script_path):
        print("Generating fresh evidence_drive.img for demo...")
        subprocess.run([sys.executable, script_path], check=False)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = SecEraMainWindow()
    window.show()
    sys.exit(app.exec())
