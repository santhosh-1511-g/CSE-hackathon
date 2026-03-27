import pdfplumber
# import google.generativeai as genai  # Moved inside to save memory

import os
import re
import pdfplumber
import io

def construct_gemini_client():
    # Attempt to load from env, user will need to supply it
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

def _text_lower(text):
    return text.lower()

# --- Scoring Logic (Ported from Resume Project) ---

def score_skills(text):
    t = _text_lower(text)
    matched = [s for s in REQUIRED_SKILLS if s in t]
    bonus = [s for s in BONUS_SKILLS if s in t]
    base = (len(matched) / len(REQUIRED_SKILLS)) * 8 if REQUIRED_SKILLS else 0
    extra = min(len(bonus) * 0.4, 2.0)
    score = round(min(base + extra, 10), 1)
    return score, matched, bonus

def score_experience(text):
    t = _text_lower(text)
    score = 0
    details = []
    internship_kw = ['internship', 'intern ', 'worked at', 'employed', 'junior developer',
                     'software engineer', 'developer at', 'experience at']
    has_job = any(k in t for k in internship_kw)
    if has_job:
        score += 5
        details.append("Work/Internship experience found")
    year_match = re.findall(r'(\d+)\s*\+?\s*year', t)
    if year_match:
        yrs = max(int(y) for y in year_match)
        score += min(yrs * 1.5, 4)
        details.append(f"~{yrs} year(s) of experience mentioned")
    if not has_job and 'project' in t:
        score = max(score, 1)
        details.append("Project-based exposure")
    return round(min(score, 10), 1), details

def score_projects(text):
    t = _text_lower(text)
    score = 0
    details = []
    project_count = len(re.findall(r'project[s]?[\s\:\-]', t))
    if project_count == 0: project_count = t.count('\n') // 20
    score += min(project_count * 2, 5)
    numbers = re.findall(r'\d+\s*(%|users|requests|accuracy|ms|records|problems)', t)
    if numbers:
        score += min(len(numbers) * 0.5, 3)
        details.append(f"Measurable outcomes: {len(numbers)} items")
    tech_kw = ['django', 'flask', 'react', 'nodejs', 'mongodb', 'mysql', 'postgresql', 'docker', 'aws']
    found = [k for k in tech_kw if k in t]
    score += min(len(found) * 0.5, 2)
    return round(min(score, 10), 1), details

def score_education(text):
    t = _text_lower(text)
    score = 5
    detail = "Graduate"
    if any(k in t for k in ['b.tech', 'btech', 'b.e', 'bachelor']):
        score, detail = 6, "Bachelor's degree"
    if any(k in t for k in ['m.tech', 'mtech', 'm.e', 'master', 'mca']):
        score, detail = 8, "Postgraduate degree"
    cgpa_match = re.findall(r'cgpa[\s\:\-]*([\d\.]+)', t)
    if cgpa_match:
        cgpa = float(cgpa_match[0])
        score = min(score + (2 if cgpa >= 8.5 else 1 if cgpa >= 7.5 else 0), 10)
        detail += f" (CGPA: {cgpa})"
    return round(min(score, 10), 1), detail

def score_ats(text):
    t = _text_lower(text)
    matched = [k for k in ATS_KEYWORDS if k in t]
    score = (len(matched) / len(ATS_KEYWORDS)) * 10 if ATS_KEYWORDS else 0
    return round(min(score, 10), 1), matched

# --- Support for DOCX (Ported from Resume Project) ---

def extract_text_from_docx(file_bytes):
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    lines = []
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            with z.open('word/document.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
        for para in root.iter(ns + 'p'):
            texts = [node.text for node in para.iter(ns + 't') if node.text]
            line = ''.join(texts).strip()
            if line: lines.append(line)
        return '\n'.join(lines)
    except Exception as e:
        print(f"DOCX Extraction Error: {e}")
        return ""

def extract_text_from_pdf(file_bytes):
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
        return text
    except Exception as e:
        print(f"PDF Extraction Error: {e}")
        return ""

# --- Strict Validation Logic ---
CAT_KEYWORDS = {
    "Skills": ['python', 'java', 'c++', 'javascript', 'html', 'css', 'sql', 'react', 'django', 'flask', 'nodejs', 'mongodb', 'docker', 'aws', 'git', 'linux', 'machine learning'],
    "Projects": ['project', 'app', 'system', 'platform', 'website', 'tool', 'bot', 'chatbot', 'github.com'],
    "Workshops/Trainings": ['workshop', 'training', 'seminar', 'bootcamp', 'webinar', 'certification course'],
    "Certifications": ['certification', 'certified', 'license', 'nptel', 'coursera', 'udemy', 'hackerrank', 'microsoft certified', 'aws certified'],
    "Internships": ['internship', 'intern', 'trainee', 'summer intern'],
    "Work Experience": ['job', 'experience', 'worked at', 'employment', 'senior', 'junior', 'developer at', 'engineer at']
}

CERT_ORGS = ['nptel', 'coursera', 'udemy', 'hackerrank', 'microsoft', 'google', 'aws', 'cisco', 'oracle', 'linkedin', 'edx', 'simplilearn']
CERT_KEYS = ['certified', 'certificate', 'course', 'completed', 'issued by', 'license', 'certification']
ROLE_INDICATORS = ['developer', 'engineer', 'intern', 'analyst', 'manager', 'lead', 'trainee', 'architect', 'specialist', 'associate', 'consultant']
DURATION_PATTERN = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|20\d{2}|present|months|years)'

def calculate_communication_score(text):
    """Heuristic logic for Communication Skill Evaluation (0-100%)."""
    score = 65  # Base (Good starting point)
    t_lower = text.lower()
    
    # 1. Structure (Bullet points/formatting)
    bullets = len(re.findall(r'^[•\-\*]\s+', text, re.MULTILINE))
    if bullets > 4: score += 10
    
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
    try:
        import google.generativeai as genai
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction
        )
        
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        
        data = json.loads(response.text)
        return data
    except Exception as e:
        print(f"[!] Resume Processing Failed: {e}")
        return {
            "name": "Unknown",
            "top_5_technical_skills": [],
            "years_of_experience": 0,
            "last_job_title": "Unknown",
            "resume_score": 0,
            "error": str(e)
        }
