from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file
import os
import uuid
import csv
import io
import logging
import base64
from datetime import datetime, timedelta, timezone
import requests
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask App
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ai-master-pro-secure-key-2026")

# Global variables for systems
model_a = None
manager_system = None
IS_VERCEL = "VERCEL" in os.environ

def get_systems():
    global model_a, manager_system
    try:
        from models.model_a_core import ModelACore
        from utils.db_manager import init_db
        from utils.multi_manager import MultiManagerSystem
        
        if model_a is None:
            model_a = ModelACore()
            if not os.path.exists(model_a.db_path):
                init_db()
        if manager_system is None:
            manager_system = MultiManagerSystem(model_a, model_a.db_path)
        return model_a, manager_system
    except Exception as e:
        logger.error(f"System Init Error: {e}", exc_info=True)
        return None, None

# Helper imports that are safe
try:
    from utils.db_manager import add_trade, get_recent_trades, delete_trade, get_total_trades_count, archive_all_trades, get_session_trades
except Exception as e:
    logger.error(f"Utility Import Error: {e}")

@app.before_request
def ensure_session():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    if "start_time" not in session:
        session["start_time"] = datetime.now().timestamp()
    if "user_id" not in session:
        session["user_id"] = "guest_user"

@app.route("/health")
def health_check():
    m_a, _ = get_systems()
    return jsonify({
        "status": "healthy" if m_a else "unhealthy",
        "is_vercel": IS_VERCEL
    })

@app.route("/")
def dashboard():
    try:
        m_a, m_s = get_systems()
        if not m_a: return "System Initialization Failed", 500
        
        recent_trades = get_recent_trades(10)
        total_collected = get_total_trades_count()
        all_trades = get_recent_trades(50)
        completed_trades = [t for t in all_trades if t["actual_result"] is not None]
        accuracy = round((sum(1 for t in completed_trades if t["ai_prediction"] == t["actual_result"]) / len(completed_trades)) * 100, 1) if completed_trades else 0.0
        
        return render_template("user/dashboard.html", 
                               trades=recent_trades, 
                               total_collected=total_collected, 
                               target_trades=0,
                               learning_percent=100,
                               accuracy=accuracy)
    except Exception as e:
        logger.error(f"Dashboard Error: {e}", exc_info=True)
        return f"Internal Server Error: {str(e)}", 500

@app.route("/api/dashboard-data", methods=["GET"])
def get_dashboard_data():
    try:
        recent_trades = get_recent_trades(10)
        total_collected = get_total_trades_count()
        all_trades = get_recent_trades(50)
        completed_trades = [t for t in all_trades if t["actual_result"] is not None]
        accuracy = round((sum(1 for t in completed_trades if t["ai_prediction"] == t["actual_result"]) / len(completed_trades)) * 100, 1) if completed_trades else 0.0
        
        _, m_s = get_systems()
        results = m_s.get_recent_results(20)
        vol_score, vol_status = m_s.calculate_volatility(results)
        
        return jsonify({
            "status": "success",
            "trades": recent_trades,
            "total_collected": total_collected,
            "accuracy": accuracy,
            "volatility_score": vol_score,
            "volatility_status": vol_status,
            "learning_percent": 100
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/get-signal", methods=["GET"])
def get_signal():
    try:
        m_a, m_s = get_systems()
        raw_signal = m_a.predict()
        processed_signal = m_s.process_signal(raw_signal)
        
        trade_id = str(uuid.uuid4())[:8]
        session["last_signal"] = {
            "trade_id": trade_id,
            "prediction": processed_signal["prediction"],
            "confidence": processed_signal["confidence"],
            "source": processed_signal["source"]
        }
        return jsonify({
            "status": "success",
            "trade_id": trade_id,
            "prediction": processed_signal["prediction"],
            "confidence": processed_signal["confidence"],
            "source": processed_signal["source"],
            "risk_alert": processed_signal.get("risk_alert", ""),
            "dragon_alert": processed_signal.get("dragon_alert", ""),
            "probability": processed_signal.get("probability", 0),
            "volatility_score": processed_signal.get("volatility_score", 0),
            "volatility_status": processed_signal.get("volatility_status", "STABLE"),
            "warning_color": processed_signal.get("warning_color", "Green")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/submit-result", methods=["POST"])
def submit_result():
    data = request.json
    actual_result = data.get("result")
    if not actual_result or actual_result not in ["BIG", "SMALL"]:
        return jsonify({"status": "error", "message": "Invalid result."}), 400
    
    last_signal = session.get("last_signal")
    trade_data = {
        "user_id": session.get("user_id", "guest_user"),
        "session_id": session.get("session_id"),
        "trade_id": last_signal["trade_id"] if last_signal else str(uuid.uuid4())[:8],
        "ai_prediction": last_signal["prediction"] if last_signal else "INITIAL",
        "ai_confidence": last_signal["confidence"] if last_signal else 0.0,
        "signal_source": last_signal["source"] if last_signal else "Direct Entry",
        "actual_result": actual_result
    }
    
    try:
        if add_trade(trade_data):
            m_a, _ = get_systems()
            m_a.train_from_db()
            session.pop("last_signal", None)
            return jsonify({"status": "success", "message": "Result submitted."}), 200
        return jsonify({"status": "error", "message": "Failed to save."}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/save-bulk-pattern", methods=["POST"])
def save_bulk_pattern():
    data = request.json
    pattern = data.get("pattern", [])
    try:
        ist_now = datetime.now(tz=timezone(timedelta(hours=5, minutes=30)))
        for i, result in enumerate(pattern):
            trade_data = {
                "user_id": session.get("user_id", "guest_user"),
                "session_id": session.get("session_id"),
                "trade_id": f"INIT-{str(uuid.uuid4())[:4]}",
                "timestamp": (ist_now + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S"),
                "ai_prediction": "INITIAL",
                "ai_confidence": 0.0,
                "signal_source": "Bulk Pattern Input",
                "actual_result": result
            }
            add_trade(trade_data)
        m_a, _ = get_systems()
        m_a.train_from_db()
        return jsonify({"status": "success", "message": f"{len(pattern)} patterns saved."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/undo-trade", methods=["POST"])
def undo_trade():
    trade_id = request.json.get("trade_id")
    try:
        delete_trade(trade_id)
        m_a, _ = get_systems()
        m_a.train_from_db()
        return jsonify({"status": "success", "message": "Deleted."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/new-session", methods=["POST"])
def new_session():
    try:
        archive_all_trades()
        m_a, _ = get_systems()
        m_a.train_from_db(include_archived=True)
        session.pop("last_signal", None)
        session["session_id"] = str(uuid.uuid4())
        return jsonify({"status": "success", "message": "New Session Started!"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/download-cvc")
def download_cvc():
    try:
        trades = get_session_trades(session.get("session_id"))
        if not trades: return jsonify({"status": "error", "message": "No data."}), 404
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=trades[0].keys())
        writer.writeheader()
        writer.writerows(trades)
        return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name="CVC_Data.csv")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/ocr-screenshot", methods=["POST"])
def ocr_screenshot():
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No file selected"}), 400

        # Convert image to base64 for GPT-4o-mini
        image_content = file.read()
        base64_image = base64.b64encode(image_content).decode('utf-8')

        # Call OpenAI API for OCR
        # Note: Please add 'OPENAI_API_KEY' to your Vercel Environment Variables
        # We strip the key to handle potential copy-paste issues with whitespace/newlines
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            api_key = api_key.strip()
        
        # Debug: Log status (do not log the key itself for security)
        if api_key:
            logger.info(f"OCR API Key detected (Length: {len(api_key)})")
        else:
            # Fallback check just in case
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if api_key:
                logger.info(f"OCR API Key detected via fallback (Length: {len(api_key)})")
            else:
                logger.error("OCR API Key NOT found in environment variables.")

        if not api_key:
            return jsonify({
                "status": "error", 
                "message": "OCR API key not configured in Vercel settings. Please ensure 'OPENAI_API_KEY' is added to Environment Variables (not as a Secret, but as a plain Environment Variable) and the app is redeployed."
            }), 500

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": "gpt-4.1-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this game history screenshot. Extract the last 15 results (Big or Small). Return ONLY a JSON array of strings, e.g., [\"BIG\", \"SMALL\", \"BIG\", ...]. If you can't find 15, return as many as you see in order from newest to oldest."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response_data = response.json()

        if response.status_code != 200:
            logger.error(f"OpenAI API Error: {response_data}")
            return jsonify({"status": "error", "message": "OCR service error"}), 500

        content = response_data['choices'][0]['message']['content'].strip()
        # Clean up the response if it's wrapped in markdown code blocks
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        import json
        results = json.loads(content)
        
        # Normalize results to B/S for the frontend inputs
        normalized = []
        for r in results:
            r_upper = r.upper()
            if "BIG" in r_upper: normalized.append("B")
            elif "SMALL" in r_upper: normalized.append("S")
        
        return jsonify({"status": "success", "results": normalized})

    except Exception as e:
        logger.error(f"OCR Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
