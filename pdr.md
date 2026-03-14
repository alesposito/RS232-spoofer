# Preliminary Design Review (PDR): SP5-CUBE MitM Serial Gateway

**Author:** Alessandro  
**Institution:** Brunel University of London | cengem.org  
**Date:** March 13, 2026  

---

## 1. Executive Summary
This document outlines the architecture and implementation strategy for a software-based Man-in-the-Middle (MitM) serial gateway. The system will intercept RS-232 communications between a Leica SP5 confocal microscope and a Coherent CUBE 405nm laser, enabling external modulation of the laser via SMB while autonomously spoofing Continuous Wave (CW) hardware polling responses back to the Leica controller.

## 2. Google Antigravity Integration Strategy
The software will be developed utilizing Google Antigravity to accelerate the boilerplate generation and thread management. The project will be divided into asynchronous tasks delegated via the Agent Manager.

* **Artifact-Driven Verification:** Agents will be required to produce verifiable Artifacts (e.g., automated `pytest` logs for the serial buffer routing) before physical hardware deployment.
* **Multi-Agent Orchestration:** * *Agent Alpha* will be assigned the PyQt6 View layer (GUI scaffolding).
    * *Agent Beta* will be assigned the Model layer (the asynchronous `pyserial` threading logic).
    * *Agent Gamma* will be assigned exclusively to the spoofing algorithm and buffer management.

## 3. System Architecture (Model-View-Controller)
To prevent the OS from dropping serial bytes and violating the SP5's strict timeout thresholds, the GUI must be completely decoupled from the hardware polling.

### 3.1 The View (PyQt6 Main Thread)
* **Responsibilities:** Renders the dark-mode control interface, displays active COM ports, and handles user input for state toggling.
* **Antigravity Prompt Directive:** *"Build a PyQt6 UI with two QComboBoxes for port selection, a 'Scan Ports' QPushButton, and a primary QToggleButton for 'Pass-Through' vs 'Modulation'. Ensure all interactions emit standard PyQt Signals rather than executing blocking code."*

### 3.2 The Controller (QThread Dispatcher)
* **Responsibilities:** Instantiates the background hardware threads and safely routes PyQt Signals to the serial worker objects without blocking the event loop.

### 3.3 The Model (Serial Daemons)
* **Responsibilities:** Two independent, persistent `pyserial` threads running concurrently. 
* **Data Flow State 1 (Pass-Through):** Thread 1 reads `COM_LEICA` and pushes raw bytes to Thread 2 (`COM_LASER`), and vice versa. Latency must remain under 2ms.
* **Data Flow State 2 (Spoofing):** Thread 1 intercepts Leica polling strings, drops them, and transmits a hardcoded `"Status OK"` string back to the SP5. Thread 2 locks external Rx and transmits the `EXT=1` modulation command to the laser.

## 4. Hardware and Protocol Risks
1.  **Buffer Overrun / Timeout:** Standard Windows USB polling operates at 16ms. The FTDI drivers must be manually forced to a 1ms latency timer in the Device Manager.
2.  **Handshake Ignorance:** The precise polling string expected by the Leica SP5 is currently unknown. 
    * *Mitigation:* The initial Antigravity agent task will be to write a passive "sniffer" script that merely logs the hex data traversing the FTDI cables to a `.txt` file for reverse-engineering.

## 5. Development Milestones
* **Phase 1:** Agent-generated PyQt6 GUI and Port Scanner execution.
* **Phase 2:** Passive serial sniffing and protocol documentation.
* **Phase 3:** Integration of spoofing logic and live hardware testing.
    * **3.1 Tx/Rx Visualization:** Introduce real-time hex visualization of Tx and Rx data from both cables in the GUI, operating in pass-through mode by default.
    * **3.2 Laser Control Pane:** Create a dedicated and highly visual GUI pane displaying all laser parameters (Power, L, CW, EXT) that can be manipulated and queried (`?S`) via the COM port directly from the application.
* **Phase 4:** Emulation and Virtual Testing.
    * **4.1 Digital Twin:** Implement TCP-based virtual laser and microscope controllers to simulate RS-232 traffic.
    * **4.2 Port Emulation:** Utilize `socket://` serial transport to verify the MitM logic and spoofing rules without physical hardware dependencies.