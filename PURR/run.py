import sys
import os

# Add src to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.main import main
except ImportError:
    # If using as package directly or some path issue
    from main import main

if __name__ == "__main__":
    main()
