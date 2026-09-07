import os
import requests
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, jsonify, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # change in production

# ---------- OAuth Config ----------
APP_ID = os.getenv('INSTAGRAM_APP_ID')
APP_SECRET = os.getenv('INSTAGRAM_APP_SECRET')
REDIRECT_URI = os.getenv('INSTAGRAM_REDIRECT_URI')
AUTH_URL = 'https://api.instagram.com/oauth/authorize'
TOKEN_URL = 'https://api.instagram.com/oauth/access_token'
GRAPH_URL = 'https://graph.instagram.com'

# ---------- Global State (thread-safe) ----------
state = {
    'running': False,
    'interval': 10,
    'countdown': 10,
    'elapsed': 0,
    'cycles': 0,
    'media': [],
    'logs': []
}
state_lock = threading.Lock()

def add_log(msg):
    now = datetime.now().strftime('%H:%M:%S')
    with state_lock:
        state['logs'].insert(0, {'time': now, 'msg': msg})
        if len(state['logs']) > 100:
            state['logs'].pop()

def fetch_media(access_token):
    """Fetch recent media using Instagram Graph API."""
    url = f'{GRAPH_URL}/me/media'
    params = {
        'fields': 'id,caption,media_type,media_url,permalink,timestamp',
        'access_token': access_token,
        'limit': 20
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get('data', [])
    except Exception as e:
        add_log(f"API error: {str(e)}")
        return []

def background_ticker():
    """Background thread: update countdown, cycles, and fetch media."""
    while True:
        time.sleep(1)
        with state_lock:
            if state['running']:
                state['elapsed'] += 1
                state['countdown'] -= 1
                if state['countdown'] <= 0:
                    state['cycles'] += 1
                    state['countdown'] = state['interval']
                    # Fetch media (only if we have token)
                    token = session.get('access_token', None)
                    if token:
                        media = fetch_media(token)
                        state['media'] = media
                        add_log(f"Fetched {len(media)} items (cycle #{state['cycles']})")
                    else:
                        add_log("No access token – skipping fetch")
                    # Reset countdown

thread = threading.Thread(target=background_ticker, daemon=True)
thread.start()

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    # Redirect to Instagram OAuth
    params = {
        'client_id': APP_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'user_profile,user_media',
        'response_type': 'code'
    }
    url = f"{AUTH_URL}?{requests.compat.urlencode(params)}"
    return redirect(url)

@app.route('/oauth/callback')
def oauth_callback():
    code = request.args.get('code')
    if not code:
        return "Missing code", 400

    # Exchange code for token
    data = {
        'client_id': APP_ID,
        'client_secret': APP_SECRET,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI,
        'code': code
    }
    resp = requests.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        return f"Token exchange failed: {resp.text}", 400

    token_data = resp.json()
    session['access_token'] = token_data['access_token']
    session['user_id'] = token_data['user_id']
    add_log(f"Logged in with user ID: {token_data['user_id']}")
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    add_log("Logged out")
    return redirect('/')

@app.route('/state', methods=['GET'])
def get_state():
    with state_lock:
        elapsed_seconds = state['elapsed']
        hours = elapsed_seconds // 3600
        minutes = (elapsed_seconds % 3600) // 60
        seconds = elapsed_seconds % 60
        elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Get user info (optional)
        user_info = {}
        token = session.get('access_token')
        if token:
            try:
                resp = requests.get(f'{GRAPH_URL}/me', params={'access_token': token})
                if resp.status_code == 200:
                    user_info = resp.json()
            except:
                pass

        return jsonify({
            'running': state['running'],
            'interval': state['interval'],
            'countdown': state['countdown'],
            'elapsed': elapsed_str,
            'cycles': state['cycles'],
            'media': state['media'],
            'logs': state['logs'][:50],
            'user': user_info,
            'authenticated': bool(token)
        })

@app.route('/start', methods=['POST'])
def start():
    if not session.get('access_token'):
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
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
            state['elapsed'] = 0
            state['cycles'] = 0
            # Initial fetch
            token = session.get('access_token')
            if token:
                state['media'] = fetch_media(token)
                add_log("Started polling")
    return jsonify({'status': 'started'})

@app.route('/stop', methods=['POST'])
def stop():
    with state_lock:
        if state['running']:
            state['running'] = False
            add_log("Stopped polling")
    return jsonify({'status': 'stopped'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
