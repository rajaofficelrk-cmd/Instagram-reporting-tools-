from flask import Flask, render_template, request, jsonify
import threading
import time
from datetime import datetime

app = Flask(__name__)

# ---------- Global state (thread‑safe) ----------
state = {
    'running': False,
    'interval': 10,          # seconds between reports
    'countdown': 10,
    'counter': 0,
    'logs': []               # list of dicts: {'time': str, 'msg': str}
}
state_lock = threading.Lock()

def add_log(msg):
    """Add a log entry with current timestamp."""
    now = datetime.now().strftime('%H:%M:%S')
    with state_lock:
        state['logs'].append({'time': now, 'msg': msg})
        if len(state['logs']) > 100:   # keep last 100
            state['logs'].pop(0)

def perform_report():
    """Simulate sending a report (just increments counter and logs)."""
    with state_lock:
        state['counter'] += 1
    add_log(f"📩 Report sent for @{request.form.get('username', 'unknown')}" if request else "📩 Report sent")
    # Note: request context not available in background thread – we'll pass username via state
    # We'll handle username in the ticker by reading from global, but it's simpler to just log generic.

# ---------- Background timer thread ----------
def ticker():
    """Runs every second and manages countdown / reports."""
    while True:
        time.sleep(1)
        with state_lock:
            if state['running']:
                state['countdown'] -= 1
                if state['countdown'] <= 0:
                    # Perform a simulated report
                    state['counter'] += 1
                    state['countdown'] = state['interval']
                    # Log with the current username (stored separately)
                    username = state.get('username', 'unknown')
                    add_log(f"📩 Simulated report sent for @{username}")
                    # Reset countdown to interval

# Start the background thread (daemon so it exits with the app)
thread = threading.Thread(target=ticker, daemon=True)
thread.start()

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/state', methods=['GET'])
def get_state():
    """Return current state as JSON."""
    with state_lock:
        return jsonify({
            'running': state['running'],
            'interval': state['interval'],
            'countdown': state['countdown'],
            'counter': state['counter'],
            'logs': state['logs'][-50:]   # send last 50
        })

@app.route('/start', methods=['POST'])
def start():
    """Start the reporting cycle."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400
    username = data.get('username', 'unknown')
    interval = data.get('interval', 10)
    try:
        interval = int(interval)
        if interval < 1:
            interval = 1
    except:
        interval = 10
    with state_lock:
        if not state['running']:
            state['running'] = True
            state['interval'] = interval
            state['countdown'] = interval
            state['username'] = username
            add_log(f"▶ Reporting started for @{username} (interval: {interval}s)")
    return jsonify({'status': 'started'})

@app.route('/stop', methods=['POST'])
def stop():
    """Stop the reporting cycle."""
    with state_lock:
        if state['running']:
            state['running'] = False
            add_log("⏹ Reporting stopped")
    return jsonify({'status': 'stopped'})

@app.route('/set_interval', methods=['POST'])
def set_interval():
    """Change interval (only if not running)."""
    data = request.get_json()
    interval = data.get('interval', 10)
    try:
        interval = int(interval)
        if interval < 1:
            interval = 1
    except:
        interval = 10
    with state_lock:
        # Only allow if not running, or we could allow while running
        if not state['running']:
            state['interval'] = interval
            state['countdown'] = interval
        else:
            # Optionally update interval without resetting countdown
            state['interval'] = interval
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
