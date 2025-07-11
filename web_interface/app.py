#!/usr/bin/env python3
"""
Flask Web Interface for ArcGIS Solution Cloner
==============================================
Simple web interface to collect credentials and execute the cloning process.
"""

import os
import sys
import subprocess
import threading
import queue
import json
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response

# Add parent directory to path to import solution_cloner
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Global variables for process management
current_process = None
output_queue = queue.Queue()
process_status = {"running": False, "output": [], "error": None}


def run_cloner(env_vars):
    """Run the solution cloner in a separate thread."""
    global current_process, process_status
    
    try:
        # Clear previous output
        process_status["output"] = []
        process_status["error"] = None
        process_status["running"] = True
        
        # Set up environment
        env = os.environ.copy()
        env.update(env_vars)
        
        # Run the cloner module
        current_process = subprocess.Popen(
            [sys.executable, '-m', 'solution_cloner.solution_cloner'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output
        for line in iter(current_process.stdout.readline, ''):
            if line:
                output_queue.put(line.strip())
                process_status["output"].append(line.strip())
        
        current_process.wait()
        
        if current_process.returncode != 0:
            process_status["error"] = f"Process exited with code {current_process.returncode}"
            
    except Exception as e:
        process_status["error"] = str(e)
        output_queue.put(f"Error: {str(e)}")
    finally:
        process_status["running"] = False
        current_process = None


@app.route('/')
def index():
    """Render the main form page."""
    return render_template('index.html')


@app.route('/clone', methods=['POST'])
def start_clone():
    """Start the cloning process with provided credentials."""
    global process_status
    
    try:
        # Check if already running
        if process_status["running"]:
            return jsonify({"error": "A cloning process is already running"}), 400
        
        # Get form data
        data = request.json
        print(f"Received clone request with data keys: {list(data.keys())}")
        
        # Validate required fields
        required_fields = [
            'source_url', 'source_username', 'source_password', 'source_folder',
            'dest_url', 'dest_username', 'dest_password', 'dest_folder'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400
    except Exception as e:
        print(f"Error in start_clone: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    
    # Create environment variables
    env_vars = {
        'SOURCE_URL': data['source_url'],
        'SOURCE_USERNAME': data['source_username'],
        'SOURCE_PASSWORD': data['source_password'],
        'SOURCE_FOLDER': data['source_folder'],
        'DEST_URL': data['dest_url'],
        'DEST_USERNAME': data['dest_username'],
        'DEST_PASSWORD': data['dest_password'],
        'DEST_FOLDER': data['dest_folder']
    }
    
    # Start cloning in background thread
    thread = threading.Thread(target=run_cloner, args=(env_vars,))
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "Cloning process started"})


@app.route('/status')
def get_status():
    """Get the current status of the cloning process."""
    return jsonify({
        "running": process_status["running"],
        "output_length": len(process_status["output"]),
        "error": process_status["error"]
    })


@app.route('/output')
def stream_output():
    """Stream output from the cloning process."""
    def generate():
        while True:
            try:
                # Get output with timeout
                line = output_queue.get(timeout=1)
                yield f"data: {json.dumps({'line': line})}\n\n"
            except queue.Empty:
                # Send heartbeat to keep connection alive
                if process_status["running"]:
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                else:
                    # Process finished
                    yield f"data: {json.dumps({'finished': True, 'error': process_status['error']})}\n\n"
                    break
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/stop', methods=['POST'])
def stop_clone():
    """Stop the current cloning process."""
    global current_process
    
    if current_process and process_status["running"]:
        current_process.terminate()
        return jsonify({"success": True, "message": "Process terminated"})
    else:
        return jsonify({"error": "No process is running"}), 400


@app.route('/logs')
def get_logs():
    """Get the full output log."""
    return jsonify({
        "logs": process_status["output"],
        "error": process_status["error"]
    })


@app.route('/health')
def health_check():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "healthy", "service": "arcgis-solution-cloner"}), 200


if __name__ == '__main__':
    # Run in debug mode for development
    # Added threaded=True to handle concurrent requests properly
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=port, threaded=True)