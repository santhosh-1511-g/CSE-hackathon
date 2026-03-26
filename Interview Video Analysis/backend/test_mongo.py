from pymongo import MongoClient
from bson import ObjectId

client = MongoClient('mongodb://localhost:27017/')
print("Available Databases:", client.list_database_names())

target_id_str = "69c4b86a411adaf26a3bd178"

for db_name in client.list_database_names():
    db = client[db_name]
    for col_name in db.list_collection_names():
        count = db[col_name].count_documents({})
        print(f" - {db_name}.{col_name}: {count} docs")
        try:
            # Check for specific ID
            doc = db[col_name].find_one({"_id": ObjectId(target_id_str)})
            if doc:
                print(f"   [FOUND] ObjectID {target_id_str} in {db_name}.{col_name}")
            
            # Also check if it's stored as a string ID
            doc_str = db[col_name].find_one({"_id": target_id_str})
            if doc_str:
                print(f"   [FOUND] StringID {target_id_str} in {db_name}.{col_name}")
        except Exception as e:
            print(f"   Error checking {db_name}.{col_name}: {e}")
