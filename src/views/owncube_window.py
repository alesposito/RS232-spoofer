from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class OwnCubeWindow(QMainWindow):
    scanPortsRequested = pyqtSignal()
    connectionToggled = pyqtSignal(bool)
    refreshRequested = pyqtSignal()
    commandRequested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ownCUBE")
        self.resize(1120, 820)
        self._apply_theme()

        root = QWidget()
        self.setCentralWidget(root)
        self.main_layout = QVBoxLayout(root)

        self._build_connection_panel()
        self._build_status_panel()
        self._build_control_panel()
        self._build_terminal_panel()
        self._build_log_panel()

    def _build_connection_panel(self):
        group = QGroupBox("Connection")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("CUBE Serial Port:"))
        self.combo_port = QComboBox()
        self.combo_port.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.combo_port)

        self.btn_scan = QPushButton("Scan")
        self.btn_scan.clicked.connect(self.scanPortsRequested.emit)
        layout.addWidget(self.btn_scan)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setCheckable(True)
        self.btn_connect.toggled.connect(self._on_connect_toggled)
        layout.addWidget(self.btn_connect)

        self.btn_refresh = QPushButton("Refresh Status")
        self.btn_refresh.clicked.connect(self.refreshRequested.emit)
        self.btn_refresh.setEnabled(False)
        layout.addWidget(self.btn_refresh)

        self.lbl_connection = QLabel("Disconnected")
        self.lbl_connection.setStyleSheet("font-weight: bold; color: #ff8a80;")
        layout.addWidget(self.lbl_connection)

        self.lbl_digital_ready = QLabel("Digital Mode Not Ready")
        self.lbl_digital_ready.setStyleSheet("font-weight: bold; color: #ffcc80;")
        layout.addWidget(self.lbl_digital_ready)

        self.main_layout.addWidget(group)

    def _build_status_panel(self):
        group = QGroupBox("Live Status")
        layout = QGridLayout(group)

        self.status_labels = {}
        fields = [
            ("HID", "Head ID"),
            ("SV", "Firmware"),
            ("F", "Fault Number"),
            ("FL", "Fault Text"),
            ("STA", "Operating State"),
            ("SS", "TEC"),
            ("SP", "Set Power (mW)"),
            ("BT", "Base Temp"),
            ("DT", "Diode Temp"),
            ("DST", "Diode Set Temp"),
            ("HH", "Head Hours"),
            ("MINLP", "Min Power"),
            ("MAXLP", "Max Power"),
            ("INT", "Interlock"),
            ("M", "Manual Mode"),
            ("L", "Laser"),
            ("T", "TEC Enable"),
            ("CW", "CW Mode"),
            ("EXT", "External Ctrl"),
            ("CDRH", "CDRH Delay"),
            ("ANA", "Analog Mode"),
        ]

        for index, (key, title) in enumerate(fields):
            row = index // 3
            col = (index % 3) * 2
            label_title = QLabel(title)
            label_value = QLabel("--")
            label_value.setStyleSheet("font-weight: bold; color: #f7f3e8;")
            layout.addWidget(label_title, row, col)
            layout.addWidget(label_value, row, col + 1)
            self.status_labels[key] = label_value

        self.main_layout.addWidget(group)

    def _build_control_panel(self):
        row = QHBoxLayout()

        quick_group = QGroupBox("Quick Controls")
        quick_layout = QGridLayout(quick_group)

        quick_layout.addWidget(QLabel("Power (mW)"), 0, 0)
        self.spin_power = QDoubleSpinBox()
        self.spin_power.setRange(0.0, 1000.0)
        self.spin_power.setDecimals(2)
        self.spin_power.setSingleStep(0.5)
        quick_layout.addWidget(self.spin_power, 0, 1)

        self.btn_set_power = QPushButton("Set Power")
        self.btn_set_power.clicked.connect(lambda: self.commandRequested.emit(f"P={self.spin_power.value():.2f}"))
        quick_layout.addWidget(self.btn_set_power, 0, 2)

        self.chk_laser = QCheckBox("Laser On")
        self.chk_laser.toggled.connect(lambda checked: self.commandRequested.emit(f"L={1 if checked else 0}"))
        quick_layout.addWidget(self.chk_laser, 1, 0)

        self.chk_tec = QCheckBox("TEC On")
        self.chk_tec.toggled.connect(lambda checked: self.commandRequested.emit(f"T={1 if checked else 0}"))
        quick_layout.addWidget(self.chk_tec, 1, 1)

        self.chk_cw = QCheckBox("CW Mode")
        self.chk_cw.toggled.connect(lambda checked: self.commandRequested.emit(f"CW={1 if checked else 0}"))
        quick_layout.addWidget(self.chk_cw, 1, 2)

        self.chk_ext = QCheckBox("External Control")
        self.chk_ext.toggled.connect(lambda checked: self.commandRequested.emit(f"EXT={1 if checked else 0}"))
        quick_layout.addWidget(self.chk_ext, 2, 0)

        self.chk_cdrh = QCheckBox("CDRH Delay")
        self.chk_cdrh.toggled.connect(lambda checked: self.commandRequested.emit(f"CDRH={1 if checked else 0}"))
        quick_layout.addWidget(self.chk_cdrh, 2, 1)

        self.btn_digital_mode = QPushButton("Arm SMB Digital Mode")
        quick_layout.addWidget(self.btn_digital_mode, 2, 2)

        row.addWidget(quick_group)

        query_group = QGroupBox("Queries")
        query_layout = QFormLayout(query_group)
        query_buttons = [
            ("Full Status", "?S"),
            ("Head ID", "?HID"),
            ("Firmware", "?SV"),
            ("Faults", "?FL"),
            ("Operating State", "?STA"),
            ("Power Limits", "?MAXLP"),
            ("Interlock", "?INT"),
            ("Manual Mode", "?M"),
        ]
        for title, command in query_buttons:
            button = QPushButton(command)
            button.clicked.connect(lambda _checked=False, cmd=command: self.commandRequested.emit(cmd))
            query_layout.addRow(title, button)
        row.addWidget(query_group)

        self.main_layout.addLayout(row)

    def _build_terminal_panel(self):
        group = QGroupBox("Terminal")
        layout = QVBoxLayout(group)

        entry_row = QHBoxLayout()
        self.input_command = QLineEdit()
        self.input_command.setPlaceholderText("Enter raw command, for example ?S or P=10")
        self.input_command.returnPressed.connect(self._send_terminal_command)
        entry_row.addWidget(self.input_command)

        self.btn_send = QPushButton("Send")
        self.btn_send.clicked.connect(self._send_terminal_command)
        entry_row.addWidget(self.btn_send)
        layout.addLayout(entry_row)

        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setStyleSheet(
            "background-color: #171717; color: #f0e7d8; font-family: Consolas, monospace;"
        )
        layout.addWidget(self.terminal_output)

        self.main_layout.addWidget(group)

    def _build_log_panel(self):
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(140)
        self.console.document().setMaximumBlockCount(400)
        self.console.setStyleSheet("background-color: #101010; color: #d7ffb8; font-family: Consolas, monospace;")
        self.main_layout.addWidget(QLabel("Session Log"))
        self.main_layout.addWidget(self.console)

    def _apply_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(26, 30, 33))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(245, 240, 232))
        palette.setColor(QPalette.ColorRole.Base, QColor(20, 23, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 41, 45))
        palette.setColor(QPalette.ColorRole.Text, QColor(245, 240, 232))
        palette.setColor(QPalette.ColorRole.Button, QColor(61, 76, 84))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(245, 240, 232))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(208, 120, 48))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(15, 15, 15))
        self.setPalette(palette)

    def _on_connect_toggled(self, checked: bool):
        self.btn_connect.setText("Disconnect" if checked else "Connect")
        self.btn_scan.setEnabled(not checked)
        self.combo_port.setEnabled(not checked)
        self.btn_refresh.setEnabled(checked)
        self.connectionToggled.emit(checked)

    def _send_terminal_command(self):
        command = self.input_command.text().strip()
        if command:
            self.commandRequested.emit(command)
            self.input_command.clear()

    def populate_ports(self, ports: list[str]):
        self.combo_port.clear()
        if ports:
            self.combo_port.addItems(ports)
        else:
            self.combo_port.addItem("No ports found")

    def set_selected_port(self, port_name: str):
        index = self.combo_port.findText(port_name)
        if index >= 0:
            self.combo_port.setCurrentIndex(index)

    def set_connected_state(self, connected: bool):
        self.lbl_connection.setText("Connected" if connected else "Disconnected")
        self.lbl_connection.setStyleSheet(
            f"font-weight: bold; color: {'#b9f27c' if connected else '#ff8a80'};"
        )
        if self.btn_connect.isChecked() != connected:
            self.btn_connect.blockSignals(True)
            self.btn_connect.setChecked(connected)
            self.btn_connect.blockSignals(False)
            self.btn_connect.setText("Disconnect" if connected else "Connect")
            self.btn_scan.setEnabled(not connected)
            self.combo_port.setEnabled(not connected)
            self.btn_refresh.setEnabled(connected)

    def update_status(self, status: dict):
        for key, value in status.items():
            label = self.status_labels.get(key)
            if label:
                label.setText(value)

        toggle_map = {
            "L": self.chk_laser,
            "T": self.chk_tec,
            "CW": self.chk_cw,
            "EXT": self.chk_ext,
            "CDRH": self.chk_cdrh,
        }
        for key, widget in toggle_map.items():
            if key in status:
                widget.blockSignals(True)
                widget.setChecked(status[key] == "1")
                widget.blockSignals(False)

        if "SP" in status:
            try:
                self.spin_power.blockSignals(True)
                self.spin_power.setValue(float(status["SP"]))
            finally:
                self.spin_power.blockSignals(False)

        combined = {}
        for key, label in self.status_labels.items():
            value = label.text()
            if value != "--":
                combined[key] = value
        self._update_digital_ready(combined)

    def append_terminal(self, command: str, response: str):
        self.terminal_output.append(f"> {command}")
        self.terminal_output.append(f"< {response or '[no response]'}")

    def log(self, message: str):
        self.console.append(message)

    def _update_digital_ready(self, status: dict):
        ready = (
            status.get("CW") == "0"
            and status.get("ANA") == "0"
            and status.get("EXT") == "0"
            and status.get("SS") == "1"
            and status.get("INT") == "1"
            and status.get("STA") in {"2", "3"}
        )
        self.lbl_digital_ready.setText("Digital Mode Ready" if ready else "Digital Mode Not Ready")
        self.lbl_digital_ready.setStyleSheet(
            f"font-weight: bold; color: {'#b9f27c' if ready else '#ffcc80'};"
        )
