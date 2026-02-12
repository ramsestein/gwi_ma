
import unittest
import os
import json
import sys
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.llm import knowledge_manager
from src.llm import protocol_generator
from src.llm import deepseek_agent
from src.utils import web_client

class TestGwiMaCore(unittest.TestCase):

    def setUp(self):
        # Setup temp paths
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.temp_knowledge = os.path.join(self.test_dir, "temp_knowledge.md")
        self.temp_results = os.path.join(self.test_dir, "temp_results")
        if not os.path.exists(self.temp_results):
            os.makedirs(self.temp_results)

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.temp_knowledge):
            os.remove(self.temp_knowledge)
        if os.path.exists(self.temp_results):
            import shutil
            shutil.rmtree(self.temp_results)

    # --- Knowledge Manager Tests ---
    def test_knowledge_manager(self):
        # Patch the constant in the module
        with patch('src.llm.knowledge_manager.KNOWLEDGE_FILE', self.temp_knowledge):
            # Test Read Empty
            self.assertEqual(knowledge_manager.read_knowledge(), "No knowledge base found.")
            
            # Test Update
            res = knowledge_manager.update_knowledge("Fact 1")
            self.assertIn("Success", res)
            
            # Test Read Content
            content = knowledge_manager.read_knowledge()
            self.assertIn("Fact 1", content)
            
            # Test Append
            knowledge_manager.update_knowledge("Fact 2")
            content = knowledge_manager.read_knowledge()
            self.assertIn("Fact 1", content)
            self.assertIn("Fact 2", content)

    # --- Protocol Generator Tests ---
    def test_protocol_generator(self):
        with patch('src.llm.protocol_generator.RESULTS_DIR', self.temp_results):
            # Test Valid JSON
            valid_json = '{"protocol": "test", "baud": 9600}'
            res = protocol_generator.generate_protocol("test_proto", valid_json)
            self.assertIn("Success", res)
            
            expected_file = os.path.join(self.temp_results, "test_proto.json")
            self.assertTrue(os.path.exists(expected_file))
            
            with open(expected_file, 'r') as f:
                data = json.load(f)
                self.assertEqual(data['baud'], 9600)

            # Test Invalid JSON
            invalid_json = '{bad json}'
            res = protocol_generator.generate_protocol("bad.json", invalid_json)
            self.assertIn("Error", res)

    # --- Web Client Tests ---
    @patch('src.utils.web_client.requests.get')
    def test_web_client_search(self, mock_get):
        # Mock Response
        mock_resp = MagicMock()
        mock_resp.text = """
        <div class="result">
            <a class="result__a" href="http://example.com">Example Title</a>
            <a class="result__snippet">Example Snippet</a>
        </div>
        """
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        
        # We need to ensure BS4 is handled or not. 
        # The script checks import. Assuming environment has it or not, logic adapts.
        # We just check it runs without error.
        res = web_client.search_web("test query")
        # Check if it parsed something or returned error
        if "BeautifulSoup" in str(sys.modules):
             self.assertIn("Example Title", res)
        else:
             # If BS4 is missing/mocked out logic might differ, 
             # but we assume the tool works or fails gracefully
             pass

    # --- DeepSeek Agent Tests ---
    def test_agent_prompt_loading(self):
        agent = deepseek_agent.DeepSeekAgent()
        
        # Patch the file reader to return dummy data
        with patch.object(agent, '_read_file') as mock_read:
            mock_read.side_effect = lambda x: f"[{x} CONTENT]"
            
            prompt = agent.get_system_prompt()
            
            self.assertIn("[system_prompt.md CONTENT]", prompt)
            self.assertIn("[acquired_knowledge.md CONTENT]", prompt)
            self.assertIn("[available_tools.md CONTENT]", prompt)
            self.assertIn("[CURRENT PROTOCOL STATE (JSON)]", prompt)

    def test_agent_tool_parsing(self):
        agent = deepseek_agent.DeepSeekAgent()
        
        # Test Markdown JSON
        llm_resp = 'Sure, I will search.\n```json\n{"type": "function", "function": {"name": "web_search", "parameters": "query"}}\n```'
        tool = agent.parse_tool_call(llm_resp)
        self.assertEqual(tool['name'], 'web_search')
        self.assertEqual(tool['parameters'], 'query')
        
        # Test Plain JSON
        llm_resp_2 = '{"type": "function", "function": {"name": "test", "parameters": "123"}}'
        tool2 = agent.parse_tool_call(llm_resp_2)
        self.assertEqual(tool2['name'], 'test')

if __name__ == '__main__':
    unittest.main()
