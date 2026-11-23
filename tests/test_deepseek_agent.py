import json
import os
import subprocess
import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.llm import deepseek_agent


def llm_reply(content):
    response = MagicMock()
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    return response


class TestDeepSeekAgent(unittest.TestCase):

    def setUp(self):
        self.agent = deepseek_agent.DeepSeekAgent()
        if not self.agent.api_key:
            self.agent.api_key = "dummy_key_for_testing"
        # Keep the agent from writing results/protocol_definition.json during tests.
        patcher = patch('src.llm.deepseek_agent.protocol_manager.load_protocol', return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_prompt_consistency(self):
        """The system prompt carries the instructions and every callable tool."""
        prompt = self.agent.get_system_prompt()

        self.assertIn("[TOOL EXECUTION FORMAT]", prompt)
        self.assertIn("[AVAILABLE TOOLS REFERENCE]", prompt)
        self.assertIn("[TOOL LIST FOR JSON CALLS]", prompt)
        for tool in ("baud_detector", "framing_scanner", "usbpcap_conversation"):
            self.assertIn(tool, prompt)

    def test_tool_execution(self):
        """Tools run as modules under src/ with a timeout."""
        with patch('subprocess.check_output', return_value=b"Detected Baud: 9600") as mock_exec, \
             patch('sys.stdout', new_callable=StringIO):
            output = self.agent.run_tool("baud_detector", "COM3")

        mock_exec.assert_called_with("python -m src.connection.baud_detector COM3",
                                     shell=True, stderr=subprocess.STDOUT, timeout=60)
        self.assertIn("Detected Baud: 9600", output)
        self.assertIn("not found", self.agent.run_tool("no_such_tool", ""))

    def test_every_mapped_tool_exists(self):
        """Every entry in TOOL_MAP points to a module that exists."""
        root = os.path.join(os.path.dirname(__file__), '..', 'src')
        for name, target in self.agent.TOOL_MAP.items():
            module = target.split()[0]
            path = os.path.join(root, *module.split('.')) + '.py'
            self.assertTrue(os.path.exists(path), f"{name} -> {path}")

    def test_api_connection_structure(self):
        """The API request has the right URL, auth header, model and messages."""
        self.agent.history = [{"role": "user", "content": "hello"}]
        with patch('src.llm.deepseek_agent.requests.post', return_value=llm_reply("hi")) as mock_post, \
             patch('sys.stdout', new_callable=StringIO):
            reply = self.agent.call_llm()

        self.assertEqual(reply, "hi")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.deepseek.com/chat/completions")
        self.assertEqual(kwargs['headers']['Authorization'], f"Bearer {self.agent.api_key}")
        self.assertEqual(kwargs['json']['model'], "deepseek-chat")
        messages = kwargs['json']['messages']
        self.assertEqual(messages[0]['role'], "system")
        self.assertEqual(messages[1:], [{"role": "user", "content": "hello"}])

    def test_agent_logic_runs_requested_tool(self):
        """A tool call in the reply is executed and its output goes back to the LLM."""
        tool_call = json.dumps({"type": "function",
                                "function": {"name": "baud_detector", "parameters": "COM3"}})
        replies = [llm_reply(f"Let me check.\n```json\n{tool_call}\n```"),
                   llm_reply("The device runs at 9600 baud.")]

        with patch('src.llm.deepseek_agent.requests.post', side_effect=replies), \
             patch.object(self.agent, 'run_tool', return_value="Detected Baud: 9600") as mock_tool, \
             patch('sys.stdout', new_callable=StringIO):
            self.agent.chat_round("What is the baud rate on COM3?")

        mock_tool.assert_called_once_with("baud_detector", "COM3")
        self.assertEqual(self.agent.history[-2], {"role": "user", "content": "Tool Output:\nDetected Baud: 9600"})
        self.assertEqual(self.agent.history[-1], {"role": "assistant", "content": "The device runs at 9600 baud."})


if __name__ == '__main__':
    unittest.main()
