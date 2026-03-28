import requests
import json

try:
    r = requests.get("http://localhost:5000/results")
    if r.status_code == 200:
        data = r.json()
        results = data.get("results", [])
        print(f"Total candidates: {len(results)}")
        for c in results:
            print(f"ID: {c.get('_id')}")
            print(f"Name: {c.get('candidate_name')}")
            print(f"Role: {c.get('selected_role')}")
            res = c.get('resume_profile', {})
            print(f"Resume Status: {res.get('status', 'MISSING')}")
            print(f"Scores: Tech={res.get('technical_score')}, Overall={res.get('overall_fit_score')}")
            print("-" * 20)
    else:
        print(f"API Error: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
