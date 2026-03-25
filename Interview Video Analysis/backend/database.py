from pymongo import MongoClient

def get_db():
    client = MongoClient("mongodb://127.0.0.1:27017/")
    db = client["interview_analysis"]
    return db
