import sys
import os
import subprocess
import time
import re
import serial.tools.list_ports

# Ensure src is in path
sys.path.append(os.getcwd())
try:
    from src.analysis import protocol_manager
except ImportError:
    # If starting from root, this might fail if __init__.py is missing or path issues
    pass

class PipelineWizard:
    def __init__(self):
        try:
            self.proto = protocol_manager.load_protocol()
        except:
            self.proto = {}
            
        self.results_dir = "results"
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

    def get_latest_capture(self):
        files = [f for f in os.listdir(self.results_dir) if f.startswith('capture_') and f.endswith('.bin')]
        if not files:
            return None
        return os.path.join(self.results_dir, max(files, key=lambda f: os.path.getctime(os.path.join(self.results_dir, f))))

    def select_serial_port(self):
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("No serial ports found!")
            return input("Enter Port Manually (e.g. COM3): ")
        
        print("\nAvailable Serial Ports:")
        for i, p in enumerate(ports):
            print(f"{i+1}. {p.device} - {p.description}")
            
        print("0. Enter Manually")
        
        while True:
            choice = input("Select Port (0-{}): ".format(len(ports)))
            if choice == '0':
                return input("Enter Port Manually: ")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(ports):
                    return ports[idx].device
            except ValueError:
                pass
            print("Invalid selection.")

    def run_cmd(self, name, cmd):
        print(f"\n>> RUNNING: {name}")
        print(f"   Command: {cmd}")
        ret = subprocess.call(cmd, shell=True)
        if ret == 0:
            print(f"   [SUCCESS]")
            return True
        else:
            print(f"   [FAILED/CANCELLED]")
            return False

    def run_cmd_capture(self, name, cmd):
        print(f"\n>> RUNNING: {name} (Capturing Output...)")
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8', errors='ignore')
            print(output)
            print("   [SUCCESS]")
            return output
        except subprocess.CalledProcessError as e:
            print(e.output.decode('utf-8', errors='ignore'))
            print("   [FAILED]")
            return None

    # --- Phase Methods (Standard) ---
    def phase_discovery(self):
        print("\n--- Phase 1: Discovery (Physical Layer) ---")
        print("1. Standard Serial Scanner (Baud/Parity)")
        print("2. Smart Baud Detector (Statistical - Recommended)")
        print("3. Physical Forensics (Inverted Logic / Control Lines)")
        c = input("Select tool (1-3): ")
        if c == '1': self.run_cmd("Serial Scanner", "python -m src.connection.serial_scanner")
        elif c == '2': 
            port = self.select_serial_port()
            self.run_cmd("Baud Detector", f"python -m src.connection.baud_detector {port}")
        elif c == '3':
            port = self.select_serial_port()
            self.run_cmd("Physical Forensics", f"python -m src.connection.physical_forensics {port}")

    def phase_acquisition(self):
        print("\n--- Phase 2: Acquisition (Data Logger) ---")
        self.proto = protocol_manager.load_protocol()
        port = self.proto.get('connection', {}).get('port', '')
        baud = self.proto.get('connection', {}).get('baudrate', 9600)
        if not port:
            port = self.select_serial_port()
            baud = input("Enter Baud: ")
        print(f"Target: {port} @ {baud}")
        if input("Start Logging? (y/n): ").lower() == 'y':
            self.run_cmd("Data Logger", f"python -m src.acquisition.data_logger {port} {baud}")

    def phase_framing(self):
        print("\n--- Phase 3: Structure & Framing ---")
        f = self.get_latest_capture()
        if not f: print("No capture file."); return
        print(f"Using: {f}")
        print("1. Packet Finder (Fixed Headers)")
        print("2. Framing Master (HDLC/SLIP/ASCII/VarLen)")
        print("3. Stat Analyzer (Autocorrelation/Markov)")
        c = input("Select tool (1-3): ")
        if c == '1': self.run_cmd("Packet Finder", f"python -m src.framing.packet_finder {f}")
        elif c == '2': self.run_cmd("Framing Scanner", f"python -m src.framing.framing_scanner {f}")
        elif c == '3': 
             lag = input("Max Lag (default 200): ") or "200"
             self.run_cmd("Stat Analyzer", f"python -m src.analysis.stat_analyzer {f} {lag}")

    def phase_semantics(self):
        print("\n--- Phase 4: Semantics & AI ---")
        f = self.get_latest_capture()
        if not f: return
        ps = self.proto.get('packet_structure', {}).get('fixed_length', 0)
        if ps == 0: ps = input("Enter Packet Size (0 if unknown): ")
        print("1. Protocol Analyzer (Manual)")
        print("2. Semantic Explorer (Auto-Range/ASCII)")
        print("3. AI Hypothesis Engine")
        print("4. LUT Detector")
        print("5. Entropy Analyzer")
        c = input("Select tool (1-5): ")
        if c == '1': 
            val = input("Value to search: ")
            self.run_cmd("Protocol Analyzer", f"python -m src.analysis.protocol_analyzer {f} {val}")
        elif c == '2': self.run_cmd("Semantic Explorer", f"python -m src.analysis.semantic_explorer {f} {ps}")
        elif c == '3': self.run_cmd("AI Explorer", f"python -m src.analysis.ai_explorer {f} {ps}")
        elif c == '4': self.run_cmd("LUT Detector", f"python -m src.analysis.lut_detector {f} {ps}")
        elif c == '5': self.run_cmd("Entropy Analyzer", f"python -m src.analysis.entropy_analyzer {f} {ps}")

    def phase_waveforms(self):
        print("\n--- Phase 5: Waveforms & Signals ---")
        f = self.get_latest_capture()
        if not f: return
        print("1. Visualizer")
        print("2. Waveform Profiler")
        print("3. FFT Analyzer")
        c = input("Select tool (1-3): ")
        if c == '1': self.run_cmd("Visualizer", f"python -m src.signals.visualizer {f}")
        elif c == '2': 
            ps = input("Packet Size: "); off = input("Offset: ")
            self.run_cmd("Waveform Profiler", f"python -m src.signals.waveform_profiler {f} {ps} {off}")
        elif c == '3':
            ps = input("Packet Size: "); off = input("Offset: ")
            self.run_cmd("FFT Analyzer", f"python -m src.signals.fft_analyzer {f} {ps} {off}")

    def phase_advanced(self):
        print("\n--- Phase 7: Advanced / God Mode ---")
        print("1. Command Fuzzer")
        print("2. Session Fuzzer")
        print("3. Checksum Cracker")
        print("4. Crypto Scanner")
        print("5. Behavior Modeler")
        print("6. Complex Protocol")
        c = input("Select tool (1-6): ")
        port = self.proto.get('connection', {}).get('port', '')
        baud = self.proto.get('connection', {}).get('baudrate', 9600)
        if not port and c in ['1', '2', '5']: port = self.select_serial_port()
        f = self.get_latest_capture()
        ps = self.proto.get('packet_structure', {}).get('fixed_length', 0)

        if c == '1': self.run_cmd("Command Fuzzer", f"python -m src.simulation.command_fuzzer {port} {baud}")
        elif c == '2': self.run_cmd("Session Fuzzer", f"python -m src.simulation.session_fuzzer {port} {baud}")
        elif c == '3': self.run_cmd("Checksum Cracker", f"python -m src.framing.checksum_cracker {f} {ps}")
        elif c == '4': self.run_cmd("Crypto Scanner", f"python -m src.security.crypto_scanner {f} {ps}")
        elif c == '5': self.run_cmd("Behavior Modeler", f"python -m src.utils.behavior_modeler {port} {baud}")
        elif c == '6': self.run_cmd("Complex Protocol", f"python -m src.security.complex_protocol {f} {ps}")
    def production(self):
        self.run_cmd("Universal Logger", "python -m src.acquisition.universal_logger")
    def generate_docs(self):
         self.run_cmd("Doc Generator", "python -m src.utils.doc_generator")

    # --- DEEP AUTO PILOT ---
    def deep_auto_pilot(self):
        print("\n" + "="*50)
        print("    🚀 DEEP AUTO-PILOT MODE 🚀")
        print("    Adaptive Reverse Engineering Chain")
        print("="*50)
        
        # 1. Port Selection
        port = self.select_serial_port()
        
        # 2. Baud Detection with Feedback
        print("\n[Step 1] Detecting Baud Rate...")
        output = self.run_cmd_capture("Smart Baud Detect", f"python -m src.connection.baud_detector {port}")
        
        detected_baud = None
        if output:
            match = re.search(r"Detected Baud:\s*(\d+)", output)
            if match:
                detected_baud = match.group(1)
                print(f"-> Auto-Detected Baud: {detected_baud}")
                
        if not detected_baud:
            print("Could not auto-detect baud. Enter manually.")
            detected_baud = input("Baud Rate: ")
            
        protocol_manager.update_connection(port, int(detected_baud))
        
        # 3. Capture Data
        print("\n[Step 2] Acquiring Data Stream...")
        print("   Auto-Pilot will log for 15 seconds. Please ensure device is sending data.")
        input("   Press ENTER to start logging...")
        
        print("   (Data Logger runs until you press Ctrl+C or 15s timeout if supported)")
        self.run_cmd("Data Logger", f"python -m src.acquisition.data_logger {port} {detected_baud}")
        
        f = self.get_latest_capture()
        if not f:
            print("Capture failed. Aborting.")
            return

        print(f"\n-> analyzing capture: {f}")

        # 4. Framing Analysis (The Brain)
        print("\n[Step 3] Analyzing Structure & Framing...")
        
        packet_size = 0
        
        # A. Try Framing Scanner
        out_frame = self.run_cmd_capture("Framing Scanner", f"python -m src.framing.framing_scanner {f}")
        if out_frame:
            # Look for regex "Detected Fixed Length: 40"
            m = re.search(r"Detected Fixed Length:\s*(\d+)", out_frame)
            if m:
                packet_size = int(m.group(1))
                print(f"-> Struct Found: Fixed Length {packet_size} bytes")
            
            if "HDLC" in out_frame: print("-> Struct Found: HDLC Framing")
            if "SLIP" in out_frame: print("-> Struct Found: SLIP Framing")

        # B. If no packet size, try Stat Analyzer (Autocorrelation)
        if packet_size == 0:
            print("   Framing Scanner unsure. Trying Statistical Autocorrelation...")
            out_stat = self.run_cmd_capture("Stat Analyzer", f"python -m src.analysis.stat_analyzer {f} 200")
            if out_stat:
                 # Look for "Lag 40:"
                 m = re.search(r"Lag\s+(\d+):\s+Correlation", out_stat)
                 if m:
                     packet_size = int(m.group(1))
                     print(f"-> Stat Found: Strong Cyclicity at {packet_size} bytes")
        
        if packet_size == 0:
            print("\n[Decision] Could not automatically determine packet structure.")
            print("Deep analysis requires packet size.")
            try:
                packet_size = int(input("Enter Packet Size manually (or 0 to abort): "))
            except: pass
            
        if packet_size > 0:
            print(f"\n[Step 4] Deep Inspection (Packet Size: {packet_size})")
            
            # 5. Security Check
            print("   Checking for Encryption/Entropy...")
            self.run_cmd("Crypto Scanner", f"python -m src.security.crypto_scanner {f} {packet_size}")
            
            # 6. Semantics (AI)
            print("   Running AI Hypothesis Engine...")
            self.run_cmd("AI Explorer", f"python -m src.analysis.ai_explorer {f} {packet_size}")
            
            # 7. Checksums
            print("   Cracking Checksums...")
            self.run_cmd("Checksum Cracker", f"python -m src.framing.checksum_cracker {f} {packet_size}")
            
            # 8. Complexity
            print("   Checking for Multiplexing...")
            self.run_cmd("Complex Protocol", f"python -m src.security.complex_protocol {f} {packet_size}")
            
        print("\n[Step 5] Auto-Pilot Finished. Check reports above.")


    def main_menu(self):
        while True:
            print(f"\n{'='*40}")
            print("   Gwi-ma v0.1.0 Reverse Engineering Suite   ")
            print(f"{'='*40}")
            print("1. Discovery        (Scanner, Baud)")
            print("2. Acquisition      (Logger)")
            print("3. Framing          (Headers, Stats)")
            print("4. Semantics        (AI, Ranges, LUT)")
            print("5. Waveforms        (Vis, FFT)")
            print("6. Advanced / God   (Crypto, Fuzz, CRC)")
            print("7. Production       (Universal Logger)")
            print("8. Documentation    (Generate Spec)")
            print("9. AUTO-PILOT (Adaptive)")
            print("10. Gwi-ma Agent (Interactive AI)")
            print("11. IntelliVue Live Monitor (Standalone)")
            print("12. Run Tests (Verification)")
            print("0. Exit")
            
            c = input("\nSelect Phase (0-12): ")
            
            if c == '1': self.phase_discovery()
            elif c == '2': self.phase_acquisition()
            elif c == '3': self.phase_framing()
            elif c == '4': self.phase_semantics()
            elif c == '5': self.phase_waveforms()
            elif c == '6': self.phase_advanced()
            elif c == '7': self.production()
            elif c == '8': self.generate_docs()
            elif c == '9': self.deep_auto_pilot()
            elif c == '10': 
                from src.llm import deepseek_agent
                agent = deepseek_agent.DeepSeekAgent()
                agent.start()
            elif c == '11':
                port = self.select_serial_port()
                # Run the standalone script in root
                self.run_cmd("IntelliVue Monitor", f"python intellivue_monitor.py {port}")
            elif c == '12':
                self.run_cmd("Core Tests", "python tests/test_gwi_ma_core.py")
            elif c == '0': sys.exit()

if __name__ == "__main__":
    app = PipelineWizard()
    app.main_menu()
