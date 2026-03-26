import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

def get_db():
    """Returns a connected MongoDB database instance or None if connection fails."""
    # Retry for up to 10 seconds (5 attempts * 2s)
    print("[*] Attempting to connect to MongoDB...")
    for i in range(5):
        try:
            # Try both localhost and 127.0.0.1
            host = "localhost" if i % 2 == 0 else "127.0.0.1"
            print(f"[>] Attempt {i+1}: Connecting to {host}:27017")
            client = MongoClient(f"mongodb://{host}:27017/", serverSelectionTimeoutMS=3000)
            client.admin.command('ping')
            print(f"[DEBUG] Connected nodes: {client.nodes}")
            db = client["interview_analysis"]
            print("[+] MongoDB connected successfully!")
            return db
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"[!] Attempt {i+1} failed: {e}")
            if i < 4:
                time.sleep(2)
            else:
                print(f"[ERROR] Could not connect to MongoDB after 5 attempts.")
    return None
