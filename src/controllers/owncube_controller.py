import typing

import serial.tools.list_ports

from src.models.cube_client import CubeClient
from src.views.owncube_window import OwnCubeWindow


class OwnCubeController:
    def __init__(self):
        self.view = OwnCubeWindow()
        self.client: typing.Optional[CubeClient] = None

        self.view.scanPortsRequested.connect(self.scan_ports)
        self.view.connectionToggled.connect(self.toggle_connection)
        self.view.refreshRequested.connect(self.refresh_status)
        self.view.commandRequested.connect(self.send_command)
        self.view.btn_digital_mode.clicked.connect(self.arm_digital_modulation)

        self.view.log("[BOOT] ownCUBE initialized.")
        self.scan_ports()

    def show_main_window(self):
        self.view.show()

    def scan_ports(self):
        self.view.log("[SYS] Scanning for serial ports...")
        ports = list(serial.tools.list_ports.comports())
        port_names = [port.device for port in ports]
        self.view.populate_ports(port_names)
        self.view.log(f"[SYS] Found {len(port_names)} ports: {', '.join(port_names) if port_names else 'None'}")

        preferred = next(
            (
                port.device
                for port in ports
                if (port.manufacturer or "").upper().startswith("FTDI")
            ),
            port_names[0] if port_names else "",
        )
        if preferred:
            self.view.set_selected_port(preferred)
            self.view.log(f"[SYS] Defaulting to {preferred}.")

    def toggle_connection(self, should_connect: bool):
        if should_connect:
            port_name = self.view.combo_port.currentText()
            if not port_name or port_name == "No ports found":
                self.view.log("[ERROR] No valid COM port selected.")
                self.view.set_connected_state(False)
                return

            self.client = CubeClient(port_name)
            self.client.logMessage.connect(self.view.log)
            self.client.errorOccurred.connect(self._handle_error)
            self.client.connectionChanged.connect(self.view.set_connected_state)
            self.client.responseReceived.connect(self._handle_response)
            self.client.statusUpdated.connect(self.view.update_status)
            self.client.start()
            return

        if self.client and self.client.isRunning():
            self.view.log("[SYS] Disconnecting from laser...")
            self.client.stop()
        self.client = None

    def refresh_status(self):
        for command in ["?HID", "?SV", "?F", "?FL", "?STA", "?SS", "?SP", "?BT", "?DT", "?DST", "?HH", "?MINLP", "?MAXLP", "?INT", "?M", "?S"]:
            self.send_command(command)

    def send_command(self, command: str):
        if not self.client or not self.client.isRunning():
            self.view.log(f"[WARN] Cannot send '{command}' because the connection is closed.")
            return
        self.client.queue_command(command)

    def arm_digital_modulation(self):
        self.view.log("[SYS] Arming external SMB digital modulation mode...")
        for command in ["T=1", "L=1", "CW=0", "ANA=0", "EXT=0", f"CAL={self.view.spin_power.value():.2f}", "?S", "?SS", "?INT"]:
            self.send_command(command)

    def _handle_response(self, command: str, response: str):
        self.view.append_terminal(command, response)
        parsed = self._parse_response(command, response)
        if parsed:
            self.view.update_status(parsed)

    def _handle_error(self, message: str):
        self.view.log(message)
        self.view.set_connected_state(False)
        if self.client and self.client.isRunning():
            self.client.stop()
        self.client = None

    def _parse_response(self, command: str, response: str) -> dict:
        response = response.strip()
        if not response:
            return {}

        if command == "?S":
            parsed = {}
            for line in response.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    parsed[key.strip()] = value.strip()
            return parsed

        if command == "?HID":
            return {"HID": response}
        if command in {"?SV", "?SVH"}:
            return {"SV": response}
        if command == "?FL":
            return {"FL": response}

        if "=" in response:
            key, value = response.split("=", 1)
            return {key.strip().lstrip("?"): value.strip()}

        key_map = {
            "?F": "F",
            "?STA": "STA",
            "?SS": "SS",
            "?SP": "SP",
            "?BT": "BT",
            "?DT": "DT",
            "?DST": "DST",
            "?HH": "HH",
            "?MINLP": "MINLP",
            "?MAXLP": "MAXLP",
            "?INT": "INT",
            "?M": "M",
        }
        key = key_map.get(command)
        return {key: response} if key else {}
