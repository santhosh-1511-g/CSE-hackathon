import requests
import os

BASE_URL = "http://127.0.0.1:5000"
resume_path = "e:/CSE-hackathon/Interview Video Analysis/test_resume.pdf"
video_path = "e:/CSE-hackathon/Interview Video Analysis/backend/uploads/test.mp4"

def test_ingestion():
    try:
        # Step 1: Create Candidate
        print(f"Step 1: Creating candidate...")
        resp = requests.post(f"{BASE_URL}/api/candidate/create", json={"name": "Test Candidate E2E"})
        if resp.status_code != 201:
            print(f"Error creating candidate: {resp.text}")
            return
        candidate_data = resp.json()
        candidate_id = candidate_data["candidate_id"]
        print(f"Candidate Created: {candidate_id}")

        # Step 2: Upload Resume
        print(f"Step 2: Uploading resume...")
        with open(resume_path, "rb") as f:
            resp = requests.post(f"{BASE_URL}/api/resume/upload", 
                               data={"candidate_id": candidate_id}, 
                               files={"file": f})
        if resp.status_code != 200:
            print(f"Error uploading resume: {resp.text}")
            return
        print(f"Resume Uploaded: {resp.json().get('status')}")

        # Step 3: Trigger Analysis
        print(f"Step 3: Triggering video analysis...")
        with open(video_path, "rb") as f:
            resp = requests.post(f"{BASE_URL}/analyze", 
                               data={"candidate_id": candidate_id, "candidate_name": "Test Candidate E2E"}, 
                               files={"video": f})
        if resp.status_code != 200:
            print(f"Error in analysis: {resp.text}")
            return
        print(f"Analysis Complete: {resp.json().get('status')}")
        print(f"Final Analysis Keys: {resp.json().get('analysis', {}).keys()}")

    except Exception as e:
        print(f"Script Error: {e}")

if __name__ == "__main__":
    test_ingestion()
