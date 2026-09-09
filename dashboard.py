from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from db import Database
from datetime import datetime, timedelta
import threading
import time
from monitor import MinerMonitor
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Загружаем адрес из файла
def load_address():
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'ghm_wallet.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('address')
    except:
        return None

ADDRESS = load_address()
if not ADDRESS:
    print("❌ Не удалось загрузить адрес из ghm_wallet.json")
    ADDRESS = ""

DB_PATH = 'data/history.db'
db = Database(DB_PATH, debug=False)

# Запускаем монитор в отдельном потоке
def start_monitor():
    monitor = MinerMonitor(ADDRESS, DB_PATH, debug=True)
    monitor.run_forever(interval_minutes=5)

monitor_thread = threading.Thread(target=start_monitor, daemon=True)
monitor_thread.start()

@app.route('/')
def dashboard():
    return render_template('dashboard.html', address=ADDRESS)

@app.route('/api/latest')
def get_latest():
    data = db.get_latest(ADDRESS)
    if data:
        return jsonify({'status': 'success', 'data': data})
    return jsonify({'status': 'error', 'message': 'No data'})

@app.route('/api/history/<int:hours>')
def get_history(hours=24):
    return jsonify({'status': 'success', 'data': db.get_history(ADDRESS, hours)})

@app.route('/api/hourly/<int:hours>')
def get_hourly(hours=24):
    return jsonify({'status': 'success', 'data': db.get_hourly_stats(ADDRESS, hours)})

@app.route('/api/price')
def get_price():
    data = db.get_latest(ADDRESS)
    if data and data.get('nock_price'):
        return jsonify({'status': 'success', 'price': data['nock_price']})
    return jsonify({'status': 'error', 'price': 0})

@socketio.on('connect')
def handle_connect():
    print('📡 Клиент подключен')
    data = db.get_latest(ADDRESS)
    if data:
        emit('update', data)

def send_updates():
    while True:
        time.sleep(30)
        data = db.get_latest(ADDRESS)
        if data:
            socketio.emit('update', data)

update_thread = threading.Thread(target=send_updates, daemon=True)
update_thread.start()

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)