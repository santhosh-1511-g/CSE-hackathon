import requests
import json
import io

BASE_URL = "http://127.0.0.1:5000"

def test_resume_upload():
    print("Fetching an existing candidate ID...")
    try:
        resp = requests.get(f"{BASE_URL}/results")
        results = resp.json().get("results", [])
        if not results:
            print("No candidates found. Creating a test candidate...")
            resp = requests.post(f"{BASE_URL}/api/candidate/create", json={"name": "Resume Test User"})
            cid = resp.json().get("candidate_id")
        else:
            cid = results[0]["_id"]
        
        print(f"Testing resume upload for candidate {cid}...")
        # Create a dummy PDF in memory
        dummy_pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Title (Test) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF")
        
        files = {"file": ("test_resume.pdf", dummy_pdf, "application/pdf")}
        data = {"candidate_id": cid}
        
        resp = requests.post(f"{BASE_URL}/api/resume/upload", files=files, data=data)
        
        print(f"Response Status: {resp.status_code}")
        print(f"Response Body: {json.dumps(resp.json(), indent=2)}")
        
        if resp.status_code == 200:
            print("[+] SUCCESS: Resume upload returned 200 (graceful fallback worked).")
        else:
            print(f"[-] FAILURE: Unexpected status code {resp.status_code}")
            
    except Exception as e:
        print(f"[-] EXCEPTION: {e}")

if __name__ == "__main__":
    test_resume_upload()
