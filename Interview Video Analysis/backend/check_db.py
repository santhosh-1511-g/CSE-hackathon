from database import get_db
from bson import ObjectId
import json

db = get_db()
if db:
    print("Checking last 5 results...")
    results = list(db.results.find().sort("_id", -1).limit(5))
    for r in results:
        print(f"ID: {r['_id']}")
        print(f"Name: {r.get('candidate_name')}")
        print(f"Role: {r.get('selected_role')}")
        print(f"Has resume_profile: {'resume_profile' in r}")
        if 'resume_profile' in r:
            # Print keys in resume_profile
            print(f"Resume Profile Keys: {list(r['resume_profile'].keys())}")
            # Print scores
            rp = r['resume_profile']
            print(f"Scores: Match={rp.get('role_match_score')}, Tech={rp.get('technical_score')}, Comm={rp.get('communication_score')}")
        print("-" * 20)
else:
    print("Could not connect to DB")
