
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_FILE = os.path.join(BASE_DIR, "acquired_knowledge.md")

def update_knowledge(text):
    try:
        with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n\n- {text}")
        return f"Success: Added to knowledge base ({len(text)} chars)."
    except Exception as e:
        return f"Error updating knowledge: {e}"

def read_knowledge():
    try:
        if os.path.exists(KNOWLEDGE_FILE):
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                return f.read()
        return "No knowledge base found."
    except Exception as e:
        return f"Error reading knowledge: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.llm.knowledge_manager <read|update> [text]")
        sys.exit(1)
        
    cmd = sys.argv[1]
    
    if cmd == 'read':
        print(read_knowledge())
    elif cmd == 'update':
        if len(sys.argv) < 3:
            print("Error: update requires text")
        else:
            text = " ".join(sys.argv[2:])
            print(update_knowledge(text))
    else:
        print("Unknown command")
