import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_ingestion_flow():
    # 1. Create Candidate
    print("Testing /api/candidate/create...")
    payload = {"name": "Test Candidate " + str(int(time.time()))}
    resp = requests.post(f"{BASE_URL}/api/candidate/create", json=payload)
    if resp.status_code not in (200, 201):
        print(f"FAILED: {resp.status_code} {resp.text}")
        return
    
    cid = resp.json().get("id") or resp.json().get("candidate_id")
    print(f"SUCCESS: Created candidate {cid}")

    # 2. Results check (should be Initialized)
    print("Checking /results...")
    resp = requests.get(f"{BASE_URL}/results")
    results = resp.json().get("results", [])
    candidate = next((r for r in results if r["_id"] == cid), None)
    if not candidate:
        print("FAILED: Candidate not found in results")
        return
    print(f"Candidate status: {candidate.get('status')}")

    # 3. Analyze (Mocking video upload if possible, but let's just check if the endpoint exists and handles missing file)
    print("Testing /analyze (missing file)...")
    resp = requests.post(f"{BASE_URL}/analyze", data={"candidate_id": cid})
    print(f"Response: {resp.status_code}") # Should be 400 or 500 depending on implementation

if __name__ == "__main__":
    import time
    try:
        test_ingestion_flow()
    except Exception as e:
        print(f"Error during test: {e}")
