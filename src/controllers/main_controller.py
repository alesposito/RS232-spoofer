import typing
from src.views.main_window import MainWindow
from src.models.serial_bridge import SerialBridgeDaemon
from src.models.emulator import LaserEmulator, LeicaEmulator

class MainController:
    """
    The Controller layer in the MVC pattern.
    Handles events from the View and interacts with the Model.
    """
    def __init__(self):
        # Initialize the view
        self.view = MainWindow()
        
        # Reference to the model (serial daemon thread)
        self.bridge_daemon: typing.Optional[SerialBridgeDaemon] = None
        
        # Connect View Signals to Controller Slots
        self.view.scanPortsRequested.connect(self.scan_ports)
        self.view.toggleMitMStateRequested.connect(self.toggle_mitm_state)
        self.view.connectionToggled.connect(self.toggle_connection)
        self.view.laserCommandRequested.connect(self.handle_laser_command)
        self.view.spoofConfigUpdated.connect(self.update_spoof_config)
        self.view.emulationToggled.connect(self.set_emulation_mode)
        
        self.current_spoof_config = {}
        self.is_emulation_mode = False
        
        # Emulator instances
        self.emu_laser: typing.Optional[LaserEmulator] = None
        self.emu_leica: typing.Optional[LeicaEmulator] = None
        
        # Initial scan on startup
        self.view.log("[BOOT] Controller initialized.")
        self.scan_ports()
        
    def show_main_window(self):
        """Displays the GUI."""
        self.view.show()
        
    def scan_ports(self):
        """Requests available COM ports from the OS and updates the view."""
        self.view.log("[SYS] Scanning for active COM ports...")
        
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        port_names = []
        ftdi_ports = []
        for port in ports:
            port_names.append(port.device)
            # Check for the RS232-WE-5000-BT_0.0 FTDI chipset (VID 0403, PID 6001)
            if port.vid == 0x0403 and port.pid == 0x6001:
                ftdi_ports.append(port.device)
        
        self.view.populate_ports(port_names)
        self.view.log(f"[SYS] Found {len(port_names)} ports: {', '.join(port_names) if port_names else 'None'}")
        
        if len(ftdi_ports) >= 2:
            self.view.log(f"[SYS] Auto-detected FTDI cables: {ftdi_ports[0]} and {ftdi_ports[1]}")
            self.view.set_selected_ports(ftdi_ports[0], ftdi_ports[1])
        elif len(ftdi_ports) == 1:
            self.view.log(f"[SYS] Auto-detected one FTDI cable: {ftdi_ports[0]}")
            self.view.set_selected_ports(ftdi_ports[0], None)

    def toggle_mitm_state(self, is_spoofing: bool):
        """Handle transition between Pass-Through and Spoofing modes."""
        mode = "SPOOFING" if is_spoofing else "PASS-THROUGH"
        self.view.log(f"[STATE CHANGE] Transitioning to {mode} mode.")
        
        if self.bridge_daemon and self.bridge_daemon.isRunning():
            self.bridge_daemon.set_spoofing(is_spoofing)

    def set_emulation_mode(self, enabled: bool):
        self.is_emulation_mode = enabled

    def update_spoof_config(self, config: dict):
        self.current_spoof_config = config
        if self.bridge_daemon and self.bridge_daemon.isRunning():
            self.bridge_daemon.set_spoofing_config(config)
            
    def toggle_connection(self, is_connecting: bool):
        """Starts or stops the serial daemon."""
        if is_connecting:
            if self.is_emulation_mode:
                # Setup Emulation Sockets
                self.view.log("[EMU] Initializing Virtual Serial Devices...")
                leica_port = "socket://localhost:9998"
                laser_port = "socket://localhost:9999"
                
                # Start Emulators
                self.emu_laser = LaserEmulator(port=9999)
                self.emu_laser.stateChanged.connect(self.view.update_emulator_ui)
                self.emu_laser.start()
                
                self.emu_leica = LeicaEmulator(port=9998)
                self.emu_leica.start()
                
                # Give servers a moment to bind
                import time
                time.sleep(0.5)
            else:
                leica_port = self.view.combo_leica.currentText()
                laser_port = self.view.combo_laser.currentText()
            
            if not leica_port or "No ports" in leica_port:
                self.view.log("[ERROR] Invalid Leica port selection.")
                return
            if not laser_port or "No ports" in laser_port:
                self.view.log("[ERROR] Invalid Laser port selection.")
                return
                
            # Instantiate the Thread
            self.bridge_daemon = SerialBridgeDaemon(leica_port, laser_port)
            self.bridge_daemon.logMessage.connect(self.view.log)
            self.bridge_daemon.errorOccurred.connect(self.handle_bridge_error)
            self.bridge_daemon.txRxData.connect(self.view.log_tx_rx)
            
            # Start Thread with current state
            self.bridge_daemon.set_spoofing_config(self.current_spoof_config)
            self.bridge_daemon.set_spoofing(self.view.btn_toggle_state.isChecked())
            self.bridge_daemon.start()
        else:
            if self.bridge_daemon and self.bridge_daemon.isRunning():
                self.view.log("[SYS] Requesting daemon shutdown...")
                self.bridge_daemon.stop()
                self.bridge_daemon = None
            
            # Stop Emulators if running
            if self.emu_laser:
                self.emu_laser.stop()
                self.emu_laser = None
            if self.emu_leica:
                self.emu_leica.stop()
                self.emu_leica = None
            self.view.log("[SYS] Connection closed.")

    def handle_laser_command(self, cmd_string: str):
        """Receive command from GUI pane and send to Laser if connected."""
        if self.bridge_daemon and self.bridge_daemon.isRunning():
            self.view.log(f"[USER -> CMD] Sending param to laser: {cmd_string.strip()}")
            self.bridge_daemon.send_laser_command(cmd_string)
        else:
            self.view.log(f"[WARN] Cannot send command '{cmd_string.strip()}' because connection is OFF.")
                
    def handle_bridge_error(self, err_msg: str):
        """Handles PySerial exceptions from the background thread."""
        self.view.log(err_msg)
        # Revert the UI to disconnected state securely
        if self.view.btn_connect.isChecked():
            # Temporarily block signals to avoid recursive calls
            self.view.btn_connect.blockSignals(True)
            self.view.btn_connect.setChecked(False)
            self.view.on_connect_toggled(False)
            self.view.btn_connect.blockSignals(False)
