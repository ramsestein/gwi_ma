
import sys
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up two levels to reach root, then into results/
RESULTS_DIR = os.path.join(BASE_DIR, "..", "..", "results")

def generate_protocol(filename, json_content):
    try:
        if not os.path.exists(RESULTS_DIR):
            os.makedirs(RESULTS_DIR)
            
        if not filename.endswith('.json'):
            filename += '.json'
            
        filepath = os.path.join(RESULTS_DIR, filename)
        
        # Validate JSON
        try:
            data = json.loads(json_content)
        except json.JSONDecodeError:
            return "Error: Invalid JSON content provided."
            
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            
        return f"Success: Protocol definition saved to {filepath}"
    except Exception as e:
        return f"Error saving protocol: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.llm.protocol_generator <filename> <json_string>")
        sys.exit(1)
        
    filename = sys.argv[1]
    # Join all remaining args in case of spaces in JSON
    json_str = " ".join(sys.argv[2:])
    
    print(generate_protocol(filename, json_str))
