import os
import sys
import json
import subprocess
import requests
import time
import re

# Ensure src is in path
sys.path.append(os.getcwd())
try:
    from src.analysis import protocol_manager
except ImportError:
    pass

class DeepSeekAgent:
    def __init__(self):
        self.api_key = self._load_api_key()
        self.api_url = "https://api.deepseek.com/chat/completions"
        self.model = "deepseek-chat" 
        self.history = []
        self.llm_dir = os.path.dirname(os.path.abspath(__file__))

        # Tool Mapping
        self.TOOL_MAP = {
            'serial_scanner': 'connection.serial_scanner',
            'baud_detector': 'connection.baud_detector',
            'flow_control_scanner': 'connection.flow_control_scanner',
            'physical_forensics': 'connection.physical_forensics',
            'handshake_replay': 'connection.handshake_replay',
            
            'data_logger': 'acquisition.data_logger',
            'universal_logger': 'acquisition.universal_logger',
            'pcap_extractor': 'acquisition.pcap_extractor',
            
            'framing_scanner': 'framing.framing_scanner',
            'packet_finder': 'framing.packet_finder',
            'checksum_cracker': 'framing.checksum_cracker',
            
            'stat_analyzer': 'analysis.stat_analyzer',
            'structure_bruteforcer': 'analysis.structure_bruteforcer',
            'ai_explorer': 'analysis.ai_explorer',
            'semantic_explorer': 'analysis.semantic_explorer',
            'entropy_analyzer': 'analysis.entropy_analyzer',
            'lut_detector': 'analysis.lut_detector',
            'protocol_analyzer': 'analysis.protocol_analyzer',

            'visualizer': 'signals.visualizer',
            'waveform_profiler': 'signals.waveform_profiler',
            'fft_analyzer': 'signals.fft_analyzer',

            'command_fuzzer': 'simulation.command_fuzzer',
            'session_fuzzer': 'simulation.session_fuzzer',

            'crypto_scanner': 'security.crypto_scanner',
            'complex_protocol': 'security.complex_protocol',
            
            'timing_analyzer': 'utils.timing_analyzer',
            'web_search': 'utils.web_client search',
            'web_read': 'utils.web_client read',
            'update_knowledge': 'llm.knowledge_manager update',
            'generate_protocol': 'llm.protocol_generator'
        }

    def _load_api_key(self):
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            try:
                with open(".env", "r") as f:
                    for line in f:
                        if line.startswith("DEEPSEEK_API_KEY"):
                            key = line.strip().split("=", 1)[1]
                            break
            except: pass
        return key

    def _read_file(self, filename):
        path = os.path.join(self.llm_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def get_system_prompt(self):
        # Load external MD files
        base_prompt = self._read_file("system_prompt.md")
        knowledge = self._read_file("acquired_knowledge.md")
        tools_doc = self._read_file("available_tools.md")
        
        # Load dynamic protocol state
        try:
            proto = protocol_manager.load_protocol()
            proto_json = json.dumps(proto, indent=2)
        except:
            proto_json = "{}"

        # Assemble Prompt
        full_prompt = f"""
{base_prompt}

[ACQUIRED KNOWLEDGE]
{knowledge}

[CURRENT PROTOCOL STATE (JSON)]
{proto_json}

[AVAILABLE TOOLS REFERENCE]
{tools_doc}

[TOOL LIST FOR JSON CALLS]
{', '.join(self.TOOL_MAP.keys())}
"""
        return full_prompt

    def run_tool(self, tool_name, args):
        module_path = self.TOOL_MAP.get(tool_name)
        if not module_path:
            return f"Error: Tool '{tool_name}' not found."
            
        print(f"\n[System] Executing: python -m src.{module_path} {args}")
        try:
            cmd = f"python -m src.{module_path} {args}"
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=60).decode('utf-8', errors='ignore')
            return output
        except subprocess.TimeoutExpired:
            return "Error: Tool execution timed out (60s)."
        except subprocess.CalledProcessError as e:
            return f"Error: {e.output.decode('utf-8', errors='ignore')}"
        except Exception as e:
            return f"Error executing tool: {e}"

    def chat_round(self, user_input):
        self.history.append({"role": "user", "content": user_input})
        
        response = self.call_llm()
        if not response: return

        tool_call = self.parse_tool_call(response)
        
        if tool_call:
            tool_name = tool_call['name']
            tool_args = tool_call['parameters']
            
            print(f"\n[AI] Requesting Tool: {tool_name} ({tool_args})")
            tool_output = self.run_tool(tool_name, tool_args)
            
            if len(tool_output) > 2000:
                tool_output = tool_output[:2000] + "\n...[Output Truncated]..."
                
            print(f"[System] Output received ({len(tool_output)} chars). Sending back to AI...")
            
            self.history.append({"role": "assistant", "content": response})
            self.history.append({"role": "user", "content": f"Tool Output:\n{tool_output}"})
            
            final_response = self.call_llm()
            if final_response:
                print(f"\n[AI]: {final_response}")
                self.history.append({"role": "assistant", "content": final_response})
        else:
            print(f"\n[AI]: {response}")
            self.history.append({"role": "assistant", "content": response})

    def call_llm(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        messages = [{"role": "system", "content": self.get_system_prompt()}] + self.history
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 1000
        }
        
        try:
            print(".", end="", flush=True)
            resp = requests.post(self.api_url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"\n[Error] LLM Call Failed: {e}")
            if 'resp' in locals():
                print(resp.text)
            return None

    def parse_tool_call(self, content):
        match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if data.get("type") == "function":
                    return data["function"]
            except: pass
        try:
            data = json.loads(content)
            if data.get("type") == "function":
                return data["function"]
        except: pass
        return None

    def start(self):
        if not self.api_key:
            print("Error: DEEPSEEK_API_KEY not set in .env")
            return

        print("\n" + "="*50)
        print("   VitalParser AI Chatbot")
        print("   Type 'exit' to quit. Ask me to run tools!")
        print("="*50)
        
        while True:
            try:
                u_input = input("\nUser: ")
                if u_input.lower() in ['exit', 'quit']:
                    break
                if not u_input.strip():
                    continue
                self.chat_round(u_input)
            except KeyboardInterrupt:
                print("\n[Interrupted]")
                break

if __name__ == "__main__":
    agent = DeepSeekAgent()
    agent.start()
