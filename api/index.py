import sys
import os

# Ensure the project root is in the Python path
# so that 'from app.models import ...' resolves correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.app import app  # noqa: E402
