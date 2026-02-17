from flask import Flask, jsonify
import os
import sys

app = Flask(__name__)

@app.route("/")
def index():
    return "AI Master Pro 10 - Debugging"

@app.route("/health")
def health():
    return jsonify({
        "status": "ok", 
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "files": os.listdir('.')
    })

if __name__ == "__main__":
    app.run(port=5000)
