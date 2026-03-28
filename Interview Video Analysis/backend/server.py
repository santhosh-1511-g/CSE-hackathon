from flask import Flask, request, jsonify, send_from_directory, send_file
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
import os
import base64
import numpy as np
from database import get_db
from video_analysis import analyze_video
from scoring_engine import get_weighted_score
from resume_processor import extract_resume_metadata
from bson import ObjectId
import sys
import io
import threading
import tempfile
from fpdf import FPDF
from datetime import datetime

# Force UTF-8 for all console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, Exception):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass  # Last resort: let it run with default encoding

app = Flask(__name__)
CORS(app)
# ✅ Custom JSON Provider to handle NumPy types & ObjectIds
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

app.json = CustomJSONProvider(app)

@app.before_request
def log_request_info():
    app.logger.info('--- NEW REQUEST ---')
    app.logger.info(f'Method: {request.method}')
    app.logger.info(f'URL: {request.url}')
    app.logger.info(f'Headers: {request.headers}')
    app.logger.info(f'Body: {request.get_data(as_text=True)}')
    app.logger.info('-------------------')

# Lazy database connection - only connect when needed
_db = None
def get_db_connection():
    global _db
    if _db is not None:
        # Verify existing connection is still alive
        try:
            _db.client.admin.command('ping')
            return _db
        except Exception:
            app.logger.warning("[!] Lost MongoDB connection, will retry...")
            _db = None

    # Attempt to connect (or reconnect)
    try:
        _db = get_db()
        if _db is not None:
            app.logger.info("Mongo Database initialised successfully")
        else:
            app.logger.error("[!] MongoDB connection failed after retries.")
    except Exception as e:
        app.logger.error(f"[!] MongoDB connection error: {e}")
        _db = None
    return _db


# ✅ Helper function to handle ObjectId serialization
def serialize_mongo_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

# ✅ Recursive function to convert NumPy types to Python types for MongoDB/JSON
def clean_numpy_types(obj):
    if isinstance(obj, dict):
        return {k: clean_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_numpy_types(x) for x in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        video_file = request.files['video']
        candidate_id = request.form.get('candidate_id')
        candidate_name = request.form.get('candidate_name')
        
        # ✅ Save file immediately and spawn background thread
        if not video_file:
            return jsonify({"status": "error", "message": "No video file provided"}), 400
            
        # Use a proper uploads directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        uploads_dir = os.path.join(base_dir, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Create a unique filename
        filename = f"vid_{candidate_id or 'new'}_{os.urandom(4).hex()}.mp4"
        temp_path = os.path.join(uploads_dir, filename)
        video_file.save(temp_path)
        
        app.logger.info(f"Video saved to {temp_path}. Starting background analysis...")

        def run_async_analysis(path, cid, name):
            try:
                # Perform analysis
                from video_analysis import analyze_video_path, extract_audio_text
                from scoring_engine import get_weighted_score

                app.logger.info(f"Background thread started for candidate {cid}")
                
                metrics = analyze_video_path(path)
                transcript = extract_audio_text(path)
                metrics["transcript"] = transcript

                # Calculate Score & Integrity Index
                gaze_away = metrics.get('video', {}).get('gazeAwayFrames', 0)
                sampled = metrics.get('video', {}).get('sampledFrames', 1)
                gaze_dev = gaze_away / sampled if sampled > 0 else 0
                emotion_probs = metrics.get('emotionProbabilities', {})
                resume_profile = None # In async we don't necessarily have it yet, or can fetch it
                
                # Fetch existing doc for resume_profile if cid exists
                db = get_db_connection()
                if db is not None and cid:
                    doc = db.results.find_one({"_id": ObjectId(cid)})
                    if doc:
                        resume_profile = doc.get('resume_profile')
                
                report = get_weighted_score(transcript, gaze_dev, emotion_probs, resume_profile)
                metrics["integrity_index"] = report.get("final_score", 0)
                metrics["analysis_report"] = report

                # Cleanup the temp file after analysis

                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        app.logger.warning(f"Failed to remove temp file {path}: {e}")

                db = get_db_connection()
                if db is not None:
                    mongo_result = clean_numpy_types(metrics)
                    if name:
                        mongo_result["candidate_name"] = name
                    mongo_result["status"] = "Processed"
                    
                    if cid:
                        db.results.update_one(
                            {"_id": ObjectId(cid)},
                            {"$set": mongo_result}
                        )
                    else:
                        db.results.insert_one(mongo_result)
                    app.logger.info(f"Background analysis complete for {cid or 'new candidate'}")
            except Exception as e:
                app.logger.error(f"Async analysis failed: {e}")
                import traceback
                traceback.print_exc()

        # Update status to 'Processing' if cid exists
        db = get_db_connection()
        if db is not None and candidate_id:
            db.results.update_one(
                {"_id": ObjectId(candidate_id)},
                {"$set": {"status": "Processing"}}
            )

        # Start thread
        thread = threading.Thread(target=run_async_analysis, args=(temp_path, candidate_id, candidate_name))
        thread.daemon = True
        thread.start()

        return jsonify({
            "status": "accepted", 
            "message": "Analysis started in background", 
            "candidate_id": candidate_id
        }), 202

    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        app.logger.error(f"Analysis error: {err_msg}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/results', methods=['GET'])
def get_results():
    db = get_db_connection()
    if db is None:
        return jsonify({"error": "Database not available"}), 503
    try:
        data = list(db.results.find({}))
        data = [serialize_mongo_doc(doc) for doc in data]
        return jsonify({"results": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/results/<id>', methods=['GET'])
def get_result(id):
    db = get_db_connection()
    if db is None:
        return jsonify({"error": "Database not available"}), 503
    try:
        doc = db.results.find_one({"_id": ObjectId(id)})
        if not doc:
            return jsonify({"error": "Not found"}), 404
        return jsonify(serialize_mongo_doc(doc))
    except Exception as e:
        return jsonify({"error": "Invalid id or record not found"}), 400

@app.route('/api/report/<id>', methods=['GET'])
def get_report(id):
    db = get_db_connection()
    if db is None:
        return jsonify({"error": "Database not available"}), 503
    try:
        doc = db.results.find_one({"_id": ObjectId(id)})
        if not doc:
            return jsonify({"error": "Not found"}), 404
            
        # Insert before returning the JSON response
        print("-----------------------------------------")
        print(f"DEBUG: MongoDB Document Keys: {list(doc.keys())}")
        if "resume_profile" in doc:
            print(f"DEBUG: resume_profile found: {doc['resume_profile']}")
        else:
            print("DEBUG: resume_profile is MISSING in MongoDB!")
        print("-----------------------------------------")
            
        transcript = doc.get('transcript', '')
        
        # Calculate gaze deviation
        video_data = doc.get('video', {})
        gaze_away = video_data.get('gazeAwayFrames', 0)
        sampled = video_data.get('sampledFrames', 1)
        gaze_dev = gaze_away / sampled if sampled > 0 else 0
        
        emotion = doc.get('emotionProbabilities', {})
        resume_profile = doc.get('resume_profile', {
            "role_match_score": 0,
            "technical_score": 0,
            "communication_score": 0,
            "overall_fit_score": 0,
            "status": "PENDING",
            "reason": "Resume data not yet synchronized. Please re-upload.",
            "report_data": {}
        })
        
        # Generate Advanced Multimodal Report
        report = get_weighted_score(transcript, gaze_dev, emotion, resume_profile)
        report['raw_data'] = serialize_mongo_doc(doc)
        
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/report/pdf/<id>', methods=['GET'])
def download_pdf_report(id):
    db = get_db_connection()
    if db is None:
        return jsonify({"error": "Database not available"}), 503
    try:
        doc = db.results.find_one({"_id": ObjectId(id)})
        if not doc:
            return jsonify({"error": "Not found"}), 404
            
        # 1. Gather all metrics (Reuse get_report logic)
        transcript = doc.get('transcript', '')
        video_data = doc.get('video', {})
        gaze_away = video_data.get('gazeAwayFrames', 0)
        sampled = video_data.get('sampledFrames', 1)
        gaze_dev = gaze_away / sampled if sampled > 0 else 0
        emotion = doc.get('emotionProbabilities', {})
        resume_profile = doc.get('resume_profile', {
            "role_match_score": 0, "technical_score": 0, "communication_score": 0, "overall_fit_score": 0,
            "status": "PENDING", "reason": "Resume data pending.", "report_data": {}
        })
        
        # 2. Get Advanced Multimodal Report
        report = get_weighted_score(transcript, gaze_dev, emotion, resume_profile)
        
        # 3. Construct PDF using fpdf2
        class EvaluationPDF(FPDF):
            def header(self):
                # Branding Header
                self.set_fill_color(79, 70, 229) # Indigo 600
                self.rect(0, 0, 210, 35, 'F')
                self.set_font('helvetica', 'B', 24)
                self.set_text_color(255, 255, 255)
                self.cell(0, 25, 'PROCTORSHIELD EVALUATION', ln=True, align='C')
                self.set_font('helvetica', 'I', 10)
                self.cell(0, -5, 'COGNI.HIRE NEURAL ANALYSIS ENGINE v4.2', ln=True, align='C')
                self.ln(20)

            def footer(self):
                self.set_y(-15)
                self.set_font('helvetica', 'I', 8)
                self.set_text_color(128, 128, 128)
                self.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Page ' + str(self.page_no()), align='C')

        pdf = EvaluationPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Sanitization helper to prevent Helvetica encoding errors
        def safe_text(text):
            if not text: return ""
            return str(text).encode('latin-1', 'replace').decode('latin-1')

        # --- SECT 1: CANDIDATE INFO ---
        pdf.set_font('helvetica', 'B', 16)
        pdf.set_text_color(30, 41, 59) # Slate 800
        pdf.cell(0, 10, safe_text(f'Candidate: {doc.get("candidate_name", "Anonymous Candidate")}'), ln=True)
        pdf.set_font('helvetica', '', 11)
        pdf.cell(0, 8, safe_text(f'Applied Position: {doc.get("selected_role", "General Talent Intake")}'), ln=True)
        pdf.cell(0, 8, f'System ID: {id}', ln=True)
        pdf.ln(10)

        # --- SECT 2: OVERALL FIT ---
        pdf.set_fill_color(248, 250, 252) # Slate 50
        pdf.rect(10, pdf.get_y(), 190, 30, 'F')
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_x(15)
        pdf.cell(0, 10, 'OVERALL NEURAL FIT INDEX', ln=True)
        pdf.set_font('helvetica', 'B', 28)
        pdf.set_text_color(79, 70, 229) # Indigo
        pdf.set_x(15)
        pdf.cell(0, 15, f'{report.get("final_score", 0)}%', ln=True)
        pdf.set_text_color(30, 41, 59)
        pdf.ln(5)

        # --- SECT 3: PERFORMANCE BREAKDOWN ---
        pdf.set_font('helvetica', 'B', 14)
        pdf.cell(0, 10, 'Diagnostic Breakdown', ln=True)
        pdf.ln(2)
        
        breakdown = report.get('performance_breakdown', {})
        metrics = [
            ('Technical Depth', f"{breakdown.get('technical', 0)}%"),
            ('Comm. Efficiency', f"{breakdown.get('communication', 0)}%"),
            ('Integrity Pass Rate', f"{report.get('integrity_index', 0)}%"),
            ('Soft Skills Bias', f"{breakdown.get('soft_skills', 0)}%")
        ]
        
        pdf.set_font('helvetica', 'B', 10)
        for label, val in metrics:
            pdf.set_text_color(100, 116, 139) # Slate 500
            pdf.cell(45, 10, label, border='B')
            pdf.set_text_color(30, 41, 59)
            pdf.cell(45, 10, val, border='B', ln=True)
        
        pdf.ln(10)

        # --- SECT 4: HR EVALUATION REPORT ---
        pdf.set_font('helvetica', 'B', 14)
        pdf.cell(0, 10, 'Candidate Evaluation Report', ln=True)
        pdf.ln(2)
        
        res = report.get('resume_profile', {})
        status = res.get('status', 'PENDING')
        pdf.set_fill_color(240, 253, 244) if status == 'SELECTED' else pdf.set_fill_color(255, 241, 242)
        pdf.rect(10, pdf.get_y(), 190, 25, 'F')
        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(21, 128, 61) if status == 'SELECTED' else pdf.set_text_color(190, 18, 60)
        pdf.set_x(15)
        pdf.cell(0, 12, f'FINAL DECISION: {status}', ln=True)
        pdf.set_font('helvetica', 'I', 9)
        pdf.set_text_color(71, 85, 105) # Slate 600
        pdf.set_x(15)
        pdf.multi_cell(180, 5, safe_text(f'REASONING: {res.get("reason", "N/A")}'))
        pdf.ln(10)

        pdf.set_font('helvetica', 'B', 11)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(95, 8, 'Key Strengths')
        pdf.cell(95, 8, 'Missing Skills', ln=True)
        
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        strengths = res.get('key_strengths', [])
        missing = res.get('missing_skills', [])
        y_before = pdf.get_y()
        for s in (strengths if strengths else ['No specific strengths identified.']):
            pdf.cell(95, 6, safe_text(f'* {s}'), ln=True)
        y_after_s = pdf.get_y()
        pdf.set_y(y_before)
        for m in (missing if missing else ['Meets core skill requirements.']):
            pdf.set_x(105)
            pdf.cell(95, 6, safe_text(f'* {m}'), ln=True)
        pdf.set_y(max(y_after_s, pdf.get_y()) + 10)

        if res.get('suggested_role') and res.get('suggested_role') != 'None':
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(79, 70, 229)
            pdf.cell(0, 10, 'Intelligent Role Placement Recommendation', ln=True)
            pdf.set_font('helvetica', 'B', 10)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 6, safe_text(f'Recommended Fit: {res.get("suggested_role")}'), ln=True)
            pdf.set_font('helvetica', 'I', 9)
            pdf.set_text_color(100, 116, 139)
            pdf.multi_cell(0, 5, safe_text(f'"{res.get("suggestion_reason")}"'))

        import io
        
        # Final output handling - use BytesIO for robust Flask transmission
        pdf_buffer = io.BytesIO(pdf.output())
        pdf_buffer.seek(0)
        
        safe_filename = doc.get("candidate_name", "Anonymous").replace('"', "'")
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Evaluation_Report_{safe_filename}.pdf"
        )
    except Exception as e:
        import traceback
        app.logger.error(f"PDF GENERATION ERROR: {traceback.format_exc()}")
        return jsonify({"error": str(e), "details": "PDF construction failed."}), 500

@app.route('/results/<id>', methods=['DELETE'])
def delete_result(id):
    db = get_db_connection()
    if db is None:
        return jsonify({"error": "Database not available"}), 503
    try:
        res = db.results.delete_one({"_id": ObjectId(id)})
        if res.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404
        return jsonify({"status": "success", "message": "Record deleted"})
    except Exception as e:
        return jsonify({"error": "Invalid id or deletion failed"}), 400

@app.route('/api/resume/upload', methods=['POST', 'OPTIONS'])
def upload_resume():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    print(f"Incoming Request: {request.method} {request.url}")
    try:
        candidate_id = request.form.get('candidate_id')
        selected_role = request.form.get('role', 'IT / Software Jobs') # Default to IT
        
        if not candidate_id:
            return jsonify({"error": "Missing candidate_id"}), 400
            
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # Process resume using role-aware metadata extraction
        resume_data = extract_resume_metadata(file.stream, selected_role=selected_role)
        
        db = get_db_connection()
        if db is not None:
            res = db.results.update_one(
                {"_id": ObjectId(candidate_id)},
                {"$set": {
                    "resume_profile": resume_data,
                    "selected_role": selected_role
                }}
            )
            if res.matched_count == 0:
                return jsonify({"error": "Candidate not found"}), 404
                
            return jsonify({"status": "success", "resume_profile": resume_data})
        else:
            return jsonify({"error": "Database not available"}), 503

    except Exception as e:
        app.logger.error(f"Resume upload error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/candidate/create', methods=['POST', 'OPTIONS'])
def create_candidate():
    print("DEBUG: Candidate creation request received")
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    try:
        json_data = request.get_json(silent=True) or {}
        name = json_data.get('name', 'Anonymous Candidate')
        db = get_db_connection()
        if db is not None:
            inserted = db.results.insert_one({
                "candidate_name": name,
                "status": "Initialized",
                "ingestion_date": "MAR 2026"
            })
            return jsonify({
                "status": "success", 
                "id": str(inserted.inserted_id),
                "candidate_id": str(inserted.inserted_id)
            }), 201
        else:
            return jsonify({"error": "Database not available"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/results/purge', methods=['DELETE'])
def purge_results():
    db = get_db_connection()
    if db is None:
        return jsonify({"error": "Database not available"}), 503
    try:
        res = db.results.delete_many({})
        return jsonify({
            "status": "success", 
            "message": f"Purged {res.deleted_count} records from the cluster.",
            "count": res.deleted_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/system/status', methods=['GET'])
def system_status():
    try:
        import psutil
        db = get_db_connection()
        db_status = "Connected" if db is not None else "Disconnected"
        
        # Use interval for more accurate CPU reading
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        
        return jsonify({
            "status": "success",
            "db": db_status,
            "cpu": cpu_usage,
            "ram": ram.percent,
            "latency": "18.4ms",
            "nodes": [
                {"name": "Inference Node A (Primary)", "status": "OPERATIONAL" if db is not None else "OFFLINE"},
                {"name": "Cognitive Model V4", "status": "HEALTHY" if db is not None else "DEGRADED"},
                {"name": "GPU Core Utilization", "status": "CPU FALLBACK"}
            ]
        })
    except Exception as e:
        import traceback
        app.logger.error(f"ADMIN STATS ERROR: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/candidate/photo', methods=['POST', 'OPTIONS'])
def upload_candidate_photo():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    try:
        candidate_id = request.form.get('candidate_id')
        if not candidate_id:
            return jsonify({"error": "Missing candidate_id"}), 400
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # Read image and convert to base64 data URI
        img_bytes = file.read()
        content_type = file.content_type or 'image/png'
        b64_str = base64.b64encode(img_bytes).decode('utf-8')
        data_uri = f"data:{content_type};base64,{b64_str}"

        db = get_db_connection()
        if db is not None:
            res = db.results.update_one(
                {"_id": ObjectId(candidate_id)},
                {"$set": {"profile_pic": data_uri}}
            )
            if res.matched_count == 0:
                return jsonify({"error": "Candidate not found"}), 404
            return jsonify({"status": "success", "profile_pic": data_uri})
        else:
            return jsonify({"error": "Database not available"}), 503
    except Exception as e:
        app.logger.error(f"Photo upload error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/candidate/<id>/photo', methods=['GET'])
def get_candidate_photo(id):
    db = get_db_connection()
    if db is None:
        return jsonify({"error": "Database not available"}), 503
    try:
        doc = db.results.find_one({"_id": ObjectId(id)}, {"profile_pic": 1})
        if not doc:
            return jsonify({"error": "Not found"}), 404
        pic = doc.get("profile_pic") or doc.get("resume_profile", {}).get("profile_pic")
        return jsonify({"profile_pic": pic})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/")
def home():
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    return send_from_directory(frontend_dir, "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    return send_from_directory(frontend_dir, filename)

if __name__ == "__main__":
    app.run(debug=True)
