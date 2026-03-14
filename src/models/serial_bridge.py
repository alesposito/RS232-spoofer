import os
import time
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
    
    def __init__(self, leica_port: str, laser_port: str, baudrate: int = 115200):
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
        self._command_queue = []
        
    def run(self):
        self.is_running = True
        
        try:
            # Open serial ports with non-blocking rapid polling
            # Use serial_for_url to handle both COM ports and socket:// URLs
            self.leica_serial = serial.serial_for_url(self.leica_port, baudrate=self.baudrate, timeout=0.001)
            self.laser_serial = serial.serial_for_url(self.laser_port, baudrate=self.baudrate, timeout=0.001)
            self.logMessage.emit(f"[BRIDGE] Connected: {self.leica_port} <-> {self.laser_port} at {self.baudrate} baud.")
            self.logMessage.emit(f"[BRIDGE] Logging hex traffic to: {self.log_file_path}")
            
            with open(self.log_file_path, "a") as logfile:
                logfile.write(f"\n--- SESSION START: {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                
                # Main Bridge Loop
                while self.is_running:
                    # Send any pending commands from the GUI directly to laser
                    while self._command_queue:
                        cmd = self._command_queue.pop(0)
                        self.laser_serial.write(cmd.encode('utf-8'))
                        self.txRxData.emit("LASER_TX", cmd.encode('utf-8').hex(' '))
                    
                    # 1. Read from Leica
                    leica_bytes = self.leica_serial.read(self.leica_serial.in_waiting or 1)
                    if leica_bytes:
                        hex_raw = leica_bytes.hex(' ')
                        self.txRxData.emit("LEICA_RX", hex_raw)
                        
                        if not self.spoofing_enabled:
                            # State 1: True Pass-Through
                            self.laser_serial.write(leica_bytes)
                            self.txRxData.emit("LASER_TX", hex_raw)
                            logfile.write(f"[LEICA -> LASER] {hex_raw}\n")
                        else:
                            # State 2: Intercept & Edit (Pass-Through with Replacements)
                            text = leica_bytes.decode('utf-8', errors='ignore')
                            original_text = text
                            for rule in self.spoof_config.get("commands", []):
                                if rule["target"] and rule["target"] in text:
                                    text = text.replace(rule["target"], rule["replacement"])
                                    
                            out_bytes = text.encode('utf-8')
                            self.laser_serial.write(out_bytes)
                            
                            hex_out = out_bytes.hex(' ')
                            self.txRxData.emit("LASER_TX", hex_out)
                            
                            if text != original_text:
                                logfile.write(f"[LEICA -> SPOOFED LASER] {hex_out} (Changed from: {hex_raw})\n")
                            else:
                                logfile.write(f"[LEICA -> LASER] {hex_out}\n")
                    
                    # 2. Read from Laser
                    laser_bytes = self.laser_serial.read(self.laser_serial.in_waiting or 1)
                    if laser_bytes:
                        hex_raw = laser_bytes.hex(' ')
                        self.txRxData.emit("LASER_RX", hex_raw)
                        
                        if not self.spoofing_enabled:
                            # State 1: True Pass-Through
                            self.leica_serial.write(laser_bytes)
                            self.txRxData.emit("LEICA_TX", hex_raw)
                            logfile.write(f"[LASER -> LEICA] {hex_raw}\n")
                        else:
                            # State 2: Intercept & Edit (Pass-Through with Replacements)
                            text = laser_bytes.decode('utf-8', errors='ignore')
                            original_text = text
                            for rule in self.spoof_config.get("responses", []):
                                if rule["target"] and rule["target"] in text:
                                    text = text.replace(rule["target"], rule["replacement"])
                                    
                            out_bytes = text.encode('utf-8')
                            self.leica_serial.write(out_bytes)
                            
                            hex_out = out_bytes.hex(' ')
                            self.txRxData.emit("LEICA_TX", hex_out)
                            
                            if text != original_text:
                                logfile.write(f"[LASER -> SPOOFED LEICA] {hex_out} (Changed from: {hex_raw})\n")
                            else:
                                logfile.write(f"[LASER -> LEICA] {hex_out}\n")
                            
                    logfile.flush()
                    self.msleep(1)
                    
        except serial.SerialException as e:
            self.errorOccurred.emit(f"[ERROR] Serial Port Exception: {str(e)}")
            self.logMessage.emit(f"[ERROR] Bridge stopped due to exception.")
        except Exception as e:
            self.errorOccurred.emit(f"[ERROR] Unexpected Exception: {str(e)}")
            self.logMessage.emit(f"[ERROR] Bridge stopped due to exception.")
        finally:
            self._cleanup_ports()
            self.is_running = False

    def send_laser_command(self, cmd_string: str):
        """Enqueue a command to be sent to the laser on the next bridge loop."""
        self._command_queue.append(cmd_string)

    def _cleanup_ports(self):
        """Safely close serial ports."""
        if hasattr(self, 'leica_serial') and self.leica_serial.is_open:
            self.leica_serial.close()
        if hasattr(self, 'laser_serial') and self.laser_serial.is_open:
            self.laser_serial.close()
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
