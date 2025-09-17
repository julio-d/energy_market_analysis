"""
Simple runner script for the Energy Market Analysis Dashboard
"""

import subprocess
import sys
import os

def main():
    """Run the Streamlit application"""
    try:
        # Run streamlit with the main.py file
        subprocess.run([sys.executable, "-m", "streamlit", "run", "main.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running the application: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    main()
