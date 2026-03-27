import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId

class MockCollection:
    def __init__(self, name):
        self.name = name
        self.data = {}

    def insert_one(self, doc):
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        _id = doc["_id"]
        self.data[str(_id)] = doc
        class Result: 
            def __init__(self, i): self.inserted_id = i
        return Result(_id)

    def find_one(self, filter):
        _id = str(filter.get("_id", ""))
        return self.data.get(_id)

    def find(self, filter=None):
        return list(self.data.values())

    def update_one(self, filter, update):
        _id = str(filter.get("_id", ""))
        if _id in self.data:
            if "$set" in update:
                self.data[_id].update(update["$set"])
            else:
                self.data[_id].update(update)
            class Result: 
                def __init__(self, c): self.matched_count = c
            return Result(1)
        class Result: 
            def __init__(self, c): self.matched_count = c
        return Result(0)

    def delete_one(self, filter):
        _id = str(filter.get("_id", ""))
        if _id in self.data:
            del self.data[_id]
            class Result: 
                def __init__(self, c): self.deleted_count = c
            return Result(1)
        class Result: 
            def __init__(self, c): self.deleted_count = c
        return Result(0)

class MockDatabase:
    def __init__(self):
        self.results = MockCollection("results")
        self.client = self # Fake client for ping
        class Admin:
            def command(self, cmd): pass
        self.admin = Admin()

_mock_db = MockDatabase()

def get_db():
    """Returns a connected MongoDB database instance or Mock database as fallback."""
    print("[*] Attempting to connect to MongoDB...")
    for i in range(2): # Reduce retries for speed
        try:
            host = "localhost" if i % 2 == 0 else "127.0.0.1"
            print(f"[>] Attempt {i+1}: Connecting to {host}:27017")
            client = MongoClient(f"mongodb://{host}:27017/", serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
            db = client["interview_analysis"]
            print("[+] MongoDB connected successfully!")
            return db
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"[!] Attempt {i+1} failed: Service not found.")
            if i < 1:
                time.sleep(1)
    
    print("[WARNING] Could not connect to MongoDB. Using IN-MEMORY MOCK DATABASE fallback.")
    return _mock_db
