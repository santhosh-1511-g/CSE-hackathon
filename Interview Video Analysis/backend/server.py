from flask import Flask, request, jsonify, send_from_directory
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
import os
import numpy as np
from database import get_db
from video_analysis import analyze_video
from scoring_engine import get_weighted_score
from resume_processor import extract_resume_metadata
from bson import ObjectId
import sys
import io

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
        
        result = analyze_video(video_file)
        
        if "error" in result:
            return jsonify({"status": "error", "message": result["error"]}), 500

        # ✅ Insert/Update result and capture ID (if DB is available)
        db = get_db_connection()
        if db is not None:
            try:
                # Clean result of NumPy types before MongoDB insertion
                mongo_result = clean_numpy_types(result)
                
                if candidate_name:
                    mongo_result["candidate_name"] = candidate_name
                
                if candidate_id:
                    app.logger.info(f"Updating candidate: {candidate_id}")
                    mongo_result["status"] = "Processed"  # ✅ Mark as processed
                    db.results.update_one(
                        {"_id": ObjectId(candidate_id)},
                        {"$set": mongo_result}
                    )
                    result["_id"] = candidate_id
                else:
                    app.logger.info(f"Saving new result to collection: {db.results.name}")
                    mongo_result["status"] = "Processed"  # ✅ Mark as processed
                    inserted = db.results.insert_one(mongo_result)
                    app.logger.info(f"Inserted ID: {inserted.inserted_id}")
                    result["_id"] = str(inserted.inserted_id)
            except Exception as db_error:
                app.logger.error(f"Database save/update failed: {db_error}")
                # Continue without saving to DB
        else:
            result["_id"] = None  # No DB, no ID
        
        return jsonify({"status": "success", "analysis": result})

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
        resume_profile = doc.get('resume_profile', None)
        
        # Generate Advanced Multimodal Report
        report = get_weighted_score(transcript, gaze_dev, emotion, resume_profile)
        print(f"DEBUG: Report Data Keys: {report.keys()}")
        report['raw_data'] = serialize_mongo_doc(doc)
        
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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
        if not candidate_id:
            return jsonify({"error": "Missing candidate_id"}), 400
            
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # Process resume using pdfplumber stream
        resume_data = extract_resume_metadata(file.stream)
        
        db = get_db_connection()
        if db is not None:
            res = db.results.update_one(
                {"_id": ObjectId(candidate_id)},
                {"$set": {"resume_profile": resume_data}}
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
            return jsonify({"status": "success", "candidate_id": str(inserted.inserted_id)}), 201
        else:
            return jsonify({"error": "Database not available"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
