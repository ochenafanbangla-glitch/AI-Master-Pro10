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
log_handlers = [logging.StreamHandler()]
if not IS_VERCEL:
    try:
        log_handlers.append(logging.FileHandler("app_error.log"))
    except:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
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
        # Using a short timeout to avoid blocking the request
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=2)
    except Exception as e:
        logger.error(f"Telegram Error: {e}")

# Initialize AI Models and Multi-Manager System
model_a = None
manager_system = None

def get_systems():
    global model_a, manager_system
    if model_a is None:
        model_a = ModelACore()
        # On Vercel, init_db is handled in model_a_core or by the existence of the DB
        if not os.path.exists(model_a.db_path):
            init_db()
    if manager_system is None:
        manager_system = MultiManagerSystem(model_a, model_a.db_path)
    return model_a, manager_system

@app.before_request
def ensure_session():
    get_systems()
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    if "start_time" not in session:
        session["start_time"] = datetime.now().timestamp()
    if "user_id" not in session:
        session["user_id"] = "guest_user"

@app.route("/")
def dashboard():
    """Main Trading Dashboard: Displays recent trades and AI accuracy."""
    try:
        recent_trades = get_recent_trades(10)
        total_collected = get_total_trades_count()
        all_trades = get_recent_trades(50)
        completed_trades = [t for t in all_trades if t["actual_result"] is not None]
        if completed_trades:
            wins = sum(1 for t in completed_trades if t["ai_prediction"] == t["actual_result"])
            accuracy = round((wins / len(completed_trades)) * 100, 1)
        else:
            accuracy = 0.0
    except Exception as e:
        logger.error(f"Dashboard Error: {e}", exc_info=True)
        recent_trades = []
        total_collected = 0
        accuracy = 0.0
    target_trades = 0 
    learning_percent = 100
    return render_template("user/dashboard.html", 
                           trades=recent_trades, 
                           total_collected=total_collected, 
                           target_trades=target_trades,
                           learning_percent=learning_percent,
                           accuracy=accuracy)

@app.route("/api/dashboard-data", methods=["GET"])
def get_dashboard_data():
    """Returns live data for the dashboard without full page reload."""
    try:
        recent_trades = get_recent_trades(10)
        total_collected = get_total_trades_count()
        all_trades = get_recent_trades(50)
        completed_trades = [t for t in all_trades if t["actual_result"] is not None]
        if completed_trades:
            wins = sum(1 for t in completed_trades if t["ai_prediction"] == t["actual_result"])
            accuracy = round((wins / len(completed_trades)) * 100, 1)
        else:
            accuracy = 0.0
        target_trades = 0
        learning_percent = 100
        
        # Get volatility for dashboard
        _, m_s = get_systems()
        results = m_s.get_recent_results(20)
        vol_score, vol_status = m_s.calculate_volatility(results)
        
        return jsonify({
            "status": "success",
            "trades": recent_trades,
            "total_collected": total_collected,
            "target_trades": target_trades,
            "learning_percent": learning_percent,
            "accuracy": accuracy,
            "volatility_score": vol_score,
            "volatility_status": vol_status
        })
    except Exception as e:
        logger.error(f"Dashboard Data Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/get-signal", methods=["GET"])
def get_signal():
    """Generates a trading signal immediately."""
    try:
        m_a, m_s = get_systems()
        raw_signal = m_a.predict()
        processed_signal = m_s.process_signal(raw_signal)
        
        # Forward to Telegram (Synchronous on Vercel to ensure it completes, but with short timeout)
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
            "memory_alert": processed_signal.get("memory_alert", ""),
            "probability": processed_signal.get("probability", 0),
            "correction_status": processed_signal.get("correction_status", "NONE"),
            "detected_pattern": processed_signal.get("detected_pattern", ""),
            "warning_color": processed_signal.get("warning_color", "Green"),
            "volatility_score": processed_signal.get("volatility_score", 0),
            "volatility_status": processed_signal.get("volatility_status", "STABLE")
        })
    except Exception as e:
        logger.error(f"Get Signal Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/save-bulk-pattern", methods=["POST"])
def save_bulk_pattern():
    """Saves multiple game results at once for initial pattern learning."""
    data = request.json
    if not data or 'pattern' not in data:
        return jsonify({"status": "error", "message": "No pattern provided"}), 400
    
    pattern = data.get("pattern", [])
    if not isinstance(pattern, list) or len(pattern) == 0:
        return jsonify({"status": "error", "message": "Invalid pattern format"}), 400

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
                "user_choice": None,
                "actual_result": result,
                "bet_amount": 0
            }
            add_trade(trade_data)
        
        m_a, _ = get_systems()
        # Train synchronously on Vercel
        m_a.train_from_db()
            
        return jsonify({"status": "success", "message": f"{len(pattern)} patterns saved and AI updated."}), 200
    except Exception as e:
        logger.error(f"Bulk Pattern Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/submit-result", methods=["POST"])
def submit_result():
    """Submits actual result, validates input, and triggers AI training."""
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    actual_result = data.get("result")
    user_choice = data.get("user_choice")
    bet_amount = data.get("bet_amount", 0)
    if not actual_result or actual_result not in ["BIG", "SMALL"]:
        return jsonify({"status": "error", "message": "Invalid result input.", "code": "INVALID_RESULT"}), 400
    
    last_sub_time = session.get("last_submission_time")
    last_sub_val = session.get("last_submission_val")
    curr_time = datetime.now().timestamp()
    if last_sub_time and (curr_time - last_sub_time < 0.1) and (last_sub_val == actual_result):
        return jsonify({"status": "error", "message": "Duplicate submission detected.", "code": "DUPLICATE_SUBMISSION"}), 400
    
    session["last_submission_time"] = curr_time
    session["last_submission_val"] = actual_result
    last_signal = session.get("last_signal")
    
    if not last_signal:
        trade_id = str(uuid.uuid4())[:8]
        prediction, confidence, source = "INITIAL", 0.0, "Initial Data Collection"
    else:
        trade_id, prediction, confidence, source = last_signal["trade_id"], last_signal["prediction"], last_signal["confidence"], last_signal["source"]
    
    ist_now = datetime.now(tz=timezone(timedelta(hours=5, minutes=30)))
    timestamp_str = ist_now.strftime("%Y-%m-%d %H:%M:%S")
    trade_data = {
        "user_id": session.get("user_id", "guest_user"),
        "session_id": session.get("session_id"),
        "trade_id": trade_id,
        "timestamp": timestamp_str,
        "ai_prediction": prediction,
        "ai_confidence": confidence,
        "signal_source": source,
        "user_choice": user_choice if user_choice != "---" else None,
        "actual_result": actual_result,
        "bet_amount": bet_amount
    }
    try:
        if add_trade(trade_data):
            m_a, _ = get_systems()
            # Always train synchronously on Vercel
            m_a.train_from_db()
            
            if last_signal:
                is_correct = (last_signal["prediction"] == actual_result)
                session.pop("last_signal", None)
                msg = "Correct Prediction! AI refined." if is_correct else "AI corrected its mistake."
            else:
                msg = "Initial data point collected."
            return jsonify({"status": "success", "message": msg}), 200
        return jsonify({"status": "error", "message": "Failed to save trade.", "code": "DB_SAVE_FAILED"}), 500
    except Exception as e:
        logger.error(f"API Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e), "code": "SERVER_ERROR"}), 500

@app.route("/api/undo-trade", methods=["POST"])
def undo_trade():
    data = request.json
    trade_id = data.get("trade_id")
    if not trade_id: return jsonify({"status": "error", "message": "Trade ID required", "code": "MISSING_TRADE_ID"}), 400
    try:
        delete_trade(trade_id)
        m_a, _ = get_systems()
        m_a.train_from_db()
        return jsonify({"status": "success", "message": "Trade deleted and AI updated"}), 200
    except Exception as e:
        logger.error(f"API Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e), "code": "SERVER_ERROR"}), 500

@app.route("/api/new-session", methods=["POST"])
def new_session():
    try:
        archive_all_trades()
        m_a, _ = get_systems()
        m_a.train_from_db(include_archived=True)
        m_a.patterns["error_matrix"] = {} 
        m_a._save_patterns()
        session.pop("last_signal", None)
        session["session_id"] = str(uuid.uuid4())
        return jsonify({"status": "success", "message": "New Session Started!"}), 200
    except Exception as e:
        logger.error(f"API Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e), "code": "SERVER_ERROR"}), 500

@app.route("/api/download-cvc")
def download_cvc():
    try:
        session_id = session.get("session_id")
        trades = get_session_trades(session_id)
        if not trades:
            return jsonify({"status": "error", "message": "No data found for this session."}), 404
        output = io.StringIO()
        if trades:
            writer = csv.DictWriter(output, fieldnames=trades[0].keys())
            writer.writeheader()
            writer.writerows(trades)
        output.seek(0)
        filename = f"CVC_DATA_{session_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Download CVC Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/admin-secure-portal")
@login_required
def admin_panel():
    trades = get_recent_trades(50)
    return render_template("admin/panel.html", trades=trades)

if __name__ == "__main__":
    if not os.path.exists(DB_PATH): init_db()
    app.run(debug=True, port=5000)
