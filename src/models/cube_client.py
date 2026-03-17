import queue
import time

import serial
from PyQt6.QtCore import QThread, pyqtSignal


class CubeClient(QThread):
    logMessage = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)
    responseReceived = pyqtSignal(str, str)
    statusUpdated = pyqtSignal(dict)

    def __init__(self, port_name: str):
        super().__init__()
        self.port_name = port_name
        self._running = False
        self._command_queue = queue.Queue()
        self._serial = None

    def run(self):
        self._running = True
        try:
            self._serial = serial.Serial(
                port=self.port_name,
                baudrate=19200,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.25,
                write_timeout=0.5,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            self.connectionChanged.emit(True)
            self.logMessage.emit(f"[CUBE] Connected to {self.port_name} at 19200 8N1.")

            while self._running:
                try:
                    command = self._command_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                response = self._send_and_receive(command)
                self.responseReceived.emit(command, response)
                if command == "?S":
                    self.statusUpdated.emit(self._parse_status_block(response))

        except (serial.SerialException, OSError) as exc:
            self.errorOccurred.emit(f"[ERROR] Serial connection failed: {exc}")
        finally:
            if self._serial and self._serial.is_open:
                try:
                    self._serial.close()
                except OSError:
                    pass
            self.connectionChanged.emit(False)
            self._running = False
            self.logMessage.emit("[CUBE] Connection closed.")

    def queue_command(self, command: str):
        self._command_queue.put(command.strip())

    def stop(self):
        self._running = False
        self.wait()

    def _send_and_receive(self, command: str) -> str:
        if not self._serial or not self._serial.is_open:
            raise serial.SerialException("Serial port is not open.")

        wire_command = f"{command}\r".encode("ascii")
        self._serial.reset_input_buffer()
        self._serial.write(wire_command)
        self.logMessage.emit(f"[TX] {command}")

        chunks = []
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            waiting = self._serial.in_waiting
            if waiting:
                data = self._serial.read(waiting)
                chunks.append(data)
                deadline = time.monotonic() + 0.2
            else:
                time.sleep(0.02)

        response = b"".join(chunks).decode("ascii", errors="replace").strip()
        self.logMessage.emit(f"[RX] {response or '[no response]'}")
        return response

    def _parse_status_block(self, response: str) -> dict:
        status = {}
        for raw_line in response.splitlines():
            line = raw_line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            status[key.strip()] = value.strip()
        return status
