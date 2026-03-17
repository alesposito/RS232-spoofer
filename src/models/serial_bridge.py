import os
import time
import traceback
import serial
from PyQt6.QtCore import QThread, pyqtSignal

class SerialBridgeDaemon(QThread):
    """
    The asynchronous Model logic managing the PySerial buffers.
    Runs concurrently in the background.
    """
    # Signals emitted back to the Controller/View for logging or state updates
    logMessage = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    txRxData = pyqtSignal(str, str) # source ("LEICA_RX", "LEICA_TX", "LASER_RX", "LASER_TX"), hex_data
    
    def __init__(self, leica_port: str, laser_port: str, baudrate: int = 19200):
        super().__init__()
        self.leica_port = leica_port
        self.laser_port = laser_port
        self.baudrate = baudrate
        self.is_running = False
        self.spoofing_enabled = False
        self.spoof_config = {"commands": [], "responses": []}
        
        # Determine log file path
        cwd = os.getcwd()
        self.log_file_path = os.path.join(cwd, "sniffer_log.txt")
        self.fallback_log_file_path = os.path.join(
            os.environ.get("LOCALAPPDATA", os.environ.get("TEMP", cwd)),
            "RS232-spoofer",
            "sniffer_log.txt",
        )
        self._command_queue = []
        self._log_failure_reported = False
        self._active_log_path = self.log_file_path
        
    def run(self):
        self.is_running = True
        current_operation = "starting bridge"
        
        try:
            # Open serial ports with non-blocking rapid polling
            # Use serial_for_url to handle both COM ports and socket:// URLs
            current_operation = f"opening Leica port {self.leica_port}"
            self.leica_serial = serial.serial_for_url(self.leica_port, baudrate=self.baudrate, timeout=0.01, write_timeout=0.5)
            current_operation = f"opening Laser port {self.laser_port}"
            self.laser_serial = serial.serial_for_url(self.laser_port, baudrate=self.baudrate, timeout=0.01, write_timeout=0.5)
            self.logMessage.emit(f"[BRIDGE] Connected: {self.leica_port} <-> {self.laser_port} at {self.baudrate} baud.")
            self.logMessage.emit(f"[BRIDGE] Logging hex traffic to: {self._active_log_path}")
            
            current_operation = f"writing session header to {self.log_file_path}"
            self._append_log_line(f"\n--- SESSION START: {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            
            # Main Bridge Loop
            while self.is_running:
                # Send any pending commands from the GUI directly to laser
                while self._command_queue:
                    current_operation = "sending queued laser command"
                    cmd = self._command_queue.pop(0)
                    cmd_bytes = cmd.encode('utf-8')
                    self._write_bytes(self.laser_serial, cmd_bytes, "Laser command queue")
                    self.txRxData.emit("LASER_TX", cmd_bytes.hex(' '))
                
                # 1. Read from Leica
                current_operation = "reading from Leica"
                leica_bytes = self._read_available(self.leica_serial, "Leica")
                if leica_bytes:
                    hex_raw = leica_bytes.hex(' ')
                    self.txRxData.emit("LEICA_RX", hex_raw)
                    
                    if not self.spoofing_enabled:
                        # State 1: True Pass-Through
                        current_operation = "writing Leica passthrough to Laser"
                        self._write_bytes(self.laser_serial, leica_bytes, "Leica passthrough")
                        self.txRxData.emit("LASER_TX", hex_raw)
                        self._append_log_line(f"[LEICA -> LASER] {hex_raw}\n")
                    else:
                        # State 2: Intercept & Edit (Pass-Through with Replacements)
                        text = leica_bytes.decode('utf-8', errors='ignore')
                        original_text = text
                        for rule in self.spoof_config.get("commands", []):
                            if rule["target"] and rule["target"] in text:
                                text = text.replace(rule["target"], rule["replacement"])
                                
                        out_bytes = text.encode('utf-8')
                        current_operation = "writing spoofed Leica payload to Laser"
                        self._write_bytes(self.laser_serial, out_bytes, "Leica spoofed passthrough")
                        
                        hex_out = out_bytes.hex(' ')
                        self.txRxData.emit("LASER_TX", hex_out)
                        
                        if text != original_text:
                            self._append_log_line(f"[LEICA -> SPOOFED LASER] {hex_out} (Changed from: {hex_raw})\n")
                        else:
                            self._append_log_line(f"[LEICA -> LASER] {hex_out}\n")
                
                # 2. Read from Laser
                current_operation = "reading from Laser"
                laser_bytes = self._read_available(self.laser_serial, "Laser")
                if laser_bytes:
                    hex_raw = laser_bytes.hex(' ')
                    self.txRxData.emit("LASER_RX", hex_raw)
                    
                    if not self.spoofing_enabled:
                        # State 1: True Pass-Through
                        current_operation = "writing Laser passthrough to Leica"
                        self._write_bytes(self.leica_serial, laser_bytes, "Laser passthrough")
                        self.txRxData.emit("LEICA_TX", hex_raw)
                        self._append_log_line(f"[LASER -> LEICA] {hex_raw}\n")
                    else:
                        # State 2: Intercept & Edit (Pass-Through with Replacements)
                        text = laser_bytes.decode('utf-8', errors='ignore')
                        original_text = text
                        for rule in self.spoof_config.get("responses", []):
                            if rule["target"] and rule["target"] in text:
                                text = text.replace(rule["target"], rule["replacement"])
                                
                        out_bytes = text.encode('utf-8')
                        current_operation = "writing spoofed Laser payload to Leica"
                        self._write_bytes(self.leica_serial, out_bytes, "Laser spoofed passthrough")
                        
                        hex_out = out_bytes.hex(' ')
                        self.txRxData.emit("LEICA_TX", hex_out)
                        
                        if text != original_text:
                            self._append_log_line(f"[LASER -> SPOOFED LEICA] {hex_out} (Changed from: {hex_raw})\n")
                        else:
                            self._append_log_line(f"[LASER -> LEICA] {hex_out}\n")
                
                current_operation = "sleeping between poll cycles"
                self.msleep(1)
                    
        except (serial.SerialException, OSError) as e:
            self.errorOccurred.emit(f"[ERROR] Serial Port Exception during {current_operation}: {str(e)}")
            self.logMessage.emit(traceback.format_exc())
            self.logMessage.emit(f"[ERROR] Bridge stopped due to exception.")
        except Exception as e:
            self.errorOccurred.emit(f"[ERROR] Unexpected Exception during {current_operation}: {str(e)}")
            self.logMessage.emit(traceback.format_exc())
            self.logMessage.emit(f"[ERROR] Bridge stopped due to exception.")
        finally:
            self._cleanup_ports()
            self.is_running = False

    def send_laser_command(self, cmd_string: str):
        """Enqueue a command to be sent to the laser on the next bridge loop."""
        self._command_queue.append(cmd_string)

    def _read_available(self, port, port_label: str) -> bytes:
        """
        Read up to a small chunk without relying on `in_waiting`, which is less stable on some
        Windows serial drivers and can surface bad descriptor errors during disconnects.
        """
        try:
            return port.read(4096)
        except (serial.SerialException, OSError) as exc:
            raise serial.SerialException(f"{port_label} read failed: {exc}") from exc

    def _write_bytes(self, port, payload: bytes, context: str):
        """Wrap writes so low-level OS errors are surfaced with direction/context."""
        try:
            port.write(payload)
        except (serial.SerialException, OSError) as exc:
            raise serial.SerialException(f"{context} write failed: {exc}") from exc

    def _append_log_line(self, line: str):
        """
        Best-effort disk logging. Logging failures should not kill the serial bridge because the
        primary job is live traffic forwarding.
        """
        try:
            with open(self._active_log_path, "a", encoding="utf-8") as logfile:
                logfile.write(line)
        except OSError as exc:
            if self._active_log_path != self.fallback_log_file_path:
                self._switch_to_fallback_log(exc)
                try:
                    with open(self._active_log_path, "a", encoding="utf-8") as logfile:
                        logfile.write(line)
                    return
                except OSError as fallback_exc:
                    exc = fallback_exc

            if not self._log_failure_reported:
                self._log_failure_reported = True
                self.logMessage.emit(f"[WARN] Traffic logging disabled: {exc}")

    def _switch_to_fallback_log(self, original_exc: OSError):
        fallback_dir = os.path.dirname(self.fallback_log_file_path)
        try:
            os.makedirs(fallback_dir, exist_ok=True)
            self._active_log_path = self.fallback_log_file_path
            self.logMessage.emit(
                f"[WARN] Primary log file unavailable ({original_exc}). "
                f"Falling back to: {self._active_log_path}"
            )
        except OSError:
            self._active_log_path = self.fallback_log_file_path

    def _cleanup_ports(self):
        """Safely close serial ports."""
        if hasattr(self, 'leica_serial') and self.leica_serial.is_open:
            try:
                self.leica_serial.close()
            except OSError:
                pass
        if hasattr(self, 'laser_serial') and self.laser_serial.is_open:
            try:
                self.laser_serial.close()
            except OSError:
                pass
        self.logMessage.emit("[BRIDGE] Ports closed.")

    def set_spoofing(self, state: bool):
        self.spoofing_enabled = state
        self.logMessage.emit(f"[BRIDGE] Spoofing state updated internally to: {state}")

    def set_spoofing_config(self, config: dict):
        self.spoof_config = config
        self.logMessage.emit(f"[BRIDGE] Spoofing config updated with {len(config.get('commands', []))} commands and {len(config.get('responses', []))} response rules.")

    def stop(self):
        self.is_running = False
        self.wait() # Block until run loop completely exits
