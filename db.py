import sqlite3
from datetime import datetime
import json
import re
import os

class Database:
    def __init__(self, db_path='data/history.db', debug=True):
        self.db_path = db_path
        self.debug = debug
        self.init_db()
    
    def init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS miner_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                address TEXT NOT NULL,
                balance REAL,
                paid REAL,
                reserved REAL,
                workers_online INTEGER,
                zk_hashrate REAL,
                estimated_earnings REAL,
                share_acceptance REAL,
                total_hashrate REAL,
                nock_price REAL,
                workers TEXT,
                payouts TEXT,
                raw_data TEXT
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS hourly_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour TEXT NOT NULL,
                address TEXT NOT NULL,
                balance_change REAL,
                cumulative_from_hour_start REAL,
                avg_estimated REAL,
                avg_hashrate REAL,
                UNIQUE(hour, address)
            )
        ''')
        
        conn.commit()
        conn.close()
        if self.debug:
            print("✅ База данных инициализирована")
    
    def save_snapshot(self, data):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        balance = self._parse_number(data.get('balance'))
        paid = self._parse_number(data.get('paid'))
        reserved = self._parse_number(data.get('reserved'))
        workers_online = self._parse_int(data.get('workers_online'))
        zk_hashrate = self._parse_hashrate(data.get('zk_hashrate'))
        estimated = self._parse_estimated(data.get('estimated_earnings'))
        share = self._parse_percent(data.get('share_acceptance'))
        nock_price = data.get('nock_price')
        
        workers_json = json.dumps(data.get('workers', []), ensure_ascii=False)
        payouts_json = json.dumps(data.get('payouts', []), ensure_ascii=False)
        
        if self.debug:
            print(f"💾 Сохраняем в БД:")
            print(f"   - balance: {balance}")
            print(f"   - paid: {paid}")
            print(f"   - nock_price: {nock_price}")
            print(f"   - workers_online: {workers_online}")
            print(f"   - payouts: {len(data.get('payouts', []))} шт.")
        
        c.execute('''
            INSERT INTO miner_history (
                timestamp, address, balance, paid, reserved, 
                workers_online, zk_hashrate, estimated_earnings, 
                share_acceptance, total_hashrate, nock_price, workers, payouts, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            data.get('address'),
            balance,
            paid,
            reserved,
            workers_online,
            zk_hashrate,
            estimated,
            share,
            zk_hashrate or 0,
            nock_price,
            workers_json,
            payouts_json,
            json.dumps(data, ensure_ascii=False)
        ))
        
        conn.commit()
        conn.close()
        if self.debug:
            print("✅ Данные сохранены в БД")
    
    def get_latest(self, address):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT balance, paid, workers_online, zk_hashrate, 
                   estimated_earnings, share_acceptance, timestamp,
                   nock_price, workers, payouts
            FROM miner_history
            WHERE address = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (address,))
        
        row = c.fetchone()
        conn.close()
        
        if row:
            result = {
                'balance': row[0] if row[0] is not None else 0,
                'paid': row[1] if row[1] is not None else 0,
                'workers_online': row[2] if row[2] is not None else 0,
                'zk_hashrate': row[3] if row[3] is not None else 0,
                'estimated_earnings': row[4] if row[4] is not None else 0,
                'share_acceptance': row[5] if row[5] is not None else 0,
                'timestamp': row[6] if row[6] else datetime.now().isoformat(),
                'nock_price': row[7] if row[7] is not None else 0
            }
            
            if row[8]:
                try:
                    result['workers'] = json.loads(row[8])
                except:
                    result['workers'] = []
            else:
                result['workers'] = []
            
            if row[9]:
                try:
                    result['payouts'] = json.loads(row[9])
                except:
                    result['payouts'] = []
            else:
                result['payouts'] = []
            
            return result
        return None
    
    def get_history(self, address, hours=24):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT timestamp, balance, paid, workers_online, 
                   zk_hashrate, estimated_earnings, share_acceptance,
                   nock_price, workers, payouts
            FROM miner_history
            WHERE address = ? 
              AND datetime(timestamp) >= datetime('now', ?)
            ORDER BY timestamp ASC
        ''', (address, f'-{hours} hours'))
        
        rows = c.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            item = {
                'timestamp': row[0],
                'balance': row[1] if row[1] is not None else 0,
                'paid': row[2] if row[2] is not None else 0,
                'workers_online': row[3] if row[3] is not None else 0,
                'zk_hashrate': row[4] if row[4] is not None else 0,
                'estimated_earnings': row[5] if row[5] is not None else 0,
                'share_acceptance': row[6] if row[6] is not None else 0,
                'nock_price': row[7] if row[7] is not None else 0
            }
            if row[8]:
                try:
                    item['workers'] = json.loads(row[8])
                except:
                    item['workers'] = []
            else:
                item['workers'] = []
            if row[9]:
                try:
                    item['payouts'] = json.loads(row[9])
                except:
                    item['payouts'] = []
            else:
                item['payouts'] = []
            result.append(item)
        
        return result
    
    def get_hourly_stats(self, address, hours=24):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT hour, balance_change, cumulative_from_hour_start, avg_estimated, avg_hashrate
            FROM hourly_stats
            WHERE address = ?
              AND datetime(hour) >= datetime('now', ?)
            ORDER BY hour ASC
        ''', (address, f'-{hours} hours'))
        
        rows = c.fetchall()
        conn.close()
        
        return [
            {
                'hour': row[0],
                'balance_change': row[1] if row[1] is not None else 0,
                'cumulative_from_hour_start': row[2] if row[2] is not None else 0,
                'avg_estimated': row[3] if row[3] is not None else 0,
                'avg_hashrate': row[4] if row[4] is not None else 0
            }
            for row in rows
        ]
    
    def calculate_hourly_stats(self, address):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                MIN(balance) as min_balance,
                MAX(balance) as max_balance,
                MIN(balance) as first_balance,
                MAX(balance) as last_balance,
                AVG(estimated_earnings) as avg_estimated,
                AVG(zk_hashrate) as avg_hashrate
            FROM miner_history
            WHERE address = ?
              AND datetime(timestamp) >= datetime('now', '-25 hours')
            GROUP BY hour
            ORDER BY hour ASC
        ''', (address,))
        
        for row in c.fetchall():
            hour = row[0]
            first_balance = row[3] or 0
            last_balance = row[4] or 0
            avg_estimated = row[5] or 0
            avg_hashrate = row[6] or 0
            
            balance_change = last_balance - first_balance
            cumulative_from_hour_start = (row[2] or 0) - first_balance
            
            c.execute('''
                INSERT OR REPLACE INTO hourly_stats 
                    (hour, address, balance_change, cumulative_from_hour_start, avg_estimated, avg_hashrate)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (hour, address, balance_change, cumulative_from_hour_start, avg_estimated, avg_hashrate))
        
        conn.commit()
        conn.close()
        if self.debug:
            print("✅ Почасовая статистика обновлена")
    
    def clear_database(self, address=None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if address:
            c.execute("DELETE FROM miner_history WHERE address = ?", (address,))
            c.execute("DELETE FROM hourly_stats WHERE address = ?", (address,))
        else:
            c.execute("DELETE FROM miner_history")
            c.execute("DELETE FROM hourly_stats")
        
        conn.commit()
        conn.close()
        print("✅ База данных очищена")
    
    def _parse_number(self, text):
        if not text:
            return None
        clean = str(text).replace(' ', '').replace(',', '.').replace('NOCK', '').strip()
        clean = re.sub(r'[^\d.\-]', '', clean)
        try:
            return float(clean)
        except:
            match = re.search(r'(\d+[\d.]*)', str(text).replace(',', '.'))
            return float(match.group(1)) if match else None
    
    def _parse_int(self, text):
        if not text:
            return 0
        clean = re.sub(r'[^\d]', '', str(text))
        return int(clean) if clean else 0
    
    def _parse_hashrate(self, text):
        if not text:
            return None
        clean = text.replace(' ', '').replace(',', '.')
        if 'тыс' in clean:
            clean = clean.replace('тыс.proof/s', '').strip()
            return float(clean) * 1000
        elif 'k' in clean:
            clean = clean.replace('kproof/s', '').strip()
            return float(clean) * 1000
        elif 'млн' in clean:
            clean = clean.replace('млнproof/s', '').strip()
            return float(clean) * 1000000
        else:
            clean = clean.replace('proof/s', '').strip()
            return float(clean) if clean else None
    
    def _parse_estimated(self, text):
        if not text:
            return None
        clean = text.replace(' ', '').replace('$', '').replace('/day', '').replace(',', '.')
        clean = re.sub(r'[^\d.]', '', clean)
        return float(clean) if clean else None
    
    def _parse_percent(self, text):
        if not text:
            return None
        clean = text.replace(' ', '').replace('%', '').replace(',', '.')
        clean = re.sub(r'[^\d.]', '', clean)
        return float(clean) if clean else None

if __name__ == "__main__":
    db = Database(debug=True)
    print("✅ База данных готова к работе")