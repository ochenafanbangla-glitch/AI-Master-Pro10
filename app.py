from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/")
def index():
    return "AI Master Pro 10 - Minimal Test"

@app.route("/health")
def health():
    return jsonify({"status": "ok", "env": "minimal"})

if __name__ == "__main__":
    app.run(port=5000)
