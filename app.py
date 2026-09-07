from flask import Flask, render_template, request, jsonify
import threading
import time
from datetime import datetime

app = Flask(__name__)

# ---------- Thread-safe state ----------
state = {
    'running': False,
    'target': '',
    'interval': 10,
    'countdown': 10,
    'elapsed': 0,
    'cycles': 0,
    'logs': []
}
state_lock = threading.Lock()

def add_log(msg):
    now = datetime.now().strftime('%H:%M:%S')
    with state_lock:
        state['logs'].append({'time': now, 'msg': msg})
        if len(state['logs']) > 100:
            state['logs'].pop(0)

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
                    add_log(f"Cycle #{cycle_num} for @{target} (simulated)")
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
            'logs': state['logs'][-50:]
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
            add_log(f"▶ Started for @{target} (interval: {interval}s)")
    return jsonify({'status': 'started'})

@app.route('/stop', methods=['POST'])
def stop():
    with state_lock:
        if state['running']:
            state['running'] = False
            add_log("⏹ Stopped")
    return jsonify({'status': 'stopped'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
