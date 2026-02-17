from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file
import os
import uuid
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from models.model_a_core import ModelACore
from utils.db_manager import add_trade, get_recent_trades, init_db, delete_trade, clear_db, get_total_trades_count, DB_PATH, archive_all_trades, get_session_trades
from utils.auth_helper import login_required, admin_required
from utils.multi_manager import MultiManagerSystem
import requests

# Configure Logging
IS_VERCEL = "VERCEL" in os.environ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask App
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ai-master-pro-secure-key-2026")

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_signal(signal_data):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    msg = f"🚀 *AI MASTER PRO V.10 SIGNAL*\n\n"
    msg += f"📊 Prediction: *{signal_data['prediction']}*\n"
    msg += f"🎯 Confidence: {signal_data['confidence']}%\n"
    msg += f"🔥 Probability: {signal_data.get('probability', 0)}%\n"
    msg += f"📈 Volatility: {signal_data.get('volatility_status', 'STABLE')}\n"
    msg += f"🔍 Source: {signal_data['source']}\n"
    
    if signal_data.get('risk_alert'):
        msg += f"\n⚠️ *Risk Alert:* {signal_data['risk_alert']}"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=2)
    except Exception as e:
        logger.error(f"Telegram Error: {e}")

# Initialize AI Models and Multi-Manager System lazily
model_a = None
manager_system = None

def get_systems():
    global model_a, manager_system
    try:
        if model_a is None:
            model_a = ModelACore()
            if not os.path.exists(model_a.db_path):
                init_db()
        if manager_system is None:
            manager_system = MultiManagerSystem(model_a, model_a.db_path)
        return model_a, manager_system
    except Exception as e:
        logger.error(f"System Init Error: {e}", exc_info=True)
        raise e

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
    """Health check endpoint for Vercel diagnostics."""
    try:
        m_a, _ = get_systems()
        return jsonify({
            "status": "healthy",
            "db_path": m_a.db_path,
            "db_exists": os.path.exists(m_a.db_path),
            "is_vercel": IS_VERCEL
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route("/")
def dashboard():
    """Main Trading Dashboard."""
    try:
        get_systems() # Ensure systems are ready
        recent_trades = get_recent_trades(10)
        total_collected = get_total_trades_count()
        all_trades = get_recent_trades(50)
        completed_trades = [t for t in all_trades if t["actual_result"] is not None]
        if completed_trades:
            wins = sum(1 for t in completed_trades if t["ai_prediction"] == t["actual_result"])
            accuracy = round((wins / len(completed_trades)) * 100, 1)
        else:
            accuracy = 0.0
        
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
        send_telegram_signal(processed_signal)
        
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

@app.route("/api/save-bulk-pattern", methods=["POST"])
def save_bulk_pattern():
    data = request.json
    if not data or 'pattern' not in data:
        return jsonify({"status": "error", "message": "No pattern provided"}), 400
    
    pattern = data.get("pattern", [])
    try:
        ist_now = datetime.now(tz=timezone(timedelta(hours=5, minutes=30)))
        session_id = session.get("session_id")
        user_id = session.get("user_id", "guest_user")
        
        for i, result in enumerate(pattern):
            timestamp = (ist_now + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
            trade_data = {
                "user_id": user_id,
                "session_id": session_id,
                "trade_id": f"INIT-{str(uuid.uuid4())[:4]}",
                "timestamp": timestamp,
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

@app.route("/api/submit-result", methods=["POST"])
def submit_result():
    data = request.json
    actual_result = data.get("result")
    if not actual_result or actual_result not in ["BIG", "SMALL"]:
        return jsonify({"status": "error", "message": "Invalid result."}), 400
    
    last_signal = session.get("last_signal")
    trade_id = last_signal["trade_id"] if last_signal else str(uuid.uuid4())[:8]
    prediction = last_signal["prediction"] if last_signal else "INITIAL"
    confidence = last_signal["confidence"] if last_signal else 0.0
    source = last_signal["source"] if last_signal else "Direct Entry"
    
    trade_data = {
        "user_id": session.get("user_id", "guest_user"),
        "session_id": session.get("session_id"),
        "trade_id": trade_id,
        "ai_prediction": prediction,
        "ai_confidence": confidence,
        "signal_source": source,
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
        session_id = session.get("session_id")
        trades = get_session_trades(session_id)
        if not trades: return jsonify({"status": "error", "message": "No data."}), 404
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=trades[0].keys())
        writer.writeheader()
        writer.writerows(trades)
        return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=f"CVC_{session_id[:8]}.csv")
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/admin-secure-portal")
@login_required
def admin_panel():
    return render_template("admin/panel.html", trades=get_recent_trades(50))

if __name__ == "__main__":
    if not os.path.exists(DB_PATH): init_db()
    app.run(debug=True, port=5000)
