from flask import Flask, request, jsonify
from flask_cors import CORS
from database import get_db
from video_analysis import analyze_video
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

# Lazy database connection - only connect when needed
_db = None
def get_db_connection():
    global _db
    if _db is None:
        try:
            _db = get_db()
            # Test the connection
            _db.client.admin.command('ping')
            print("Mongo Database initialised")
        except Exception as e:
            print(f"[!] MongoDB connection failed: {e}")
            print("[!] Server will run without database. Results won't be saved.")
            _db = None
    return _db

# ✅ Helper function to handle ObjectId serialization
def serialize_mongo_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        video_file = request.files['video']
        result = analyze_video(video_file)
        
        if "error" in result:
            return jsonify({"status": "error", "message": result["error"]}), 500

        # ✅ Insert result and capture inserted ID (if DB is available)
        db = get_db_connection()
        if db:
            try:
                inserted = db.results.insert_one(result)
                result["_id"] = str(inserted.inserted_id)  # Convert ObjectId to string
            except Exception as db_error:
                print(f"Database save failed: {db_error}")
                # Continue without saving to DB
        else:
            result["_id"] = None  # No DB, no ID
        
        return jsonify({"status": "success", "analysis": result})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def home():
    return "Interview Video Analysis Backend is Running!"
@app.route('/results', methods=['GET'])
def get_results():
    db = get_db_connection()
    if not db:
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
    if not db:
        return jsonify({"error": "Database not available"}), 503
    try:
        doc = db.results.find_one({"_id": ObjectId(id)})
        if not doc:
            return jsonify({"error": "Not found"}), 404
        return jsonify(serialize_mongo_doc(doc))
    except Exception as e:
        return jsonify({"error": "Invalid id"}), 400

if __name__ == "__main__":
    app.run(debug=True)
