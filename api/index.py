import sys
import os

# Add the backend directory to the sys path so it can find main.py and quantize logic
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from main import app
