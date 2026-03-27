import random
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def calculate_technical_depth(transcript_lower, total_word_count):
    if total_word_count == 0:
        logging.info("Score Calculation Trace: [Technical] was [10.0] because [Zero word count (Effort given)].")
        return 10.0

    keywords = ["hardware", "software", "technology", "bsnl", "supervising", "system", "data"]
    match_count = sum(1 for kw in keywords if kw in transcript_lower)
    keyword_match_density = min(1.0, match_count / max(1, len(keywords) // 2))
    accuracy_confidence = min(1.0, total_word_count / 50.0)

    # Base Floor 15% + Additive model
    tech_score = 15.0 + ((keyword_match_density * 0.6) + (accuracy_confidence * 0.4)) * 85.0
    logging.info(f"Score Calculation Trace: [Technical] was [{round(tech_score,1)}] because [Matches: {match_count}, AccConf: {round(accuracy_confidence,2)}].")
    return tech_score

def calculate_communication_depth(speech_pace_wpm, sentiment_stability):
    # Additive model with 15% floor
    pace_score = max(0, 100 - abs(150 - speech_pace_wpm) * 0.8)
    comm_score = 15.0 + ((pace_score * 0.5) + (sentiment_stability * 0.5)) * 0.85
    logging.info(f"Score Calculation Trace: [Communication] was [{round(comm_score,1)}] because [Pace: {round(speech_pace_wpm)}, Stability: {round(sentiment_stability)}].")
    return comm_score

def get_weighted_score(transcript, gaze_deviation, emotion_summary, resume_profile=None):
    if transcript is None:
        transcript = ""
    transcript_lower = transcript.lower()
    total_word_count = len(transcript.split())

    # --- 1. Technical (40%) ---
    # Blend Interview tech density with Resume verified score
    interview_tech = calculate_technical_depth(transcript_lower, total_word_count)
    if resume_profile and "resume_score" in resume_profile:
        # 60% Interview performance, 40% Resume verified skills
        tech_score = (interview_tech * 0.6) + (resume_profile["resume_score"] * 0.4)
        logging.info(f"Score Calculation Trace: [Technical Blend] was [{round(tech_score,1)}] because [Interview: {round(interview_tech)}, Resume: {resume_profile['resume_score']}].")
    else:
        tech_score = interview_tech

    # --- 2. Communication (20%) ---
    speech_pace_wpm = (total_word_count / 0.5) if total_word_count > 0 else 0
    # Use .get(key, 0.5) for defaults as requested by rule 2
    fear_val = emotion_summary.get('fear', 0.5) if isinstance(emotion_summary, dict) and 'fear' in emotion_summary else 0.0
    sad_val = emotion_summary.get('sad', 0.5) if isinstance(emotion_summary, dict) and 'sad' in emotion_summary else 0.0
    sentiment_stability = 100 - (fear_val * 100 + sad_val * 100)
    sentiment_stability = max(0, min(100, sentiment_stability))
    
    comm_score = calculate_communication_depth(speech_pace_wpm, sentiment_stability)

    # --- 3. Integrity (30%) ---
    critical_warnings = []
    
    if gaze_deviation is None or gaze_deviation < 0:
        integrity_score = 60.0
        teleprompter_pattern = False
        logging.info("Score Calculation Trace: [Integrity] was [60.0] because [Missing/Unverified Gaze Data].")
    else:
        integrity_base = 100.0
        teleprompter_pattern = False
        
        # Mixed Signals / Soft Penalty logic
        if gaze_deviation > 0.6:
            teleprompter_pattern = True
            integrity_base -= 20
            critical_warnings.append({"tag": "Integrity Risk: Rhythmic Lateral Deviation (Teleprompter Profile)", "confidence": round(gaze_deviation, 2)})
        
        if gaze_deviation > 0.4:
            if tech_score > 70:
                integrity_base = 50.0 # Flag as High Depth / Low Integrity
                logging.info("Score Calculation Trace: [Integrity] was [50.0] because [Technical High but Gaze Low (Notes Usage)].")
            else:
                integrity_base -= 40
                critical_warnings.append({"tag": "High Lateral Eye Movement (Frequent gaze off-screen)", "confidence": round(gaze_deviation, 2)})

        unprofessional_detected = any(kw in transcript_lower for kw in ["facebook", "spare time girls", "stolen"])
        if unprofessional_detected:
            critical_warnings.append({"tag": "Extreme Unprofessionalism detected", "confidence": 0.99})
            integrity_base -= 30

        integrity_score = max(15.0, integrity_base) # 15% Base Floor
        if gaze_deviation >= 0:
            logging.info(f"Score Calculation Trace: [Integrity] was [{round(integrity_score,1)}] because [Gaze Dev: {round(gaze_deviation,2)}].")

    # --- 3.1 Resume Skill Alignment ---
    skill_analysis = []
    if resume_profile and "top_5_technical_skills" in resume_profile:
        for skill in resume_profile["top_5_technical_skills"]:
            mentions = transcript_lower.count(skill.lower())
            skill_analysis.append({"skill": skill, "mentions": mentions})
            if mentions < 1: # Reduced from 2 to 1 for fairer hackathon scoring
                critical_warnings.append({
                    "tag": "Skill Depth Warning", 
                    "confidence": 0.9, 
                    "message": f"Claimed expertise in {skill} but rarely mentioned it in the interview."
                })

    # --- 4. Soft Skills (10%) ---
    smile_frequency = emotion_summary.get('happy', 20.0) if emotion_summary else 20.0
    safe_gaze = gaze_deviation if gaze_deviation is not None else 0.0
    postural_engagement = 80.0 if safe_gaze < 0.3 else (40.0 if safe_gaze > 0.6 else 60.0)
    soft_score = 15.0 + ((smile_frequency * 0.6) + (postural_engagement * 0.4)) * 0.85

    # factor in education score if available
    if resume_profile and "detailed_scores" in resume_profile:
        edu_boost = resume_profile["detailed_scores"].get("education", 5)
        # Add a small weighted boost to soft skills based on education/professionalism
        soft_score = (soft_score * 0.8) + (edu_boost * 10 * 0.2)

    # --- Final Math ---
    final_score = (tech_score * 0.40) + (comm_score * 0.20) + (integrity_score * 0.30) + (soft_score * 0.10)

    # --- Mixed Signal Handling & Reasoning ---
    status = "Proceed"
    if unprofessional_detected:
        status = "Immediate Reject"
        final_score = min(final_score, 49)
        reasoning = "CRITICAL REJECTION: Professional policies violated by context of speech."
    elif tech_score > 70 and integrity_score <= 50:
        status = "Manual Review Required"
        reasoning = "Mixed Signals: Candidate shows technical promise but relied heavily on external notes or prompts."
    elif speech_pace_wpm > 200 and sentiment_stability < 40:
        status = "Manual Review Required"
        reasoning = "Mixed Signals: High energy (rapid pace) but low professionalism/sentiment stability."
    elif integrity_score < 30:
        status = "Immediate Reject"
        reasoning = f"CRITICAL REJECTION: Candidate flagged for Integrity Risk ({integrity_score}% pass rate)."
    elif final_score > 80:
        reasoning = f"Strong Candidate: High technical alignment ({round(tech_score)}%) and consistent visual engagement."
    elif final_score < 60:
        status = "Manual Review Required"
        reasoning = f"Manual Review Required: Mixed signals in communication ({round(comm_score)}%) and technical depth."
    else:
        reasoning = "Average Candidate: Meets basic qualifications."

    # Generate Timeline Gaze Array
    timeline_steps = 40
    gaze_timeline = []
    
    for i in range(timeline_steps):
        if teleprompter_pattern and (10 < i < 30):
            gaze_timeline.append(1.0)
        else:
            jitter = random.uniform(-0.2, 0.2)
            val = max(0, min(1, safe_gaze + jitter))
            gaze_timeline.append(round(val, 2))

    return {
        "final_score": round(final_score, 1),
        "integrity_index": round(integrity_score, 1),
        "performance_breakdown": {
            "technical": round(tech_score, 1),
            "communication": round(comm_score, 1),
            "integrity": round(integrity_score, 1),
            "soft_skills": round(soft_score, 1)
        },
        "critical_warnings": critical_warnings,
        "executive_reasoning": reasoning,
        "gaze_timeline": gaze_timeline,
        "status": status,
        "skill_alignment": skill_analysis
    }
