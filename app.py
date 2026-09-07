from flask import Flask, render_template, request, jsonify
import threading
import time
from datetime import datetime

app = Flask(__name__)

# ---------- Thread-safe state ----------
state = {
    'running': False,
    'target': '',               # cleaned username (no @)
    'interval': 10,
    'countdown': 10,
    'elapsed': 0,
    'cycles': 0,
    'history': []               # list of dicts: {'time': str, 'cycle': int, 'username': str}
}
state_lock = threading.Lock()

def add_history_entry(cycle_num, username):
    """Add a completed cycle to the history (keeps last 100)."""
    now = datetime.now().strftime('%H:%M:%S')
    with state_lock:
        state['history'].insert(0, {'time': now, 'cycle': cycle_num, 'username': username})
        if len(state['history']) > 100:
            state['history'].pop()

def add_system_log(msg):
    """Optional: log system events (not shown in history)."""
    # We're not displaying system logs in UI, but keep them for debugging.
    pass

# ---------- Background timer ----------
def background_ticker():
    while True:
        time.sleep(1)
        with state_lock:
            if state['running']:
                state['elapsed'] += 1
                state['countdown'] -= 1
                if state['countdown'] <= 0:
                    state['cycles'] += 1
                    cycle_num = state['cycles']
                    target = state['target'] if state['target'] else 'unknown'
                    # Add to history (outside lock? still inside)
                    # We'll call a function that acquires lock again, but we already hold it.
                    # Better to do it inline.
                    now = datetime.now().strftime('%H:%M:%S')
                    state['history'].insert(0, {'time': now, 'cycle': cycle_num, 'username': target})
                    if len(state['history']) > 100:
                        state['history'].pop()
                    state['countdown'] = state['interval']

thread = threading.Thread(target=background_ticker, daemon=True)
thread.start()

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/state', methods=['GET'])
def get_state():
    with state_lock:
        elapsed_seconds = state['elapsed']
        hours = elapsed_seconds // 3600
        minutes = (elapsed_seconds % 3600) // 60
        seconds = elapsed_seconds % 60
        elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return jsonify({
            'running': state['running'],
            'target': state['target'],
            'interval': state['interval'],
            'countdown': state['countdown'],
            'elapsed': elapsed_str,
            'cycles': state['cycles'],
            'history': state['history'][:100]  # send all (max 100)
        })

@app.route('/start', methods=['POST'])
def start():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400
    target = data.get('target', '').strip()
    if not target:
        return jsonify({'error': 'Username is required'}), 400
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
            state['target'] = target
            state['interval'] = interval
            state['countdown'] = interval
            state['elapsed'] = 0
            state['cycles'] = 0
            state['history'] = []   # clear history on new start? Probably not, but let's keep old history? The requirement doesn't specify. I'll keep existing history; user can clear manually.
    return jsonify({'status': 'started'})

@app.route('/stop', methods=['POST'])
def stop():
    with state_lock:
        if state['running']:
            state['running'] = False
    return jsonify({'status': 'stopped'})

@app.route('/clear_history', methods=['POST'])
def clear_history():
    with state_lock:
        state['history'] = []
    return jsonify({'status': 'cleared'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
