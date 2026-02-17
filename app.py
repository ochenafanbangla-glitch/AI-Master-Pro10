from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file
import os
import uuid
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
import requests

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

if __name__ == "__main__":
    app.run(debug=True, port=5000)
