#!/usr/bin/env python
"""Run the Flask server from the backend directory."""
import os
import sys

# Force UTF-8 encoding on Windows
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(script_dir, 'backend')

# Verify backend directory exists
if not os.path.exists(backend_dir):
    print(f"[ERROR] Backend directory not found at {backend_dir}")
    sys.exit(1)

# Verify server.py exists
server_path = os.path.join(backend_dir, 'server.py')
if not os.path.exists(server_path):
    print(f"[ERROR] server.py not found at {server_path}")
    sys.exit(1)

# Change to backend directory
# os.chdir(backend_dir)  # Removed to fix Flask reloader path issue

# Add backend directory to Python path
sys.path.insert(0, backend_dir)

# Import and run the server
if __name__ == "__main__":
    print("[*] Starting Flask server...")
    print(f"[>] Working directory: {os.getcwd()}")
    print(f"[>] Server file: {server_path}")
    
    try:
        from server import app
        app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=True)
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        print(f"Python path: {sys.path}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

