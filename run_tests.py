"""
Simple test runner for the 3AM Talks system.
Run this script to execute all comprehensive tests.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file first
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "tests"))

if __name__ == "__main__":
    # Check for required environment variables (after loading .env)
    required_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these in your .env file or environment.")
        print("See .env.example for reference.")
        sys.exit(1)
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("WARNING: .env file not found.")
        print("Please create a .env file with your credentials.")
        print("You can copy .env.example as a template.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Import and run tests
    try:
        from tests.test_full_system import run_all_tests
        run_all_tests()
    except ImportError as e:
        print(f"ERROR: Failed to import test module: {e}")
        print("Make sure you're in the project root directory.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
