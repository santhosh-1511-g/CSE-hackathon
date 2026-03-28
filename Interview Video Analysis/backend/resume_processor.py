import zipfile
import xml.etree.ElementTree as ET
import os
import re
import base64
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

# --- Support for Profile Pic Extraction ---

def extract_profile_pic_from_pdf(file_bytes):
    """Try to extract the largest image from the first page of a PDF (likely a profile photo)."""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                return None
            page = pdf.pages[0]
            images = page.images
            if not images:
                return None
            best = max(images, key=lambda img: (img.get('width', 0) or 0) * (img.get('height', 0) or 0))
            w = best.get('width', 0) or 0
            h = best.get('height', 0) or 0
            if w < 30 or h < 30:
                return None
            x0 = best.get('x0', 0)
            top = best.get('top', 0)
            x1 = best.get('x1', x0 + w)
            bottom = best.get('bottom', top + h)
            cropped = page.crop((x0, top, x1, bottom))
            img_obj = cropped.to_image(resolution=150)
            buf = io.BytesIO()
            img_obj.save(buf, format='PNG')
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode('utf-8')
            return f"data:image/png;base64,{b64}"
    except Exception as e:
        print(f"Profile Pic Extraction Error: {e}")
        return None

# --- Strict Validation Logic Constants ---
CERT_ORGS = ['nptel', 'coursera', 'udemy', 'hackerrank', 'microsoft', 'google', 'aws', 'cisco', 'oracle', 'linkedin', 'edx', 'simplilearn']
CERT_KEYS = ['certified', 'certificate', 'course', 'completed', 'issued by', 'license', 'certification']
ROLE_INDICATORS = ['developer', 'engineer', 'intern', 'analyst', 'manager', 'lead', 'trainee', 'architect', 'specialist', 'associate', 'consultant']
DURATION_PATTERN = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|20\d{2}|present|months|years)'

# --- Role-Based Benchmarks (STRICT HR REQUIREMENTS) ---
ROLE_BENCHMARKS = {
    "Corporate / Management Roles": {
        "Skills": ['leadership', 'team management', 'decision making', 'strategic thinking', 'problem-solving', 'time management', 'communication', 'excel', 'powerpoint', 'jira', 'trello'],
        "Traits": ['goal-oriented', 'people-focused']
    },
    "Sales & Marketing Jobs": {
        "Skills": ['persuasion', 'negotiation', 'customer handling', 'crm', 'seo', 'social media', 'ads', 'communication', 'storytelling'],
        "Traits": ['energetic', 'confident', 'creative']
    },
    "Core / Technical Jobs (Non-IT)": {
        "Skills": ['mechanical', 'civil', 'electrical', 'autocad', 'solidworks', 'matlab', 'site work', 'machine handling'],
        "Traits": ['problem solving', 'analytical thinking']
    },
    "Finance & Accounting Jobs": {
        "Skills": ['tally', 'gst', 'taxation', 'excel', 'financial analysis', 'p&l', 'balance sheet'],
        "Traits": ['accuracy', 'integrity', 'patience']
    },
    "IT / Software Jobs": { # Keeping as legacy fallback
        "Skills": ['python', 'java', 'c++', 'javascript', 'react', 'django', 'flask', 'nodejs', 'mongodb', 'docker', 'aws', 'git', 'sql', 'machine learning'],
        "Traits": []
    }
}

COMPANY_INDICATORS = [
    'pvt ltd', 'ltd', 'corp', 'inc', 'solutions', 'services', 'technologies', 'software',
    'bank', 'college', 'university', 'institute', 'limited', 'industries', 'group', 'pvt.', 'systems'
]

def find_company_names(text_lines):
    """Identify lines that likely contain a company name based on suffixes."""
    companies = []
    for line in text_lines:
        l_low = line.lower()
        if any(ind in l_low for ind in COMPANY_INDICATORS):
            # Strict: Not a home address (Nagar, Road, Street)
            if not any(noise in l_low for noise in ['nagar', 'road', 'street', 'colony', 'apartment', 'house no']):
                companies.append(line.strip())
    return companies

def calculate_communication_score(text):
    """Heuristic logic for Communication Skill Evaluation (0-100%)."""
    score = 65  
    t_lower = text.lower()
    bullets = len(re.findall(r'^[•\-\*]\s+', text, re.MULTILINE))
    if bullets > 4: score += 10
    pro_verbs = ['achieved', 'developed', 'managed', 'led', 'optimized', 'implemented', 'designed', 'coordinated', 'mentored']
    found_verbs = [v for v in pro_verbs if v in t_lower]
    score += min(len(found_verbs) * 2, 15)
    lines = [l for l in text.split('\n') if len(l.strip()) > 10]
    if lines:
        avg_words = sum(len(l.split()) for l in lines) / len(lines)
        if avg_words < 18: score += 10
        elif avg_words > 30: score -= 10
    return max(0, min(100, score))

def extract_resume_metadata(file_stream, selected_role="Corporate / Management Roles") -> dict:
    """Advanced & Strict Role-Based HR Resume Analyzer AI."""
    try:
        file_bytes = file_stream.read()
    except AttributeError:
        file_bytes = file_stream

    profile_pic = extract_profile_pic_from_pdf(file_bytes)
    text = extract_text_from_pdf(file_bytes)
    if not text.strip():
        text = extract_text_from_docx(file_bytes)
    if not text.strip():
        return {"error": "Could not extract text from file.", "name": "Unknown"}

    t_lower = _text_lower(text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # 1. Role Match Logic
    benchmarks = ROLE_BENCHMARKS.get(selected_role, ROLE_BENCHMARKS["IT / Software Jobs"])
    req_skills = benchmarks.get("Skills", [])
    found_required = [s for s in req_skills if s.lower() in t_lower]
    missing_required = [s for s in req_skills if s.lower() not in t_lower]
    
    # Validation Rules (STRICT)
    # Work Experience = FOUND only if: company name + role OR duration
    companies = find_company_names(lines)
    work_exp_found = False
    valid_exp_lines = []
    
    for line in lines:
        l_low = line.lower()
        # Check if line contains a company we identified
        is_company_line = any(comp.lower() in l_low for comp in companies)
        has_role = any(r in l_low for r in ROLE_INDICATORS)
        has_dur = bool(re.search(DURATION_PATTERN, l_low))
        
        if is_company_line and (has_role or has_dur):
            work_exp_found = True
            valid_exp_lines.append(line)
    
    # Certifications = FOUND only if: certification keyword + valid organization
    certs_found = []
    for line in lines:
        l_low = line.lower()
        if any(k in l_low for k in CERT_KEYS) and any(o in l_low for o in CERT_ORGS):
            certs_found.append(line)

    # 2. Scoring System
    # Role Match Score (0-100%): Skills + Traits keywords
    match_total = len(req_skills)
    match_score = (len(found_required) / match_total * 100) if match_total > 0 else 0
    
    # Technical/Domain Score (0-100%): Presence of specific technical keywords
    tech_score = 40 if work_exp_found else 10
    tech_score += min(len(found_required) * 10, 60) # Max 60 from skills
    
    # Communication Score (0-100%)
    comm_score = calculate_communication_score(text)
    
    # Overall Fit Score
    overall_fit = (match_score * 0.4) + (tech_score * 0.4) + (comm_score * 0.2)
    overall_fit = min(100, round(overall_fit, 1))
    
    # Final Decision
    final_decision = "SELECTED" if overall_fit >= 60 else "NOT SELECTED"
    
    # Identify Strengths
    strengths = []
    if match_score > 70: strengths.append(f"Strong alignment with {selected_role} requirements")
    if work_exp_found: strengths.append("Verified professional work history")
    if comm_score > 80: strengths.append("Excellent professional communication & documentation")
    if certs_found: strengths.append(f"Holding {len(certs_found)} industry-recognized certifications")
    
    # Intelligent Role Suggestion
    suggested_role = "None"
    suggestion_reason = "No better matching role identified."
    
    if final_decision == "NOT SELECTED":
        best_alt_score = 0
        for role, data in ROLE_BENCHMARKS.items():
            if role == selected_role: continue
            alt_found = [s for s in data["Skills"] if s.lower() in t_lower]
            alt_score = (len(alt_found) / len(data["Skills"]) * 100) if data["Skills"] else 0
            if alt_score > best_alt_score and alt_score > 40:
                best_alt_score = alt_score
                suggested_role = role
                suggestion_reason = f"Candidate shows higher technical alignment ({round(alt_score)}%) with {role} skillset."

    reason = f"Candidate match with {selected_role} is {round(overall_fit)}%. "
    if final_decision == "NOT SELECTED":
        reason += f"Missing critical skills: {', '.join(missing_required[:3])}."
    else:
        reason += f"Demonstrates core competencies in {', '.join(found_required[:3])}."

    report_data = {
        "Skills": {"status": "FOUND" if found_required else "NOT FOUND", "details": ", ".join(found_required[:10])},
        "Work Experience": {"status": "FOUND" if work_exp_found else "NOT FOUND", "details": ", ".join(valid_exp_lines[:2])},
        "Certifications": {"status": "FOUND" if certs_found else "NOT FOUND", "details": ", ".join(certs_found[:2])},
        "Internships": {"status": "FOUND" if any('intern' in l.lower() for l in lines) else "NOT FOUND", "details": "Found in records" if any('intern' in l.lower() for l in lines) else "None"}
    }

    return {
        "name": lines[0][:30] if lines else "Candidate",
        "profile_pic": profile_pic,
        "selected_role": selected_role,
        "role_match_score": round(match_score, 1),
        "technical_score": round(tech_score, 1),
        "communication_score": round(comm_score, 1),
        "overall_fit_score": overall_fit,
        "key_strengths": strengths if strengths else ["Basic technical awareness"],
        "missing_skills": missing_required[:5],
        "status": final_decision,
        "reason": reason,
        "suggested_role": suggested_role,
        "suggestion_reason": suggestion_reason,
        "report_data": report_data,
        "top_5_technical_skills": found_required[:5],
        "resume_score": overall_fit # For compatibility with UI gauges
    }
