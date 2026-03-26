import pdfplumber
import google.generativeai as genai
import os
import json

def construct_gemini_client():
    # Attempt to load from env, user will need to supply it
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        genai.configure(api_key=api_key)

def extract_resume_metadata(file_stream) -> dict:
    construct_gemini_client()
    
    # Extract text from PDF
    text = ""
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    
    # Prompt and instruction
    system_instruction = (
        "You are a professional HR data extractor. Extract metadata from resume text into a strict JSON format. "
        "Normalize all technology names to lowercase (e.g., 'ReactJS' becomes 'react')."
    )
    
    prompt = f"""
Extract these fields from the resume text into a strict JSON:
- name (string)
- top_5_technical_skills (list of strings, normalized lowercase)
- years_of_experience (integer)
- last_job_title (string)
- resume_score (integer, 1-100)

RETURN ONLY THE JSON.

Resume Text:
{text}
"""
    # Note: Using gemini-3-flash as requested by user
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system_instruction
    )
    
    response = model.generate_content(
        prompt, 
        generation_config={"response_mime_type": "application/json"}
    )
    
    try:
        data = json.loads(response.text)
        return data
    except Exception as e:
        print(f"Error parsing LLM response: {e}")
        return {
            "name": "Unknown",
            "top_5_technical_skills": [],
            "years_of_experience": 0,
            "last_job_title": "Unknown",
            "skill_confidence_score": 0,
            "error": "Failed to parse JSON"
        }
