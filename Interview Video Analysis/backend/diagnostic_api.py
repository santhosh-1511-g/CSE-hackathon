import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def check_api_keys():
    print("Checking /api/candidate/create response keys...")
    try:
        resp = requests.post(f"{BASE_URL}/api/candidate/create", json={"name": "Diagnostic Test"})
        if resp.status_code in (200, 201):
            data = resp.json()
            print(f"Full Response: {json.dumps(data, indent=2)}")
            if "candidate_id" in data:
                print("[+] SUCCESS: 'candidate_id' is present in the response.")
            else:
                print("[-] FAILURE: 'candidate_id' is MISSING. The server is likely running OLD code.")
        else:
            print(f"[-] ERROR: Status {resp.status_code}, Body: {resp.text}")
    except Exception as e:
        print(f"[-] EXCEPTION: {e}")

if __name__ == "__main__":
    check_api_keys()
