import json
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QPushButton, QLabel, QTextEdit, QGroupBox,
    QSizePolicy, QSpinBox, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPalette

CONFIG_FILE = "spoof_settings.json"

DEFAULT_COMMANDS = [
    ("Fault Status", "?F", "?F"),
    ("Fault Binary", "?FF", "?FF"),
    ("Fault List", "?FL", "?FL"),
    ("Operating Status", "?STA", "?STA"),
    ("Laser Mode", "?M", "?M"),
    ("Interlock", "?INT", "?INT"),
    ("TEC Status", "?SS", "?SS"),
    ("Laser Power", "P=", "P="),
    ("Set Power Out", "?SP", "?SP"),
    ("Ext Analog", "EXT=1", "EXT=0"),
    ("CW Mode", "CW=", "CW="),
    ("Base Plate Temp", "?BT", "?BT"),
    ("Laser ON-OFF", "L=1", "L=0"),
    ("Software Version", "?SV", "?SV"),
    ("Head ID", "?HID", "?HID"),
    ("Current Hours", "?HH", "?HH")
]

DEFAULT_RESPONSES = [
    ("No Fault (int)", "0", "0"),
    ("System OK (text)", "System OK", "System OK"),
    ("Operating Status (ON)", "3", "3"),
    ("Operating Status (Standby)", "2", "3"),
    ("Interlock (Closed)", "1", "1"),
    ("TEC (ON)", "1", "1"),
    ("Ext Analog (ON)", "1", "1"),
    ("CW Mode (ON)", "1", "1")
]

class MainWindow(QMainWindow):
    scanPortsRequested = pyqtSignal()
    toggleMitMStateRequested = pyqtSignal(bool)
    connectionToggled = pyqtSignal(bool)
    laserCommandRequested = pyqtSignal(str) 
    spoofConfigUpdated = pyqtSignal(dict) # Emitted whenever spoof settings change
    emulationToggled = pyqtSignal(bool) # Emitted when emulation mode is turned on/off

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SP5-CUBE MitM Gateway")
        self.resize(1000, 800)
        self.apply_dark_theme()
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        self.setup_ui()
        self.load_spoofing_settings()
        
    def setup_ui(self):
        # Top Panel: Connection Settings
        connection_group = QGroupBox("Hardware Connection Settings")
        conn_layout = QHBoxLayout()
        
        conn_layout.addWidget(QLabel("Leica SP5 (COM):"))
        self.combo_leica = QComboBox()
        self.combo_leica.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        conn_layout.addWidget(self.combo_leica)
        
        conn_layout.addWidget(QLabel("CUBE Laser (COM):"))
        self.combo_laser = QComboBox()
        self.combo_laser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        conn_layout.addWidget(self.combo_laser)
        
        self.btn_scan = QPushButton("Scan Ports")
        self.btn_scan.clicked.connect(self.scanPortsRequested.emit)
        conn_layout.addWidget(self.btn_scan)

        self.chk_emulation = QCheckBox("EMULATION MODE")
        self.chk_emulation.setStyleSheet("color: #ff9800; font-weight: bold;")
        self.chk_emulation.toggled.connect(self.on_emulation_toggled)
        conn_layout.addWidget(self.chk_emulation)

        self.btn_connect = QPushButton("CONNECT")
        self.btn_connect.setCheckable(True)
        self.btn_connect.setStyleSheet("font-weight: bold; background-color: #1976D2; color: white;")
        self.btn_connect.toggled.connect(self.on_connect_toggled)
        conn_layout.addWidget(self.btn_connect)
        connection_group.setLayout(conn_layout)
        self.main_layout.addWidget(connection_group)
        
        # State Toggle
        state_group = QGroupBox("MitM Operation Mode")
        state_layout = QVBoxLayout()
        self.btn_toggle_state = QPushButton("Current Mode: PASS-THROUGH (Click to Enable SPOOFING)")
        self.btn_toggle_state.setCheckable(True)
        self.btn_toggle_state.setMinimumHeight(40)
        self.btn_toggle_state.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white;")
        self.btn_toggle_state.toggled.connect(self.on_state_toggled)
        state_layout.addWidget(self.btn_toggle_state)
        state_group.setLayout(state_layout)
        self.main_layout.addWidget(state_group)
        
        # TABS
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        self.tab_monitor = QWidget()
        self.tab_monitor_layout = QVBoxLayout(self.tab_monitor)
        self.setup_monitor_tab()
        self.tabs.addTab(self.tab_monitor, "Monitor & Config")
        
        self.tab_spoofing = QWidget()
        self.tab_spoofing_layout = QVBoxLayout(self.tab_spoofing)
        self.setup_spoofing_tab()
        self.tabs.addTab(self.tab_spoofing, "Spoofing Rules")

        self.tab_emulator = QWidget()
        self.tab_emulator_layout = QVBoxLayout(self.tab_emulator)
        self.setup_emulator_tab()
        self.tabs.addTab(self.tab_emulator, "Emulator (Digital Twin)")

        # Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(150)
        self.console.document().setMaximumBlockCount(300)
        self.console.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas, monospace;")
        self.main_layout.addWidget(QLabel("System Logs:"))
        self.main_layout.addWidget(self.console)

    def setup_monitor_tab(self):
        data_group = QGroupBox("Data Monitor (Tx / Rx Hex Logging)")
        data_layout = QGridLayout()
        
        def create_hex_monitor():
            te = QTextEdit()
            te.setReadOnly(True)
            te.setMaximumHeight(100)
            te.document().setMaximumBlockCount(100)
            te.setStyleSheet("background-color: #1e1e1e; color: #ffeb3b; font-family: Consolas, monospace;")
            return te

        self.leica_rx = create_hex_monitor()
        self.leica_tx = create_hex_monitor()
        self.laser_rx = create_hex_monitor()
        self.laser_tx = create_hex_monitor()
        
        data_layout.addWidget(QLabel("Leica Rx (From SP5):"), 0, 0)
        data_layout.addWidget(self.leica_rx, 1, 0)
        data_layout.addWidget(QLabel("Leica Tx (To SP5):"), 0, 1)
        data_layout.addWidget(self.leica_tx, 1, 1)
        
        data_layout.addWidget(QLabel("Laser Rx (From CUBE):"), 2, 0)
        data_layout.addWidget(self.laser_rx, 3, 0)
        data_layout.addWidget(QLabel("Laser Tx (To CUBE):"), 2, 1)
        data_layout.addWidget(self.laser_tx, 3, 1)
        data_group.setLayout(data_layout)
        self.tab_monitor_layout.addWidget(data_group)

        ctrl_group = QGroupBox("Laser Parameters (COM Control)")
        ctrl_layout = QGridLayout()
        ctrl_layout.addWidget(QLabel("Power (mW):"), 0, 0)
        self.spin_power = QSpinBox()
        self.spin_power.setRange(0, 500)
        self.btn_set_power = QPushButton("Set Power (P=)")
        self.btn_set_power.clicked.connect(self.on_set_power_clicked)
        ctrl_layout.addWidget(self.spin_power, 0, 1)
        ctrl_layout.addWidget(self.btn_set_power, 0, 2)

        self.chk_laser_on = QCheckBox("Laser ON (L=1/0)")
        self.chk_laser_on.toggled.connect(self.on_laser_toggled)
        ctrl_layout.addWidget(self.chk_laser_on, 1, 0)
        
        self.chk_cw_mode = QCheckBox("CW Mode (CW=1/0)")
        self.chk_cw_mode.toggled.connect(self.on_cw_toggled)
        ctrl_layout.addWidget(self.chk_cw_mode, 1, 1)

        self.chk_ext_ctrl = QCheckBox("Ext Analog (EXT=1/0)")
        self.chk_ext_ctrl.toggled.connect(self.on_ext_toggled)
        ctrl_layout.addWidget(self.chk_ext_ctrl, 1, 2)
        
        self.btn_poll_status = QPushButton("Poll Current Laser Parameters (?S)")
        self.btn_poll_status.clicked.connect(self.on_poll_status_clicked)
        ctrl_layout.addWidget(self.btn_poll_status, 2, 0, 1, 3)
        ctrl_group.setLayout(ctrl_layout)
        self.tab_monitor_layout.addWidget(ctrl_group)
        self.tab_monitor_layout.addStretch()

    def setup_spoofing_tab(self):
        desc = QLabel("Check the box to intercept and overwrite a specific command or response.")
        desc.setStyleSheet("font-style: italic; color: #aaaaaa;")
        self.tab_spoofing_layout.addWidget(desc)

        layout = QHBoxLayout()

        # Table 1: Leica -> Laser Commands
        grp1 = QGroupBox("Commands (Leica -> Laser)")
        lt1 = QVBoxLayout(grp1)
        self.tbl_commands = QTableWidget(0, 4)
        self.tbl_commands.setHorizontalHeaderLabels(["Spoof?", "Parameter", "Target Match", "Replacement"])
        self.tbl_commands.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_commands.horizontalHeader().setStretchLastSection(True)
        lt1.addWidget(self.tbl_commands)
        layout.addWidget(grp1)

        # Table 2: Laser -> Leica Responses
        grp2 = QGroupBox("Responses (Laser -> Leica)")
        lt2 = QVBoxLayout(grp2)
        self.tbl_responses = QTableWidget(0, 4)
        self.tbl_responses.setHorizontalHeaderLabels(["Spoof?", "Description", "Target Match", "Replacement"])
        self.tbl_responses.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_responses.horizontalHeader().setStretchLastSection(True)
        lt2.addWidget(self.tbl_responses)
        layout.addWidget(grp2)

        self.tab_spoofing_layout.addLayout(layout)

        save_btn = QPushButton("Save & Apply Restrictions")
        save_btn.clicked.connect(self.save_spoofing_settings)
        self.tab_spoofing_layout.addWidget(save_btn)

    def setup_emulator_tab(self):
        desc = QLabel("Visual representation of the Emulated CUBE Laser Hardware (Digital Twin).")
        desc.setStyleSheet("font-style: italic; color: #ff9800;")
        self.tab_emulator_layout.addWidget(desc)

        self.emu_group = QGroupBox("Laser Internal State (Real-time)")
        self.emu_layout = QGridLayout()

        self.lbl_emu_power = QLabel("Power: 0 mW")
        self.lbl_emu_power.setStyleSheet("font-size: 18pt; font-weight: bold; color: #00ff00;")
        self.lbl_emu_laser = QLabel("Laser: OFF")
        self.lbl_emu_laser.setStyleSheet("font-size: 14pt;")
        self.lbl_emu_cw = QLabel("Mode: CW")
        self.lbl_emu_cw.setStyleSheet("font-size: 14pt;")
        self.lbl_emu_ext = QLabel("Ext Ctrl: DISABLED")
        self.lbl_emu_ext.setStyleSheet("font-size: 14pt;")

        self.emu_layout.addWidget(self.lbl_emu_power, 0, 0, 1, 2)
        self.emu_layout.addWidget(self.lbl_emu_laser, 1, 0)
        self.emu_layout.addWidget(self.lbl_emu_cw, 1, 1)
        self.emu_layout.addWidget(self.lbl_emu_ext, 2, 0)

        self.emu_group.setLayout(self.emu_layout)
        self.tab_emulator_layout.addWidget(self.emu_group)
        self.tab_emulator_layout.addStretch()

    def update_emulator_ui(self, state: dict):
        """Called by controller to update the Digital Twin display."""
        self.lbl_emu_power.setText(f"Power: {state.get('power', 0)} mW")
        self.lbl_emu_laser.setText(f"Laser: {'ON' if state.get('laser_on') else 'OFF'}")
        self.lbl_emu_laser.setStyleSheet(f"font-size: 14pt; color: {'red' if state.get('laser_on') else 'gray'};")
        self.lbl_emu_cw.setText(f"Mode: {'CW' if state.get('cw_mode') else 'Pulsed'}")
        self.lbl_emu_ext.setText(f"Ext Ctrl: {'ENABLED' if state.get('ext_analog') else 'DISABLED'}")
        self.lbl_emu_ext.setStyleSheet(f"font-size: 14pt; color: {'cyan' if state.get('ext_analog') else 'white'};")

    def on_emulation_toggled(self, checked):
        if checked:
            self.log("[SYS] Entering EMULATION MODE. Hardware ports will be ignored.")
            self.tabs.setCurrentWidget(self.tab_emulator)
        else:
            self.log("[SYS] Exiting EMULATION MODE.")
        self.emulationToggled.emit(checked)

    def populate_table_defaults(self):
        self._fill_table(self.tbl_commands, DEFAULT_COMMANDS)
        self._fill_table(self.tbl_responses, DEFAULT_RESPONSES)

    def _fill_table(self, table, data_list):
        table.setRowCount(len(data_list))
        for r, (name, target, repl) in enumerate(data_list):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            table.setItem(r, 0, chk)
            table.setItem(r, 1, QTableWidgetItem(name))
            table.setItem(r, 2, QTableWidgetItem(target))
            table.setItem(r, 3, QTableWidgetItem(repl))

    def load_spoofing_settings(self):
        # Always populate defaults first
        self.populate_table_defaults()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                
                # Apply commands
                self._apply_config_to_table(self.tbl_commands, config.get("commands", []))
                # Apply responses
                self._apply_config_to_table(self.tbl_responses, config.get("responses", []))
                self.log(f"[SYS] Loaded spoof settings from {CONFIG_FILE}")
            except Exception as e:
                self.log(f"[ERROR] Failed to load config: {e}")
                
        # Emit initial config
        self.emit_current_config()

    def _apply_config_to_table(self, table, config_list):
        for item in config_list:
            target = item.get("target", "")
            repl = item.get("replacement", "")
            enabled = item.get("enabled", False)
            name = item.get("name", "")
            
            # Find row by target match OR create new row
            row_found = False
            for r in range(table.rowCount()):
                if table.item(r, 2).text() == target:
                    table.item(r, 0).setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
                    table.item(r, 3).setText(repl)
                    row_found = True
                    break
            
            if not row_found:
                # Append row if it's a custom saved setting
                r = table.rowCount()
                table.insertRow(r)
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
                table.setItem(r, 0, chk)
                table.setItem(r, 1, QTableWidgetItem(name))
                table.setItem(r, 2, QTableWidgetItem(target))
                table.setItem(r, 3, QTableWidgetItem(repl))

    def save_spoofing_settings(self):
        cmd_conf = self._extract_config_from_table(self.tbl_commands)
        res_conf = self._extract_config_from_table(self.tbl_responses)
        config = {
            "commands": cmd_conf,
            "responses": res_conf
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            self.log("[SYS] Saved and applied spoofing configs.")
            self.emit_current_config()
        except Exception as e:
            self.log(f"[ERROR] Failed to save config: {e}")

    def _extract_config_from_table(self, table):
        result = []
        for r in range(table.rowCount()):
            enabled = table.item(r, 0).checkState() == Qt.CheckState.Checked
            name = table.item(r, 1).text()
            target = table.item(r, 2).text()
            repl = table.item(r, 3).text()
            result.append({"enabled": enabled, "name": name, "target": target, "replacement": repl})
        return result

    def emit_current_config(self):
        cmd_conf = self._extract_config_from_table(self.tbl_commands)
        res_conf = self._extract_config_from_table(self.tbl_responses)
        config = {
            "commands": [i for i in cmd_conf if i["enabled"]],
            "responses": [i for i in res_conf if i["enabled"]]
        }
        self.spoofConfigUpdated.emit(config)

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(palette)

    def on_set_power_clicked(self):
        val = self.spin_power.value()
        self.laserCommandRequested.emit(f"P={val}\r")
    
    def on_laser_toggled(self, checked):
        val = 1 if checked else 0
        self.laserCommandRequested.emit(f"L={val}\r")
        
    def on_cw_toggled(self, checked):
        val = 1 if checked else 0
        self.laserCommandRequested.emit(f"CW={val}\r")
        
    def on_ext_toggled(self, checked):
        val = 1 if checked else 0
        self.laserCommandRequested.emit(f"EXT={val}\r")

    def on_poll_status_clicked(self):
        self.laserCommandRequested.emit("?S\r")

    def log(self, message: str):
        self.console.append(message)
        
    def log_tx_rx(self, source: str, data: str):
        """Append Hex strings to respective monitors."""
        if source == "LEICA_RX":
            self.leica_rx.append(data)
        elif source == "LEICA_TX":
            self.leica_tx.append(data)
        elif source == "LASER_RX":
            self.laser_rx.append(data)
        elif source == "LASER_TX":
            self.laser_tx.append(data)

    def on_state_toggled(self, checked):
        if checked:
            self.btn_toggle_state.setText("Current Mode: SPOOFING (Click to Disable)")
            self.btn_toggle_state.setStyleSheet("font-weight: bold; background-color: #c62828; color: white;")
        else:
            self.btn_toggle_state.setText("Current Mode: PASS-THROUGH (Click to Enable SPOOFING)")
            self.btn_toggle_state.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white;")
        
        self.toggleMitMStateRequested.emit(checked)
        
    def on_connect_toggled(self, checked):
        if checked:
            self.btn_connect.setText("DISCONNECT")
            self.btn_connect.setStyleSheet("font-weight: bold; background-color: #E64A19; color: white;")
            self.combo_leica.setEnabled(False)
            self.combo_laser.setEnabled(False)
            self.btn_scan.setEnabled(False)
        else:
            self.btn_connect.setText("CONNECT")
            self.btn_connect.setStyleSheet("font-weight: bold; background-color: #1976D2; color: white;")
            self.combo_leica.setEnabled(True)
            self.combo_laser.setEnabled(True)
            self.btn_scan.setEnabled(True)
            
        self.connectionToggled.emit(checked)

    def populate_ports(self, ports: list[str]):
        """Update both combo boxes with available COM ports."""
        self.combo_leica.clear()
        self.combo_laser.clear()
        
        if not ports:
            self.combo_leica.addItem("No ports found")
            self.combo_laser.addItem("No ports found")
        else:
            self.combo_leica.addItems(ports)
            self.combo_laser.addItems(ports)
            if len(ports) >= 2:
                self.combo_laser.setCurrentIndex(1)

    def set_selected_ports(self, leica_port: str, laser_port: str = None):
        if leica_port:
            index = self.combo_leica.findText(leica_port)
            if index >= 0:
                self.combo_leica.setCurrentIndex(index)
        if laser_port:
            index = self.combo_laser.findText(laser_port)
            if index >= 0:
                self.combo_laser.setCurrentIndex(index)
