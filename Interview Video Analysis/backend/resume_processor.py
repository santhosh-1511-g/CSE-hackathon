import zipfile
import xml.etree.ElementTree as ET
import os
import re
import pdfplumber
import io

# --- Job Role Config (Ported from Resume Project) ---
REQUIRED_SKILLS = ['python', 'django', 'sql', 'data structures', 'problem solving']
BONUS_SKILLS = ['git', 'rest api', 'html', 'css', 'javascript', 'machine learning',
                'flask', 'postgresql', 'mysql', 'sqlite', 'docker', 'linux', 'java', 'c++']
ATS_KEYWORDS = ['software developer', 'python', 'django', 'sql', 'data structures',
                'problem solving', 'api', 'backend', 'database', 'object oriented',
                'oop', 'algorithms', 'git', 'agile', 'rest']

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
    
    # 2. Professional Wording (Active Verbs)
    pro_verbs = ['achieved', 'developed', 'managed', 'led', 'optimized', 'implemented', 'designed', 'coordinated', 'mentored']
    found_verbs = [v for v in pro_verbs if v in t_lower]
    score += min(len(found_verbs) * 2, 15)
    
    # 3. Clarity (Sentence Length Heuristic)
    lines = [l for l in text.split('\n') if len(l.strip()) > 10]
    if lines:
        avg_words = sum(len(l.split()) for l in lines) / len(lines)
        if avg_words < 18: score += 10 # Good conciseness
        elif avg_words > 30: score -= 10 # Possible run-on sentences
    
    # 4. Professional Tone (Capitalization/Structure)
    # Check if lines start with uppercase
    up_lines = [l for l in lines if l[0].isupper()]
    if len(up_lines) / len(lines) > 0.7: score += 5
    
    # 5. Grammar Red Flags (Simple Heuristic)
    if ' i ' in text: score -= 5 # Informal case misuse
    
    return max(0, min(100, score))

def extract_resume_metadata(file_stream) -> dict:
    """Advanced & Strict HR Resume Analyzer AI."""
    # Read file content
    try:
        file_bytes = file_stream.read()
    except AttributeError:
        file_bytes = file_stream

    text = extract_text_from_pdf(file_bytes)
    if not text.strip():
        text = extract_text_from_docx(file_bytes)
    
    if not text.strip():
        return {"error": "Could not extract text from file.", "name": "Unknown"}

    t_lower = _text_lower(text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    report_data = {}
    found_count = 0

    # 1. Skills (Direct Scan)
    skills_found = [s for s in CAT_KEYWORDS["Skills"] if s in t_lower]
    report_data["Skills"] = {"status": "FOUND" if skills_found else "NOT FOUND", "details": ", ".join(skills_found[:10]) if skills_found else "None"}
    if skills_found: found_count += 1

    # 2. Projects (Content Validation)
    projects_found = []
    for line in lines:
        if any(k in line.lower() for k in CAT_KEYWORDS["Projects"]) and len(line) > 12:
            projects_found.append(line)
    report_data["Projects"] = {"status": "FOUND" if projects_found else "NOT FOUND", "details": ", ".join([p[:45] for p in projects_found[:3]]) if projects_found else "None"}
    if projects_found: found_count += 1

    # 3. Workshops (Content Validation)
    workshops_found = [line for line in lines if any(k in line.lower() for k in CAT_KEYWORDS["Workshops/Trainings"]) and len(line) > 10]
    report_data["Workshops/Trainings"] = {"status": "FOUND" if workshops_found else "NOT FOUND", "details": ", ".join(workshops_found[:2]) if workshops_found else "None"}
    if workshops_found: found_count += 1

    # 4. Certifications (STRICT: Key + Valid Org)
    certs_found = []
    for line in lines:
        l_low = line.lower()
        has_key = any(k in l_low for k in CERT_KEYS)
        has_org = any(o in l_low for o in CERT_ORGS)
        if has_key and has_org:
            certs_found.append(line)
    report_data["Certifications"] = {"status": "FOUND" if certs_found else "NOT FOUND", "details": ", ".join(certs_found[:2]) if certs_found else "None"}
    if certs_found: found_count += 1

    # 5. Internships (STRICT: Key + Role/Duration)
    interns_found = []
    for line in lines:
        l_low = line.lower()
        if 'intern' in l_low:
            # Must also mention a generic role indicator OR a date pattern to be valid experience
            has_role = any(r in l_low for r in ROLE_INDICATORS)
            has_dur = bool(re.search(DURATION_PATTERN, l_low))
            if has_role or has_dur:
                interns_found.append(line)
    report_data["Internships"] = {"status": "FOUND" if interns_found else "NOT FOUND", "details": ", ".join(interns_found[:2]) if interns_found else "None"}
    if interns_found: found_count += 1

    # 6. Work Experience (STRICT: Not an address, must have role/position + duration)
    work_found = []
    for line in lines:
        l_low = line.lower()
        # Filter out common address noise
        if any(noise in l_low for noise in ['street', 'road', 'nagar', 'colony', 'apartment', 'house no']): 
            continue
            
        has_exp_key = any(k in l_low for k in ['experience', 'worked at', 'employment', 'developer at', 'engineer at'])
        has_role = any(r in l_low for r in ROLE_INDICATORS)
        has_dur = bool(re.search(DURATION_PATTERN, l_low))
        
        if (has_exp_key and (has_role or has_dur)) or (has_role and has_dur):
            work_found.append(line)
            
    report_data["Work Experience"] = {"status": "FOUND" if work_found else "NOT FOUND", "details": ", ".join(work_found[:2]) if work_found else "None"}
    if work_found: found_count += 1

    # Communication Skill Logic
    comm_percent = calculate_communication_score(text)
    
    # Format the strict report string
    formatted_report = (
        "Candidate Evaluation Report:\n\n"
        f"Skills: {report_data['Skills']['status']}\nDetails: {report_data['Skills']['details']}\n\n"
        f"Projects: {report_data['Projects']['status']}\nDetails: {report_data['Projects']['details']}\n\n"
        f"Workshops/Trainings: {report_data['Workshops/Trainings']['status']}\nDetails: {report_data['Workshops/Trainings']['details']}\n\n"
        f"Certifications: {report_data['Certifications']['status']}\nDetails: {report_data['Certifications']['details']}\n\n"
        f"Internships: {report_data['Internships']['status']}\nDetails: {report_data['Internships']['details']}\n\n"
        f"Work Experience: {report_data['Work Experience']['status']}\nDetails: {report_data['Work Experience']['details']}\n\n"
        f"Communication Skills: {comm_percent}%"
    )

    # Scoring
    completeness_score = round((found_count / 6) * 10, 1)

    return {
        "name": lines[0][:30] if lines else "Candidate",
        "resume_score": int(completeness_score * 10),
        "completeness_score": completeness_score,
        "communication_skills": comm_percent,
        "formatted_report": formatted_report,
        "evaluation_data": report_data,
        "top_5_technical_skills": skills_found[:5],
        "strengths": ["Clear communication profile" if comm_percent > 80 else "Strong technical alignment"],
        "weaknesses": ["Improve resume detail structure" if comm_percent < 60 else "N/A"],
        "recommendation": "Strong Hire" if (completeness_score >= 8 and comm_percent >= 75) else "Consider" if completeness_score >= 5 else "Reject"
    }
