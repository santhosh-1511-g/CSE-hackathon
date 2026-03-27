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

# --- Main Processor Function ---

def extract_resume_metadata(file_stream) -> dict:
    """Consolidated Rule-Based Evaluator."""
    # Read file content
    try:
        file_bytes = file_stream.read()
        # In case the stream was already read elsewhere, we might need seek(0) in caller
    except AttributeError:
        file_bytes = file_stream

    # Detect extension-like behavior (heuristic)
    # Since we don't have filename here, we check file signature or try both
    text = extract_text_from_pdf(file_bytes)
    if not text.strip(): # Fallback to docx if PDF yields nothing
        text = extract_text_from_docx(file_bytes)
    
    if not text.strip():
        return {"error": "Could not extract text from file.", "name": "Unknown"}

    # Run Evaluator
    skills_score, matched_skills, bonus_skills = score_skills(text)
    exp_score, exp_details = score_experience(text)
    proj_score, proj_details = score_projects(text)
    edu_score, edu_detail = score_education(text)
    ats_score, ats_matched = score_ats(text)

    # Calculate Total
    total = round(skills_score + exp_score + proj_score + edu_score + ats_score, 1)
    
    # Recommendation Logic
    recommendation = "Reject"
    if total >= 35: recommendation = "Strong Hire"
    elif total >= 25: recommendation = "Consider"

    # Formatting Strengths/Weaknesses
    strengths = []
    weaknesses = []
    if 'python' in matched_skills: strengths.append("Proficient in Python core")
    else: weaknesses.append("Missing core Python requirement")
    if len(matched_skills) >= 3: strengths.append(f"Strong skill alignment ({len(matched_skills)} key skills)")
    if exp_score >= 5: strengths.append("Verified professional internship/work exp")
    if proj_score < 4: weaknesses.append("Project methodology lacks measurable data")

    return {
        "name": text.split('\n')[0][:30] or "Candidate",
        "top_5_technical_skills": matched_skills[:5],
        "years_of_experience": 2 if exp_score > 5 else 1,
        "last_job_title": "Software Developer" if exp_score > 5 else "Fresher",
        "resume_score": int((total / 50) * 100), # Normalized to 100
        "detailed_scores": {
            "skills": skills_score,
            "experience": exp_score,
            "projects": proj_score,
            "education": edu_score,
            "ats": ats_score
        },
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendation": recommendation,
        "raw_text_preview": text[:200]
    }
