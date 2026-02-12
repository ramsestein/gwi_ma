import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os
import subprocess

# Ensure src is in path
sys.path.append(os.getcwd())
try:
    from src.deepseek_handler import DeepSeekHandler
except ImportError:
    pass

class TestDeepSeekAgent(unittest.TestCase):
    
    def setUp(self):
        # Setup a dummy environment for testing
        self.handler = DeepSeekHandler()
        # Inject a dummy key if not present, to pass initialization checks
        if not self.handler.api_key:
            self.handler.api_key = "dummy_key_for_testing"

    def test_prompt_consistency(self):
        """Verify the System Prompt contains critical instructions."""
        with patch('requests.post') as mock_post:
            # Mock a valid response
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": json.dumps({"reasoning": "test", "is_finished": True})
                    }
                }]
            }
            mock_post.return_value = mock_response
            
            # Call the method
            context = {"test": "data"}
            self.handler.ask_deepseek(context)
            
            # Inspect what was sent
            args, kwargs = mock_post.call_args
            payload = kwargs['json']
            messages = payload['messages']
            
            system_msg = next(m for m in messages if m['role'] == 'system')
            system_content = system_msg['content']
            
            # Assertions on Prompt Content (Updated for case sensitivity)
            self.assertIn("Expert Protocol Reverse Engineering Agent", system_content)
            self.assertIn("AVAILABLE TOOLS", system_content)
            self.assertIn("baud_detector", system_content)
            self.assertIn("framing_scanner", system_content)
            self.assertIn("You must respond with a JSON object:", system_content)
            
            print("\n[Test] Prompt Consistency Verified.")

    def test_tool_execution(self):
        """Verify that the agent can execute tools via subprocess."""
        with patch('subprocess.check_output') as mock_exec:
            mock_exec.return_value = b"Detected Baud: 9600"
            
            output = self.handler.run_tool("baud_detector", "COM3")
            
            # Verify command construction
            mock_exec.assert_called_with("python -m src.baud_detector COM3", shell=True, stderr=subprocess.STDOUT)
            self.assertIn("Detected Baud: 9600", output)
            print("\n[Test] Tool Execution Verified.")

    def test_api_connection_structure(self):
        """Verify the API Request structure (URL, Headers, Model)."""
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "{}" 
                    }
                }]
            }
            mock_post.return_value = mock_response
            
            self.handler.ask_deepseek({})
            
            args, kwargs = mock_post.call_args
            url = args[0]
            headers = kwargs['headers']
            payload = kwargs['json']
            
            self.assertEqual(url, "https://api.deepseek.com/chat/completions")
            self.assertEqual(headers['Authorization'], f"Bearer {self.handler.api_key}")
            self.assertEqual(payload['model'], "deepseek-chat")
            self.assertEqual(payload['response_format']['type'], "json_object")
            
            print("\n[Test] API Request Structure Verified.")

    def test_agent_logic_parsing(self):
        """Verify the Agent correctly parses the JSON response."""
        
        # Simulate a response where Agent decides to run baud_detector
        agent_response = {
            "reasoning": "We need to find the speed first.",
            "next_tool": "baud_detector",
            "arguments": "COM3",
            "is_finished": False
        }
        
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": json.dumps(agent_response)
                    }
                }]
            }
            mock_post.return_value = mock_response
            
            context = {}
            plan = self.handler.ask_deepseek(context)
            
            self.assertEqual(plan['next_tool'], "baud_detector")
            self.assertEqual(plan['arguments'], "COM3")
            self.assertFalse(plan['is_finished'])
            
            print("\n[Test] Agent Logic Parsing Verified.")

if __name__ == '__main__':
    unittest.main()
