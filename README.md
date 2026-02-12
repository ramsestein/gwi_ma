# Gwi-ma v0.1.0

**Gwi-ma** (Ghost in the Machine) is an **Autonomous Reverse Engineering Agent** designed to analyze, decode, and interact with unknown serial protocols.

Powered by **DeepSeek-V3** and a specialized toolkit, Gwi-ma can autonomously explore physical connections, discover baud rates, identify framing structures, and decipher semantic meaning from binary streams.

---

## 🚀 Core Architecture

The system is built around an Interactive Agent Loop (`src/llm/deepseek_agent.py`) that:
1.  **Observes**: Reads serial data and file dumps.
2.  **Reasons**: Uses an LLM to hypothesize about protocol structures.
3.  **Acts**: Executes local Python tools to verify hypotheses (e.g., "Run CRC cracker on this file").
4.  **Learns**: Updates its persistent knowledge base with confirmed findings.

### Agent Capabilities
- **Turn-based Chat**: Interact naturally ("Analyze this capture", "Find the baud rate").
- **Tool Execution**: The agent autonomously runs scanners, loggers, and analyzers.
- **Web Research**: Can search the internet for datasheets and standards.
- **Long-term Memory**: Persists discovered protocol details.

---

## 📂 Project Structure

The codebase is organized by function in `src/`:

| Directory | Purpose |
| :--- | :--- |
| **`src/llm/`** | **The Brain**. Contains the `deepseek_agent`, system prompts, and knowledge base. |
| **`src/connection/`** | **Physical Layer**. Tools for baud detection (`baud_detector.py`) and handshakes. |
| **`src/acquisition/`** | **Data Layer**. Loggers (`data_logger.py`) and PCAP extractors. |
| **`src/framing/`** | **Transport Layer**. Scanners for SLIP/HDLC and packet finders. |
| **`src/analysis/`** | **Semantic Layer**. Entropy analysis, structure bruteforcing, and AI explorers. |
| **`src/signals/`** | **Physical Signals**. Waveform profilers and FFT analysis. |
| **`src/simulation/`** | **Active Probing**. Fuzzers and simulators. |
| **`src/security/`** | **Crypto**. Encryption detection and complexity analysis. |
| **`src/utils/`** | **Helpers**. Web clients, doc generators, and bridges. |

> For a complete list of tools and their arguments, see **[`src/llm/available_tools.md`](src/llm/available_tools.md)**.

---

## 🧠 Knowledge System

Gwi-ma uses a set of Markdown files to maintain context:

1.  **`src/llm/system_prompt.md`**: Defines the agent's persona and rules.
2.  **`src/llm/available_tools.md`**: Manual of available tools (Dynamically loaded).
3.  **`src/llm/acquired_knowledge.md`**: **The Memory**. The agent writes confirmed facts here (e.g., "Protocol is SLIP at 115200").

---

## 🔬 Case Study: IntelliVue MX750

This repository includes a proof-of-concept driver for the **Philips IntelliVue MX750** patient monitor, reverse-engineered using Gwi-ma.

*   **`intellivue_monitor.py`**: A standalone, production-ready script to connect, handshake, and stream vital signs from the device.
*   **`results/protocol_definition.json`**: The complete protocol specification derived by the agent.

---

## 🛠️ Usage

### 1. Interactive Agent (Recommended)
Launch the Gwi-ma Agent to start a reverse engineering session:
```bash
python run_pipeline.py
# Select Option 10: DeepSeek Agent
```

### 2. Standalone Monitor (IntelliVue)
To use the finished IntelliVue driver:
```bash
python intellivue_monitor.py COM3
```

### 3. Manual Tool Usage
You can explore the toolkit manually:
```bash
# Example: Detect Baud Rate
python -m src.connection.baud_detector COM3

# Example: Analyze a Capture
python -m src.analysis.structure_bruteforcer capture.bin
```

---

*Gwi-ma v0.1.0 - Unveiling the Ghost in the Machine.*
