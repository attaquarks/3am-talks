import httpx
import sys

def test_ollama_connection():
    url = "http://127.0.0.1:11434/api/tags"
    print(f"Testing connection to {url}...")
    try:
        response = httpx.get(url, timeout=5.0)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("SUCCESS: Connected to Ollama!")
            return True
        else:
            print("FAILURE: Connected but got unexpected status.")
            return False
            
    except Exception as e:
        print(f"FAILURE: Could not connect. Error: {e}")
        return False

if __name__ == "__main__":
    success = test_ollama_connection()
    sys.exit(0 if success else 1)
