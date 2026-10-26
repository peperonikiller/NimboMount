"""PySide6 desktop + tray front end."""
import sys
import time
import threading
from pathlib import Path
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QLockFile
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSystemTrayIcon,
    QVBoxLayout, QWidget, QMenu, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QTextEdit, QGroupBox, QScrollArea, QFrame, QProgressBar)
from .startup import set_login_startup
from .core import (APP, IS_WIN, BASE, CACHE, MountEngine, Settings, available_letters,
                   default_point, get_password, save_password, get_session, forget_session)


class Signals(QObject):
    result = Signal(str, bool, str)
    transfers = Signal(object, str)


def asset(name):
    # PyInstaller --one-dir bundles data under _internal (sys._MEIPASS).
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    path = base / "nimbomount" / "assets" / name
    if not path.exists():
        path = Path(__file__).resolve().parent / "assets" / name
    return str(path)


def tray_icon(color):
    """High-contrast tray glyph with an easily seen connection-status dot."""
    pix = QPixmap(asset("tray.png"))
    if pix.isNull():
        pix = QPixmap(64, 64)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.fillRect(7, 7, 50, 50, QColor("#168cff"))
        painter.end()
    pix = pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#111827"))
    painter.setBrush(QColor(color))
    painter.drawEllipse(43, 43, 17, 17)
    painter.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings.load()
        self.engine = MountEngine()
        self.events = Signals()
        self.events.result.connect(self._result)
        self.events.transfers.connect(self._transfers)
        self.queue_polling = False
        self.queue_ids = []
        self.last_transfer_poll = 0
        self.busy = False
        self.failures = 0
        self.connected_once = False
        self.next_retry = 0
        self.manual_disconnect = False
        self.shutting_down = False
        self.setWindowTitle("NimboMount — MEGA")
        self.setWindowIcon(QIcon(asset("NimboMount.ico")))
        self.setMinimumSize(750, 620)
        self.resize(840, 750)
        self.mount_started_at = 0.0
        self.mount_probe_active = False
        self.mount_deadline_seconds = 40
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        header = QLabel("NimboMount  /  MEGA")
        header.setObjectName("brand")
        layout.addWidget(header)
        sub = QLabel("Your cloud, mounted locally.  Secure • Monitored • Recoverable")
        layout.addWidget(sub)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        drive_scroll = QScrollArea()
        drive_scroll.setWidgetResizable(True)
        drive_scroll.setFrameShape(QFrame.Shape.NoFrame)
        drive_panel = QWidget()
        drive_layout = QVBoxLayout(drive_panel)
        drive_layout.setContentsMargins(8, 16, 8, 16)
        drive_layout.setSpacing(12)
        drive_scroll.setWidget(drive_panel)
        self.tabs.addTab(drive_scroll, "  Drive  ")
        transfers_panel = QWidget()
        transfers_layout = QVBoxLayout(transfers_panel)
        transfers_layout.setContentsMargins(12, 18, 12, 14)
        self.tabs.addTab(transfers_panel, "  Transfers  ")
        diag_panel = QWidget()
        diag_layout = QVBoxLayout(diag_panel)
        diag_layout.setContentsMargins(12, 18, 12, 14)
        self.tabs.addTab(diag_panel, "  Diagnostics  ")
        account_group = QGroupBox("MEGA account")
        account_layout = QVBoxLayout(account_group)
        form = QFormLayout()
        form.setSpacing(11)
        self.email = QLineEdit(self.settings.email)
        self.email.setPlaceholderText("you@example.com")
        form.addRow("MEGA email", self.email)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("MEGA account password")
        form.addRow("Password", self.password)
        self.otp = QLineEdit()
        self.otp.setPlaceholderText("Six-digit code from your authenticator")
        self.otp.setMaxLength(6)
        self.otp.setEchoMode(QLineEdit.EchoMode.Password)
        self.otp_label = QLabel("Authenticator code")
        self.otp_label.setBuddy(self.otp)
        form.addRow(self.otp_label, self.otp)
        self.otp_label.hide()
        self.otp.hide()
        self.auth_hint = QLabel("Step 1: Enter your MEGA email and password, then continue.")
        self.auth_hint.setWordWrap(True)
        account_layout.addWidget(self.auth_hint)
        self.auth_stage = False
        self.pending_login = None
        self.remember = QCheckBox("Save password in operating-system credential vault")
        account_layout.addLayout(form)
        account_layout.addWidget(self.remember)
        self.force_login = QCheckBox("Force fresh login (ignore existing saved session)")
        account_layout.addWidget(self.force_login)
        drive_layout.addWidget(account_group)
        destination_group = QGroupBox("Mount location")
        destination_layout = QVBoxLayout(destination_group)
        row = QHBoxLayout()
        self.point = QComboBox() if IS_WIN else QLineEdit()
        if IS_WIN:
            self.point.setEditable(False)
            self.refresh_letters()
            self.point.addItem(self.settings.mountpoint or default_point()) if not self.point.count() else None
            index = self.point.findText(self.settings.mountpoint or default_point())
            if index >= 0:
                self.point.setCurrentIndex(index)
        else:
            self.point.setText(self.settings.mountpoint or default_point())
        row.addWidget(self.point)
        if not IS_WIN:
            browse = QPushButton("Browse")
            browse.clicked.connect(self.browse)
            row.addWidget(browse)
        form2 = QFormLayout()
        form2.addRow("Drive letter" if IS_WIN else "Mount directory", row)
        destination_layout.addLayout(form2)
        drive_layout.addWidget(destination_group)
        options_group = QGroupBox("Preferences")
        options_layout = QVBoxLayout(options_group)
        self.reconnect = QCheckBox("Automatically reconnect after failed mount")
        self.reconnect.setChecked(self.settings.auto_reconnect)
        options_layout.addWidget(self.reconnect)
        self.write_cache_checkbox = QCheckBox("Enable local file caching (recommended)")
        self.write_cache_checkbox.setChecked(self.settings.write_cache_enabled)
        self.write_cache_checkbox.setToolTip("Enabled: offline staging and retryable uploads. Disabled: direct remote writes; failed uploads cannot be retried.")
        self.write_cache_checkbox.toggled.connect(self.change_cache_mode)
        options_layout.addWidget(self.write_cache_checkbox)
        self.cache_mode_notice = QLabel("Cache mode changes remount the drive and may interrupt open files.")
        self.cache_mode_notice.setWordWrap(True)
        options_layout.addWidget(self.cache_mode_notice)
        self.startup = QCheckBox("Launch and mount automatically at login (requires saved MEGA session)")
        self.startup.setChecked(self.settings.mount_at_login)
        self.startup.toggled.connect(self.configure_startup)
        options_layout.addWidget(self.startup)
        drive_layout.addWidget(options_group)
        self.status = QLabel("● Disconnected")
        self.status.setStyleSheet("color:#ffbb70; font-size: 14px; font-weight: bold")
        drive_layout.addWidget(self.status)
        self.details = QLabel("rclone and WinFsp are included with the Windows installer." if IS_WIN else "Install rclone and FUSE3 before connecting.")
        self.details.setWordWrap(True)
        drive_layout.addWidget(self.details)
        self.mount_activity = QProgressBar()
        self.mount_activity.setRange(0, 0)
        self.mount_activity.setTextVisible(False)
        self.mount_activity.setFixedHeight(5)
        self.mount_activity.hide()
        drive_layout.addWidget(self.mount_activity)
        buttons = QHBoxLayout()
        self.connect_btn = QPushButton("Continue to sign in / Connect")
        self.connect_btn.clicked.connect(self.connect)
        self.disconnect_btn = QPushButton("Unmount")
        self.disconnect_btn.clicked.connect(self.disconnect)
        buttons.addWidget(self.connect_btn)
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._back_to_credentials)
        self.back_btn.hide()
        buttons.addWidget(self.back_btn)
        self.no_2fa_btn = QPushButton("Account has no 2FA")
        self.no_2fa_btn.clicked.connect(lambda: self._authenticate(with_otp=False))
        self.no_2fa_btn.hide()
        buttons.addWidget(self.no_2fa_btn)
        buttons.addWidget(self.disconnect_btn)
        drive_layout.addLayout(buttons)
        diag_layout.addWidget(QLabel("Recent rclone errors (review before sharing)"))
        self.diagnostics_view = QTextEdit()
        self.diagnostics_view.setReadOnly(True)
        self.diagnostics_view.setMinimumHeight(260)
        diag_layout.addWidget(self.diagnostics_view)
        diagbuttons = QHBoxLayout()
        refresh_diag = QPushButton("Show rclone errors")
        refresh_diag.clicked.connect(self.show_diagnostics)
        diagbuttons.addWidget(refresh_diag)
        fresh_button = QPushButton("Forget saved MEGA session")
        fresh_button.clicked.connect(self.forget_login)
        diagbuttons.addWidget(fresh_button)
        diag_layout.addLayout(diagbuttons)
        diag_layout.addStretch(1)
        tip = QLabel("Offline writes remain in rclone's disk cache until upload succeeds. Do not force-close while writes are pending.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#9ba6b4; font-size: 11px")
        transfers_layout.addWidget(tip)
        bandwidth_group = QGroupBox("Transfer bandwidth")
        bandwidth_layout = QHBoxLayout(bandwidth_group)
        speed_choices = (
            ("Unlimited", "off"), ("512 KiB/s", "512k"),
            ("1 MiB/s", "1M"), ("5 MiB/s", "5M"),
            ("10 MiB/s", "10M"), ("25 MiB/s", "25M"), ("50 MiB/s", "50M"),
        )
        bandwidth_layout.addWidget(QLabel("Upload"))
        self.upload_limit_combo = QComboBox()
        self.upload_limit_combo.setObjectName("upload_limit")
        bandwidth_layout.addWidget(self.upload_limit_combo, 1)
        bandwidth_layout.addWidget(QLabel("Download"))
        self.download_limit_combo = QComboBox()
        self.download_limit_combo.setObjectName("download_limit")
        bandwidth_layout.addWidget(self.download_limit_combo, 1)
        for label, rate in speed_choices:
            self.upload_limit_combo.addItem(label, rate)
            self.download_limit_combo.addItem(label, rate)
        self.upload_limit_combo.setEnabled(False)
        self.download_limit_combo.setEnabled(False)
        self.bandwidth_apply = QPushButton("Apply limit")
        self.bandwidth_apply.setEnabled(False)
        self.bandwidth_apply.clicked.connect(self.apply_bandwidth_limit)
        bandwidth_layout.addWidget(self.bandwidth_apply)
        transfers_layout.addWidget(bandwidth_group)
        self.bandwidth_status = QLabel("Mount a drive to adjust transfer bandwidth.")
        self.bandwidth_status.setWordWrap(True)
        transfers_layout.addWidget(self.bandwidth_status)
        transfers_layout.addWidget(QLabel("Upload activity"))
        self.queue_table = QTableWidget(0, 5)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setHorizontalHeaderLabels(["File", "Size", "Status", "Attempts", "Progress"])
        self.queue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.queue_table.setMinimumHeight(155)
        transfers_layout.addWidget(self.queue_table, 1)
        retry_bar = QHBoxLayout()
        self.retry_button = QPushButton("Retry selected upload now")
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self.retry_selected_upload)
        retry_bar.addWidget(self.retry_button)
        self.queue_table.itemSelectionChanged.connect(self._retry_selection_changed)
        retry_bar.addStretch(1)
        transfers_layout.addLayout(retry_bar)
        self.transfer_summary = QLabel("Queue unavailable until mounted")
        self.transfer_summary.setWordWrap(True)
        transfers_layout.addWidget(self.transfer_summary)
        self.tray_notice = QLabel("System tray: initializing…")
        self.tray_notice.setWordWrap(True)
        drive_layout.addWidget(self.tray_notice)
        drive_layout.addStretch(1)
        self.setCentralWidget(root)
        self.setStyleSheet("""
        QMainWindow, QWidget { background: #10151d; color: #e7edf7; font-size: 13px; }
        QLabel#brand { font-size: 25px; font-weight: 800; color: #e8f3ff; padding-bottom: 3px; }
        QTabWidget::pane { border: 1px solid #2b394a; border-radius: 11px; background: #151d28; }
        QTabBar::tab { color: #a8b8cd; padding: 11px 23px; background: #151d28; margin-right: 4px;
                       border-top-left-radius: 8px; border-top-right-radius: 8px; }
        QTabBar::tab:selected { background: #263d57; color: #f0f8ff; }
        QGroupBox { background: #192332; border: 1px solid #2b3e52; border-radius: 10px;
                    margin-top: 14px; padding: 14px 12px 10px 12px; font-weight: 600; }
        QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #a4d0ff; }
        QLineEdit, QComboBox { background: #101b2a; border: 1px solid #3c536d; border-radius: 7px;
                              padding: 9px; selection-background-color: #3177bb; }
        QLineEdit:focus, QComboBox:focus { border: 1px solid #57aeff; }
        QPushButton { background: #2669a8; border: 1px solid #3883c3; border-radius: 8px;
                      padding: 10px 17px; font-weight: 600; }
        QPushButton:hover { background: #347ebf; }
        QPushButton:disabled { background: #27313e; color: #77889b; border-color: #293544; }
        QCheckBox { spacing: 10px; padding: 6px; }
        QTableWidget, QTextEdit { background: #101a27; border: 1px solid #304257; border-radius: 8px;
                                  alternate-background-color: #182536; }
        QHeaderView::section { background: #25354a; color: #c9d8eb; border: 0; padding: 9px; }
        QScrollArea { border: 0; }
        QScrollBar:vertical { background: #182332; width: 9px; }
        QScrollBar::handle:vertical { background: #415a74; border-radius: 4px; }
        QProgressBar { border: none; background: #253547; border-radius: 2px; }
        QProgressBar::chunk { background: #62b5ff; }
        """)
        self.tray = QSystemTrayIcon(tray_icon("#77849a"), self)
        self.tray.setToolTip("NimboMount — Disconnected")
        menu = QMenu()
        self.tray_status = QAction("Status: Disconnected", self)
        self.tray_status.setEnabled(False)
        menu.addAction(self.tray_status)
        menu.addSeparator()
        show = QAction("Show NimboMount", self)
        show.triggered.connect(self.showNormal)
        menu.addAction(show)
        self.mount_action = QAction("Connect", self)
        self.mount_action.triggered.connect(self.connect)
        menu.addAction(self.mount_action)
        unmount = QAction("Unmount", self)
        unmount.triggered.connect(self.disconnect)
        menu.addAction(unmount)
        menu.addSeparator()
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.exit_app)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        # Windows Explorer may not expose its notification area immediately at
        # logon, and can restart later. Keep retrying rather than dropping the
        # tray icon permanently after a single startup check.
        self.tray_timer = QTimer(self)
        self.tray_timer.setInterval(3000)
        self.tray_timer.timeout.connect(self.ensure_tray_visible)
        self.tray_timer.start()
        self.ensure_tray_visible()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.last_health = 0
        self._controls()

    def ensure_tray_visible(self):
        """Re-publish tray icon after Explorer starts/restarts.

        A visible QSystemTrayIcon may still be inside the Windows hidden-icons
        overflow; Windows controls whether it is pinned to the taskbar.
        """
        supported = QSystemTrayIcon.isSystemTrayAvailable()
        if supported and not self.tray.isVisible():
            self.tray.show()
        if supported and self.tray.isVisible():
            self.tray_notice.setText(
                "System tray: active (check the ^ hidden-icons menu if not pinned)."
            )
            self.tray_notice.setStyleSheet("color:#79dfa7")
        else:
            self.tray_notice.setText(
                "System tray unavailable. Waiting for Windows Explorer; "
                "the app will retry automatically."
            )
            self.tray_notice.setStyleSheet("color:#ffc06b")

    def refresh_letters(self):
        if IS_WIN:
            current = self.point.currentText()
            self.point.clear()
            self.point.addItems(available_letters())
            if current and self.point.findText(current) >= 0:
                self.point.setCurrentText(current)

    def browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select empty mount folder", self.point.text())
        if path:
            self.point.setText(path)

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.showNormal()
            self.activateWindow()

    def _worker(self, operation, function):
        if self.busy:
            return
        self.busy = True
        self._controls()
        def run():
            try:
                function()
                self.events.result.emit(operation, True, "")
            except Exception as exc:
                self.events.result.emit(operation, False, str(exc))
        threading.Thread(target=run, daemon=True).start()

    def _point_text(self):
        return self.point.currentText() if IS_WIN else self.point.text().strip()

    def _back_to_credentials(self):
        self.auth_stage = False
        self.pending_login = None
        self.otp.clear()
        self.otp.hide()
        self.otp_label.hide()
        self.password.show()
        self.email.setEnabled(True)
        self.back_btn.hide()
        self.no_2fa_btn.hide()
        self.auth_hint.setText("Step 1: Enter your MEGA email and password, then continue.")
        self._controls()

    def connect(self):
        if self.busy or self.engine.alive():
            return
        if self.auth_stage:
            self._authenticate(with_otp=True)
            return
        email = self.email.text().strip()
        password = self.password.text() or get_password(email)
        point = self._point_text()
        if not email:
            QMessageBox.warning(self, APP, "Enter your MEGA email address.")
            return
        self._save_preferences(email, point)
        # Known sessions are used ONLY when fresh login has not been requested.
        if get_session(email) and not self.force_login.isChecked():
            self.manual_disconnect = False
            self._set_status("● Connecting…", "Restoring the saved MEGA session", "#ffd074")
            self._worker("mount", lambda: self.engine.mount(email, "", point, write_cache_enabled=self.settings.write_cache_enabled))
            return
        if not password:
            QMessageBox.warning(self, APP, "Enter your MEGA password to continue.")
            return
        self.pending_login = (email, password, point)
        self.auth_stage = True
        self.email.setEnabled(False)
        self.password.hide()
        self.otp_label.show()
        self.otp.show()
        self.otp.clear()
        self.otp.setFocus()
        self.back_btn.show()
        self.no_2fa_btn.show()
        self.auth_hint.setText("Step 2: Enter a NEW six-digit authenticator code. "
                               "Your credentials and code are submitted together to MEGA for verification.")
        self._controls()

    def _save_preferences(self, email, point):
        self.settings.email = email
        self.settings.mountpoint = point
        self.settings.auto_reconnect = self.reconnect.isChecked()
        self.settings.write_cache_enabled = self.write_cache_checkbox.isChecked()
        self.settings.mount_at_login = self.startup.isChecked()
        self.settings.save()

    def _authenticate(self, with_otp=True):
        if self.busy or not self.pending_login:
            return
        email, password, point = self.pending_login
        otp = self.otp.text().strip() if with_otp else ""
        if with_otp and (len(otp) != 6 or not otp.isascii() or not otp.isdigit()):
            QMessageBox.warning(self, APP, "Enter exactly six digits from your authenticator app.")
            return
        # One-time code exists only in this worker invocation. Never stored in settings.
        self.otp.clear()
        self._set_status("● Signing in…", "Verifying MEGA credentials before mounting", "#ffd074")
        self._worker("auth", lambda: self.engine.validate(email, password, otp))

    def _restore_cache_checkbox(self):
        self.write_cache_checkbox.blockSignals(True)
        self.write_cache_checkbox.setChecked(self.settings.write_cache_enabled)
        self.write_cache_checkbox.blockSignals(False)

    def change_cache_mode(self, enabled):
        """Switch modes by a verified safe unmount and remount, never in-place."""
        if self.busy:
            self._restore_cache_checkbox()
            return
        if not self.engine.alive():
            self.settings.write_cache_enabled = enabled
            self.settings.save()
            self.cache_mode_notice.setText("Preference saved. Next mount will use " + ("local caching." if enabled else "direct writes (no offline recovery)."))
            return
        try:
            snapshot = self.engine.transfer_snapshot()
            safe, reason = self.engine._write_state(snapshot)
        except Exception as exc:
            self._restore_cache_checkbox()
            QMessageBox.warning(self, APP, "Unable to verify uploads. Cache mode unchanged: " + str(exc))
            return
        if not safe:
            self._restore_cache_checkbox()
            QMessageBox.warning(self, APP,
                "Uploads are pending or the write state is unsafe: " + reason +
                "\n\nNimboMount cannot safely cancel cached uploads and switch modes immediately. "
                "Canceling these writes can lose files. Retry after transfers finish; the existing cache and mount are preserved.")
            return
        choice = QMessageBox.question(self, APP,
            "Switch cache mode now? NimboMount must unmount and remount the drive. "
            "Close any open files first. With caching disabled, failed direct writes cannot be retried.")
        if choice != QMessageBox.StandardButton.Yes:
            self._restore_cache_checkbox()
            return
        email = self.settings.email or self.email.text().strip()
        point = self.engine.point
        self.manual_disconnect = True
        self._set_status("● Switching cache mode…", "Verifying writes and remounting", "#ffd074")
        old_mode = self.engine.write_cache_enabled
        def switch():
            self.engine.stop()  # performs a SECOND write-state check just before termination
            try:
                self.engine.mount(email, "", point, write_cache_enabled=enabled)
            except Exception as new_error:
                # Best-effort rollback of the original mode; never delete cached writes.
                # If the new process started, DO NOT attempt a second mount.
                if self.engine.alive():
                    raise RuntimeError("New cache-mode mount started but readiness is uncertain; "
                                       "inspect Diagnostics before trying again") from new_error
                try:
                    self.engine.mount(email, "", point, write_cache_enabled=old_mode)
                except Exception as rollback_error:
                    raise RuntimeError("Cache-mode change failed; restoring previous mount also failed: "
                                       + str(rollback_error)) from new_error
                raise RuntimeError("Cache-mode change failed; previous mount mode was restarted. "
                                   "Wait for the drive to become available before trying again") from new_error
        self._cache_switch_requested = enabled
        self._worker("cache_switch", switch)

    def disconnect(self):
        if self.busy:
            return
        self.manual_disconnect = True
        self.next_retry = 0
        self._set_status("● Unmounting…", "Finishing filesystem operations", "#ffd074")
        self._worker("stop", self.engine.stop)

    def _result(self, op, ok, message):
        self.busy = False
        if op == "auth":
            if ok and self.pending_login:
                email, password, point = self.pending_login
                if self.remember.isChecked():
                    try:
                        save_password(email, password)
                    except Exception as exc:
                        self.diagnostics_view.setPlainText("Password was not saved to the vault: " + str(exc))
                self._back_to_credentials()
                self.force_login.setChecked(False)
                self.manual_disconnect = False
                self._set_status("● Authenticated", "MEGA login verified. Mounting the drive…", "#83dfab")
                self._worker("mount", lambda: self.engine.mount(email, "", point, write_cache_enabled=self.settings.write_cache_enabled))
            else:
                self._set_status("● Login failed", message, "#ff8181")
                self.diagnostics_view.setPlainText(message)
                self.otp.setFocus()
        elif op == "mount":
            if ok:
                self.connected_once = False
                self.failures = 0
                self.last_health = 0
                self.mount_started_at = time.monotonic()
                self.mount_probe_active = False
                self._set_status("● Mount starting…", "Checking filesystem and MEGA connectivity", "#ffd074")
                self.otp.clear()
                self.force_login.setChecked(False)
            else:
                self.engine.cleanup()
                self._set_status("● Mount failed", message, "#ff8181")
                self.tabs.setCurrentIndex(2)
                if "session" in message.lower() or "authentication" in message.lower():
                    self.force_login.setChecked(True)
                    self.auth_hint.setText("Saved session may have expired. Continue to sign in again.")
                self.diagnostics_view.setPlainText(message)
                # Do not automatically retry authentication errors.
                if self.reconnect.isChecked() and any(x in message.lower() for x in ("network", "unreachable", "timeout")):
                    self.next_retry = time.monotonic() + 15
        elif op == "cache_switch":
            if ok:
                self.settings.write_cache_enabled = self._cache_switch_requested
                self.settings.save()
                self.manual_disconnect = False
                self.connected_once = False
                self.mount_started_at = time.monotonic()
                self.mount_probe_active = False
                self._set_status("● Mount starting…", "Cache mode changed; waiting for drive registration", "#ffd074")
                self.cache_mode_notice.setText("Active cache mode: " + ("Enabled" if self.settings.write_cache_enabled else "Disabled"))
            else:
                self._restore_cache_checkbox()
                self.connected_once = False
                if self.engine.alive():
                    self.mount_started_at = time.monotonic()
                    self.mount_probe_active = False
                    self._set_status("● Mount starting…", "Cache change failed; verifying restored mount", "#ffd074")
                else:
                    self.mount_started_at = 0
                    self._set_status("● Cache change failed", message, "#ff8181")
                QMessageBox.warning(self, APP, "Cache switch failed. " + message + "\nAny existing recovery cache was not deleted.")
        elif op == "bandwidth":
            if ok:
                self.bandwidth_status.setText(
                    "Limits applied — Upload: " + self.upload_limit_combo.currentText() + "; Download: " + self.download_limit_combo.currentText()
                )
            else:
                self.bandwidth_status.setText("Bandwidth change failed: " + message[:220])
                QMessageBox.warning(self, APP, "Unable to change bandwidth limit: " + message)
        elif op == "retry_upload":
            if ok:
                self.transfer_summary.setText("Retry requested. rclone will upload the selected queued file as soon as a slot is available.")
                self.last_transfer_poll = 0
            else:
                QMessageBox.warning(self, APP, "Could not retry upload: " + message)
        elif op == "stop":
            if ok:
                self.connected_once = False
                self._set_status("● Disconnected", "Drive unmounted; cached data directory retained", "#ffbb70")
                if IS_WIN:
                    self.refresh_letters()
            else:
                self._set_status("● Unmount incomplete", message, "#ff8181")
        elif op == "ready":
            self.mount_probe_active = False
            if ok:
                self.connected_once = True
                self.failures = 0
                self.next_retry = 0
                self._set_status("● Mounted", f"Drive ready at {self.engine.point}", "#83dfab")
                self.mount_started_at = 0
            elif not self.engine.alive():
                self._set_status("● Mount failed", self.engine.exit_diagnostic(), "#ff8181")
                self.tabs.setCurrentIndex(2)
            else:
                self.details.setText("Waiting for WinFsp drive registration: " + message[:160])
        elif op == "probe":
            if ok and self.engine.alive() and self.connected_once:
                self.failures = 0
                self._set_status("● Online", f"MEGA mounted at {self.engine.point}", "#83dfab")
            elif not ok and self.connected_once:
                self.failures += 1
                if self.failures >= 2:
                    self._set_status("● Offline / degraded", message + "; cached writes preserved", "#ffbb70")
        elif op == "health":
            if ok:
                self.failures = 0
                self.connected_once = True
                self.next_retry = 0
                self._set_status("● Online", f"MEGA mounted at {self.engine.point}", "#83dfab")
            else:
                self.failures += 1
                if self.failures >= 2:
                    self._set_status("● Offline / degraded", message + "; mount preserved and writes remain cached", "#ffbb70")
        self._controls()

    def _check_mount_ready(self):
        # Must confirm actual filesystem registration, not just a live subprocess.
        ready, message = self.engine.mount_ready()
        if not ready:
            raise RuntimeError(message)

    def _health_worker(self):
        self._worker("health", lambda: self._check_health())

    def _check_health(self):
        ok, message = self.engine.health()
        if not ok:
            raise RuntimeError(message)
        # Successful health probe is reported by the worker.

    def tick(self):
        if self.busy or self.shutting_down:
            return
        if self.engine.alive():
            if self.mount_started_at and not self.connected_once:
                elapsed = time.monotonic() - self.mount_started_at
                if elapsed > self.mount_deadline_seconds:
                    self.mount_started_at = 0
                    self._set_status("● Mount timed out", "Drive did not appear within 40 seconds. Inspect Diagnostics and check WinFsp.", "#ff8181")
                    self.tabs.setCurrentIndex(2)
                elif not self.mount_probe_active:
                    self.mount_probe_active = True
                    self._worker("ready", self._check_mount_ready)
                return
            if not self.queue_polling and time.monotonic() - self.last_transfer_poll >= 3:
                self.last_transfer_poll = time.monotonic()
                self.queue_polling = True
                threading.Thread(target=self._poll_transfers, daemon=True).start()
            if time.monotonic() - self.last_health > 60:
                self.last_health = time.monotonic()
                self._worker("probe", self._probe)
        elif self.engine.proc is not None:
            error = self.engine.exit_diagnostic()
            self.engine.cleanup()
            self.mount_started_at = 0
            self._set_status("● Mount process exited", error, "#ff8181")
            self.connected_once = False
            self._controls()
            self.tabs.setCurrentIndex(2)
            self.diagnostics_view.setPlainText(error)
            if not self.manual_disconnect and self.reconnect.isChecked():
                self.next_retry = time.monotonic() + min(300, 15 * 2 ** min(self.failures, 4))
                self.failures += 1
        elif self.next_retry and time.monotonic() >= self.next_retry and not self.manual_disconnect:
            self.next_retry = 0
            # No OTP replay: saved session is used, or user login is required.
            self.connect()

    def configure_startup(self, enabled):
        saved = get_session(self.email.text().strip())
        if enabled and not saved:
            QMessageBox.warning(self, APP, "Auto-mount needs a saved MEGA session. Connect successfully with your 2FA code first, then enable startup.")
            self.startup.blockSignals(True)
            self.startup.setChecked(False)
            self.startup.blockSignals(False)
            return
        try:
            set_login_startup(enabled)
            self.settings.mount_at_login = enabled
            self.settings.save()
        except Exception as exc:
            QMessageBox.warning(self, APP, str(exc))
            self.startup.blockSignals(True)
            self.startup.setChecked(False)
            self.startup.blockSignals(False)

    def show_diagnostics(self):
        self.diagnostics_view.setPlainText(self.engine.diagnostics())

    def forget_login(self):
        email = self.email.text().strip()
        if not email:
            return
        if self.engine.alive():
            QMessageBox.warning(self, APP, "Unmount before forgetting the session.")
            return
        choice = QMessageBox.question(self, APP, "Forget saved MEGA session? You will need a new password and 2FA login.")
        if choice == QMessageBox.StandardButton.Yes:
            forget_session(email)
            self.force_login.setChecked(True)
            self.diagnostics_view.setPlainText("Saved session removed. Enter password and a fresh 2FA code.")

    def _retry_selection_changed(self):
        row = self.queue_table.currentRow()
        self.retry_button.setEnabled(self.engine.alive() and self.engine.write_cache_enabled
                                     and not self.busy and 0 <= row < len(self.queue_ids)
                                     and self.queue_ids[row] is not None)

    def apply_bandwidth_limit(self):
        if self.busy or not self.engine.alive() or not self.connected_once:
            self.bandwidth_status.setText("Wait for the drive to finish mounting before changing bandwidth.")
            return
        upload_rate = self.upload_limit_combo.currentData()
        download_rate = self.download_limit_combo.currentData()
        self.bandwidth_apply.setEnabled(False)
        self.bandwidth_status.setText("Applying bandwidth limit…")
        self._worker("bandwidth", lambda: self.engine.set_bandwidth_limits(upload_rate, download_rate))

    def retry_selected_upload(self):
        row = self.queue_table.currentRow()
        if not (0 <= row < len(self.queue_ids)):
            return
        item_id = self.queue_ids[row]
        if item_id is None:
            return
        if not self.engine.write_cache_enabled:
            QMessageBox.information(self, APP, "Direct-write mode has no upload queue. Retry from the application that wrote the file.")
            return
        self.retry_button.setEnabled(False)
        self._worker("retry_upload", lambda: self.engine.retry_upload(item_id))

    def _poll_transfers(self):
        try:
            data = self.engine.transfer_snapshot()
            self.events.transfers.emit(data, "")
        except Exception as exc:
            self.events.transfers.emit(None, str(exc))

    def _transfers(self, data, error):
        self.queue_polling = False
        if error:
            self.transfer_summary.setText("Transfer monitoring temporarily unavailable: " + error[:140])
            return
        if data.get("direct"):
            stats = data.get("stats") or {}
            transferring = stats.get("transferring") or []
            self.queue_ids = []
            self.queue_table.setRowCount(0)
            self._retry_selection_changed()
            self.transfer_summary.setText(
                "Direct-write mode: no local VFS upload queue or failed-write retry. "
                f"Active transfers: {len(transferring)} | Reported errors: {stats.get('errors', 'unknown')}. "
                "A failed direct upload must be restarted by the application writing the file."
            )
            return
        queue = data.get("queue") or []
        cache = data.get("cache") or {}
        stats = data.get("stats") or {}
        if not isinstance(queue, list) or not all(isinstance(item, dict) for item in queue):
            self.transfer_summary.setText("Malformed transfer queue response. Check Diagnostics; no retry requested.")
            self.queue_ids = []
            self.queue_table.setRowCount(0)
            return
        self.queue_ids = [item.get("id") if isinstance(item.get("id"), int) and not isinstance(item.get("id"), bool) else None for item in queue]
        self.queue_table.setRowCount(len(queue))
        # core/stats transfers names may reflect backend internal names, not exactly VFS path.
        running = stats.get("transferring") or []
        if not isinstance(running, list):
            running = []
        for i, entry in enumerate(queue):
            name = str(entry.get("name", ""))
            transfer = next((t for t in running if isinstance(t, dict) and
                             (t.get("name") == name or str(t.get("name", "")).endswith("/" + name))), None)
            pct = "—"
            if transfer and isinstance(transfer.get("size"), (int, float)) and transfer["size"] > 0 \
                    and isinstance(transfer.get("bytes", 0), (int, float)):
                pct = f"{min(100, max(0, 100 * transfer.get('bytes', 0) / transfer['size'])):.1f}%"
            raw_tries = entry.get("tries", 0)
            tries = raw_tries if isinstance(raw_tries, int) and not isinstance(raw_tries, bool) and raw_tries >= 0 else 0
            state = "Uploading" if entry.get("uploading") else ("Retrying" if tries else "Queued")
            cells = [name, self._human_bytes(entry.get("size", 0)), state, str(tries), pct]
            for j, value in enumerate(cells):
                self.queue_table.setItem(i, j, QTableWidgetItem(value))
        self._retry_selection_changed()
        errors = int(cache.get("erroredFiles") or 0)
        low_disk = bool(cache.get("outOfSpace"))
        self.transfer_summary.setText(
            f"Queued: {cache.get('uploadsQueued', len(queue))} | Uploading: {cache.get('uploadsInProgress', 0)} | "
            f"Cache errors: {errors} | Cached: {self._human_bytes(cache.get('bytesUsed', 0))}"
            + (" | DISK FULL" if low_disk else "")
            + (" | WARNING: Failed writes remain in the VFS cache; do not clear it." if errors else "")
        )

    @staticmethod
    def _human_bytes(size):
        size = float(size or 0)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}"
            size /= 1024

    def _probe(self):
        ok, message = self.engine.health()
        if not ok:
            raise RuntimeError(message)

    def _set_status(self, label, message, color):
        self.status.setText(label)
        self.status.setStyleSheet(f"color:{color}; font-size:14px; font-weight:bold")
        self.details.setText(message)
        self.mount_activity.setVisible(any(x in label for x in ("starting", "Connecting", "Signing", "Unmounting", "Authenticated")))
        self.tray.setIcon(tray_icon(color))
        self.tray.setToolTip("NimboMount — " + label.replace("● ", ""))
        self.tray_status.setText("Status: " + label.replace("● ", ""))

    def _controls(self):
        active = self.engine.alive()
        bandwidth_ready = active and self.connected_once and not self.busy
        self.upload_limit_combo.setEnabled(bandwidth_ready)
        self.download_limit_combo.setEnabled(bandwidth_ready)
        self.bandwidth_apply.setEnabled(bandwidth_ready)
        self.write_cache_checkbox.setEnabled(not self.busy)
        self.connect_btn.setText("Verify & Mount" if self.auth_stage else "Continue to sign in / Connect")
        self.connect_btn.setEnabled(not self.busy and not active)
        self.back_btn.setEnabled(not self.busy)
        self.no_2fa_btn.setEnabled(not self.busy)
        self.disconnect_btn.setEnabled(not self.busy and active)
        self.mount_action.setEnabled(not self.busy and not active)

    def closeEvent(self, event):
        if self.shutting_down:
            event.accept()
        elif self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            event.ignore()
            self.exit_app()

    def exit_app(self):
        if self.busy:
            QMessageBox.information(self, APP, "A filesystem operation is in progress. Try exiting again shortly.")
            return
        if self.engine.alive():
            answer = QMessageBox.question(self, APP, "Verify pending writes and unmount? NimboMount will refuse to exit if any transfer or cache error remains.")
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                self.engine.stop()
            except Exception as exc:
                QMessageBox.warning(self, APP, str(exc))
                return
        self.shutting_down = True
        self.tray_timer.stop()
        self.tray.hide()
        QApplication.instance().quit()


def main():
    app = QApplication(sys.argv)
    BASE.mkdir(parents=True, exist_ok=True)
    instance_lock = QLockFile(str(BASE / "NimboMount-instance.lock"))
    instance_lock.setStaleLockTime(0)  # only reclaim if locking PID is gone
    if not instance_lock.tryLock(100):
        QMessageBox.information(None, APP, "NimboMount is already running. Check its window or the system tray. A second instance will not start.")
        return 0
    # Lock must live for the entire GUI process, including hidden-to-tray time.
    app._nimbo_instance_lock = instance_lock
    app.aboutToQuit.connect(instance_lock.unlock)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("NimboMount")
    app.setOrganizationName("NimboMount")
    app.setWindowIcon(QIcon(asset("NimboMount.ico")))
    window = MainWindow()
    if "--minimized" not in sys.argv:
        window.show()
    if window.settings.mount_at_login:
        QTimer.singleShot(1600, window.connect)
    return app.exec()
