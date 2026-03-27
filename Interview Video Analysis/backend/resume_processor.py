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

# --- Role-Based Benchmarks ---
ROLE_BENCHMARKS = {
    "IT / Software Jobs": {
        "Skills": ['python', 'java', 'c++', 'javascript', 'react', 'django', 'flask', 'nodejs', 'mongodb', 'docker', 'aws', 'git', 'sql', 'machine learning', 'data structures', 'algorithms'],
        "Projects": ['software', 'app', 'system', 'web', 'tool', 'github', 'coding', 'development']
    },
    "Corporate / Management Roles": {
        "Skills": ['leadership', 'management', 'project management', 'communication', 'decision making', 'strategy', 'operations', 'stakeholder', 'team building', 'presentation'],
        "Projects": ['project', 'team', 'managed', 'led', 'coordinated', 'handling', 'operations']
    },
    "Sales & Marketing Jobs": {
        "Skills": ['sales', 'marketing', 'persuasion', 'communication', 'negotiation', 'digital marketing', 'seo', 'content strategy', 'advertising', 'crm', 'leads', 'revenue'],
        "Projects": ['campaign', 'marketing', 'sales', 'growth', 'market research', 'branding']
    },
    "Core / Technical Jobs (Non-IT)": {
        "Skills": ['mechanical', 'civil', 'electrical', 'autocad', 'design', 'manufacturing', 'site', 'field work', 'thermodynamics', 'structural', 'analysis', 'machinery'],
        "Projects": ['core', 'technical', 'field', 'infrastructure', 'design', 'machinery', 'plant']
    },
    "Finance & Accounting Jobs": {
        "Skills": ['accounting', 'finance', 'excel', 'tally', 'auditing', 'taxation', 'financial analysis', 'banking', 'investment', 'ledger', 'balance sheet', 'gst'],
        "Projects": ['finance', 'financial', 'audit', 'accounts', 'tax', 'portfolio']
    }
}

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
            # Find the largest image by area (width * height)
            best = max(images, key=lambda img: (img.get('width', 0) or 0) * (img.get('height', 0) or 0))
            # Check if image is reasonable size for a headshot (at least 30x30 px)
            w = best.get('width', 0) or 0
            h = best.get('height', 0) or 0
            if w < 30 or h < 30:
                return None
            # Extract the image data from the page
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

def extract_resume_metadata(file_stream, selected_role="IT / Software Jobs") -> dict:
    """Advanced & Strict Role-Based HR Resume Analyzer AI."""
    # Read file content
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
    report_data = {}
    
    # Get rolebenchmarks (default to IT if not found)
    benchmarks = ROLE_BENCHMARKS.get(selected_role, ROLE_BENCHMARKS["IT / Software Jobs"])
    
    # 1. Skills (Filtered by Role Relevance)
    skills_found = [s for s in benchmarks["Skills"] if s in t_lower]
    report_data["Skills"] = {"status": "FOUND" if skills_found else "NOT FOUND", "details": ", ".join(skills_found[:10]) if skills_found else "None"}

    # 2. Projects (Role Relevance + content validation)
    projects_found = []
    for line in lines:
        if any(k in line.lower() for k in benchmarks["Projects"]) and len(line) > 12:
            projects_found.append(line)
    report_data["Projects"] = {"status": "FOUND" if projects_found else "NOT FOUND", "details": ", ".join([p[:45].strip() + "..." for p in projects_found[:3]]) if projects_found else "None"}

    # 3. Workshops (General check)
    w_keys = ['workshop', 'training', 'seminar', 'bootcamp', 'webinar', 'certification course']
    workshops_found = [line for line in lines if any(k in line.lower() for k in w_keys) and len(line) > 10]
    report_data["Workshops/Trainings"] = {"status": "FOUND" if workshops_found else "NOT FOUND", "details": ", ".join(workshops_found[:2]) if workshops_found else "None"}

    # 4. Certifications (STRICT: Key + Valid Org)
    certs_found = []
    for line in lines:
        l_low = line.lower()
        has_key = any(k in l_low for k in CERT_KEYS)
        has_org = any(o in l_low for o in CERT_ORGS)
        if has_key and has_org:
            certs_found.append(line)
    report_data["Certifications"] = {"status": "FOUND" if certs_found else "NOT FOUND", "details": ", ".join(certs_found[:2]) if certs_found else "None"}

    # 5. Internships (STRICT: Key + Role/Duration)
    interns_found = []
    for line in lines:
        l_low = line.lower()
        if 'intern' in l_low:
            has_role = any(r in l_low for r in ROLE_INDICATORS)
            has_dur = bool(re.search(DURATION_PATTERN, l_low))
            if has_role or has_dur:
                interns_found.append(line)
    report_data["Internships"] = {"status": "FOUND" if interns_found else "NOT FOUND", "details": ", ".join(interns_found[:2]) if interns_found else "None"}

    # 6. Work Experience (STRICT: Not an address, must have role/position + duration)
    work_found = []
    for line in lines:
        l_low = line.lower()
        if any(noise in l_low for noise in ['street', 'road', 'nagar', 'colony', 'apartment', 'house no']): 
            continue
        has_exp_key = any(k in l_low for k in ['experience', 'worked at', 'employment', 'developer at', 'engineer at'])
        has_role = any(r in l_low for r in ROLE_INDICATORS)
        has_dur = bool(re.search(DURATION_PATTERN, l_low))
        if (has_exp_key and (has_role or has_dur)) or (has_role and has_dur):
            work_found.append(line)
    report_data["Work Experience"] = {"status": "FOUND" if work_found else "NOT FOUND", "details": ", ".join(work_found[:2]) if work_found else "None"}

    # Communication Skill Logic
    comm_percent = calculate_communication_score(text)
    
    # --- Role Fit & Selection Logic ---
    # Role Fit Score (0-10) based on skills and projects
    skill_score = (len(skills_found) / 5) * 5  # Max 5 points for skills
    proj_score = (len(projects_found) / 2) * 5  # Max 5 points for projects
    role_fit_score = min(10, round(skill_score + proj_score, 1))

    # Overall Resume Score (0-10) based on category presence
    found_categories = 0
    for cat in ["Skills", "Projects", "Workshops/Trainings", "Certifications", "Internships", "Work Experience"]:
        if report_data[cat]["status"] == "FOUND": found_categories += 1
    resume_score = round((found_categories / 6) * 10, 1)

    # Final Decision Status
    # Criteria: Role Fit > 6 AND (Skills FOUND OR Experience FOUND) AND Communication > 50
    is_selected = (role_fit_score >= 6) and (len(skills_found) > 0 or len(work_found) > 0) and (comm_percent >= 50)
    status = "SELECTED" if is_selected else "NOT SELECTED"
    
    # Reason Generator
    if is_selected:
        reason = f"Candidate matches {len(skills_found)} role-specific skills with a strong {role_fit_score}/10 Fit Index. "
        reason += f"Communication quality ({comm_percent}%) meets professional standards."
    else:
        if role_fit_score < 6:
            reason = f"Low role alignment ({role_fit_score}/10). Resume lacks sufficient keywords relevant to {selected_role}."
        elif comm_percent < 50:
            reason = "Communication quality score is below the required 50% threshold for professional intake."
        else:
            reason = "Candidate lacks either verified skills or professional experience in the selected domain."

    return {
        "name": "Candidate Profile", # Placeholder, name extraction could be added if needed
        "selected_role": selected_role,
        "completeness_score": resume_score, # Mapping old key for compatibility
        "resume_score": resume_score,
        "role_fit_score": role_fit_score,
        "communication_skills": comm_percent,
        "selection_status": status,
        "selection_reason": reason,
        "report_data": report_data,
        "raw_text": text[:500] + "..."
    }

    return {
        "name": lines[0][:30] if lines else "Candidate",
        "profile_pic": profile_pic,
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
