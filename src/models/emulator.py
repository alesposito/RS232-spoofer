import socket
import threading
import time
from PyQt6.QtCore import QThread, pyqtSignal

class LaserEmulator(QThread):
    """
    Simulates the CUBE Laser hardware.
    Listens on a TCP port and responds to RS-232 commands.
    """
    stateChanged = pyqtSignal(dict) # Emits the internal state whenever it changes
    
    def __init__(self, port=9999):
        super().__init__()
        self.port = port
        self.is_running = False
        self._state = {
            "power": 0,
            "laser_on": False,
            "cw_mode": True,
            "ext_analog": False,
            "base_temp": 25.4,
            "hours": 123.4,
            "faults": "0"
        }

    def run(self):
        self.is_running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('localhost', self.port))
        server.listen(1)
        server.settimeout(1.0)
        
        print(f"[EMU-LASER] Listning on port {self.port}...")
        
        while self.is_running:
            try:
                conn, addr = server.accept()
                with conn:
                    conn.settimeout(1.0)
                    while self.is_running:
                        try:
                            data = conn.recv(1024)
                            if not data:
                                break
                            
                            command = data.decode('utf-8').strip().upper()
                            response = self.process_command(command)
                            if response:
                                conn.sendall(response.encode('utf-8') + b"\r\n")
                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[EMU-LASER] Error: {e}")
                            break
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    print(f"[EMU-LASER] Server Error: {e}")
                break
        
        server.close()

    def stop(self):
        self.is_running = False
        self.wait()

    def process_command(self, cmd):
        # Basic parsing for emulation
        if cmd == "?S":
            # Return status string
            l_bit = "1" if self._state["laser_on"] else "0"
            m_bit = "1" if self._state["cw_mode"] else "0" # Simple map for demo
            return f"Status: L={l_bit} CW={m_bit} P={self._state['power']} F={self._state['faults']}"
        
        elif cmd.startswith("P="):
            try:
                self._state["power"] = int(cmd[2:])
                self.stateChanged.emit(dict(self._state))
                return "OK"
            except: return "ERROR"
            
        elif cmd.startswith("L="):
            self._state["laser_on"] = (cmd[2:] == "1")
            self.stateChanged.emit(dict(self._state))
            return "OK"
            
        elif cmd.startswith("CW="):
            self._state["cw_mode"] = (cmd[3:] == "1")
            self.stateChanged.emit(dict(self._state))
            return "OK"
            
        elif cmd.startswith("EXT="):
            self._state["ext_analog"] = (cmd[4:] == "1")
            self.stateChanged.emit(dict(self._state))
            return "OK"
            
        elif cmd == "?BT": return str(self._state["base_temp"])
        elif cmd == "?HH": return str(self._state["hours"])
        elif cmd == "?F": return self._state["faults"]
        
        return None # Default: No response or unknown

class LeicaEmulator(QThread):
    """
    Simulates the Leica SP5 Hardware controller.
    Periodically sends polling commands down the line.
    """
    def __init__(self, port=9998):
        super().__init__()
        self.port = port
        self.is_running = False

    def run(self):
        self.is_running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('localhost', self.port))
        server.listen(1)
        server.settimeout(1.0)
        
        print(f"[EMU-LEICA] Listning on port {self.port}...")
        
        while self.is_running:
            try:
                conn, addr = server.accept()
                with conn:
                    # Simulation: Periodically send "?S" every 2 seconds
                    while self.is_running:
                        try:
                            # Send poll
                            conn.sendall(b"?S\r")
                            # Wait and receive response (ignore it, just like SP5 does mostly)
                            data = conn.recv(1024) 
                            time.sleep(2.0)
                        except (socket.timeout, ConnectionResetError):
                            break
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    print(f"[EMU-LEICA] Server Error: {e}")
                break
        
        server.close()

    def stop(self):
        self.is_running = False
        self.wait()
