from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
import time
from db import Database
import schedule
import threading
import os

class MinerMonitor:
    def __init__(self, address=None, db_path='data/history.db', debug=True):
        # Если адрес не передан, читаем из файла
        if address is None:
            address = self._load_address()
        self.address = address
        self.db = Database(db_path, debug=debug)
        self.debug = debug
    
    def _load_address(self):
        """Загружает адрес из файла ghm_wallet.json"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'ghm_wallet.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                address = config.get('address')
                if address:
                    print(f"📂 Загружен адрес из ghm_wallet.json: {address[:20]}...")
                    return address
                else:
                    raise ValueError("В файле ghm_wallet.json не найден 'address'")
        except FileNotFoundError:
            print("❌ Файл ghm_wallet.json не найден!")
            print("   Создайте файл со структурой: {\"address\": \"ваш_адрес\"}")
            raise
        except Exception as e:
            print(f"❌ Ошибка чтения ghm_wallet.json: {e}")
            raise
    
    def fetch_nock_price(self):
        """Парсит цену NOCK с главной страницы"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.get("https://gigahash.cloud")
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            driver.quit()
            
            price_elem = soup.find('strong', {'id': 'nock-price'})
            if price_elem:
                price_text = price_elem.text.strip()
                match = re.search(r'([\d,]+)', price_text)
                if match:
                    price = float(match.group(1).replace(',', '.'))
                    if self.debug:
                        print(f"💲 Цена NOCK: ${price}")
                    return price
            
            price_match = re.search(r'NOCK price.*?([\d,]+)\s*\$', driver.page_source)
            if price_match:
                price = float(price_match.group(1).replace(',', '.'))
                if self.debug:
                    print(f"💲 Цена NOCK: ${price}")
                return price
                
        except Exception as e:
            if self.debug:
                print(f"⚠️ Ошибка парсинга цены: {e}")
        
        return None
    
    def parse_data(self):
        """Парсит данные с сайта"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            url = f"https://gigahash.cloud/account?miner={self.address}"
            driver.get(url)
            
            wait = WebDriverWait(driver, 15)
            wait.until(EC.presence_of_element_located((By.ID, "miner-result")))
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            data = {
                'address': self.address,
                'timestamp': datetime.now().isoformat(),
                'balance': None,
                'reserved': None,
                'paid': None,
                'workers_online': None,
                'zk_hashrate': None,
                'ai_hashrate': None,
                'estimated_earnings': None,
                'share_acceptance': None,
                'nock_price': None,
                'workers': [],
                'payouts': []
            }
            
            # Парсим miner-metrics
            metrics_section = soup.find('div', class_='miner-metrics')
            if metrics_section:
                if self.debug:
                    print("✅ Найдена секция miner-metrics")
                
                articles = metrics_section.find_all('article')
                for article in articles:
                    p_tag = article.find('p')
                    if not p_tag:
                        continue
                    label = p_tag.text.strip()
                    strong = article.find('strong')
                    if not strong:
                        continue
                    value = strong.text.strip()
                    
                    if 'Available balance' in label:
                        data['balance'] = value
                        if self.debug:
                            print(f"💰 Баланс: {data['balance']}")
                    elif 'Reserved' in label:
                        data['reserved'] = value
                        if self.debug:
                            print(f"📌 Зарезервировано: {data['reserved']}")
                    elif 'Paid' in label:
                        data['paid'] = value
                        if self.debug:
                            print(f"💳 ВСЕГО ВЫПЛАЧЕНО: {data['paid']}")
                    elif 'Workers online' in label:
                        data['workers_online'] = value
                        if self.debug:
                            print(f"👷 Онлайн воркеры: {data['workers_online']}")
            else:
                if self.debug:
                    print("❌ Секция miner-metrics не найдена")
            
            # Парсим хешрейты
            hashrates_section = soup.find('div', class_='miner-hashrates')
            if hashrates_section:
                for div in hashrates_section.find_all('div'):
                    span = div.find('span')
                    strong = div.find('strong')
                    if span and strong:
                        label = span.text.strip()
                        value = strong.text.strip()
                        if 'ZK hashrate' in label:
                            data['zk_hashrate'] = value
                            if self.debug:
                                print(f"⚡ ZK Хешрейт: {data['zk_hashrate']}")
                        elif 'Estimated' in label:
                            data['estimated_earnings'] = value
                            if self.debug:
                                print(f"💵 Расчетный доход: {data['estimated_earnings']}")
                        elif 'Share acceptance' in label:
                            data['share_acceptance'] = value
                            if self.debug:
                                print(f"📊 Принято шаров: {data['share_acceptance']}")
            
            # Парсим воркеров
            worker_cards = soup.find_all('article', class_=re.compile(r'worker-card'))
            for card in worker_cards:
                name_tag = card.find('strong')
                if not name_tag:
                    continue
                name = name_tag.text.strip()
                if name.lower() in ['workers', 'worker', 'online', 'offline']:
                    continue
                
                worker = {'name': name, 'id': None, 'hashrate': None, 'earnings': None, 'gpus': None, 'uptime': None, 'status': None}
                
                id_span = card.find('span', string=re.compile(r'ID'))
                if id_span:
                    worker['id'] = id_span.text.split('ID ')[-1].strip()
                
                summary = card.find('div', class_='worker-summary')
                if summary:
                    for div in summary.find_all('div'):
                        span = div.find('span')
                        strong = div.find('strong')
                        if span and strong:
                            text = span.text.strip()
                            if text == 'Worker hashrate':
                                worker['hashrate'] = strong.text.strip()
                            elif text == 'Estimated':
                                worker['earnings'] = strong.text.strip()
                            elif text == 'GPUs online':
                                worker['gpus'] = strong.text.strip()
                            elif text == 'Online / Uptime':
                                worker['uptime'] = strong.text.strip()
                
                status_tag = card.find('b', class_='worker-state')
                if status_tag:
                    worker['status'] = status_tag.text.strip()
                data['workers'].append(worker)
            
            # Парсим выплаты
            payout_section = soup.find('section', class_=re.compile(r'account-payout'))
            if payout_section:
                table = payout_section.find('table')
                if table:
                    for row in table.find_all('tr')[1:]:
                        cols = row.find_all('td')
                        if len(cols) >= 6:
                            batch = cols[0].text.strip() if cols[0] else None
                            if batch and batch not in ['Batch', '']:
                                data['payouts'].append({
                                    'batch': batch,
                                    'status': cols[1].text.strip() if len(cols) > 1 else None,
                                    'amount': cols[2].text.strip() if len(cols) > 2 else None,
                                    'fee': cols[3].text.strip() if len(cols) > 3 else None,
                                    'transaction': cols[4].text.strip() if len(cols) > 4 else None,
                                    'updated': cols[5].text.strip() if len(cols) > 5 else None
                                })
            
            # Парсим цену NOCK
            nock_price = self.fetch_nock_price()
            if nock_price:
                data['nock_price'] = nock_price
            
            if self.debug:
                print(f"\n📊 ИТОГО:")
                print(f"   - Баланс: {data.get('balance', 'N/A')}")
                print(f"   - Выплачено: {data.get('paid', 'N/A')}")
                print(f"   - Цена NOCK: ${data.get('nock_price', 'N/A')}")
                print(f"   - Воркеров: {len(data.get('workers', []))}")
                print(f"   - Выплат: {len(data.get('payouts', []))}")
            
            return data
            
        finally:
            driver.quit()
    
    def collect_and_save(self):
        """Собирает данные и сохраняет в БД"""
        if self.debug:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Сбор данных...")
            print("-" * 40)
        
        try:
            data = self.parse_data()
            
            if not data or not data.get('balance'):
                print("❌ Ошибка: данные не получены")
                return
            
            self.db.save_snapshot(data)
            self.db.calculate_hourly_stats(self.address)
            
            if self.debug:
                print(f"✅ Данные сохранены")
                print(f"   - Баланс: {data.get('balance', 'N/A')}")
                print(f"   - Выплачено: {data.get('paid', 'N/A')}")
                print(f"   - Воркеров: {len(data.get('workers', []))}")
                print(f"   - Выплат: {len(data.get('payouts', []))}")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
        if self.debug:
            print("-" * 40)
    
    def run_forever(self, interval_minutes=5):
        """Запускает бесконечный сбор данных"""
        print(f"🚀 Запуск мониторинга. Интервал: {interval_minutes} минут")
        print(f"📊 Адрес: {self.address[:20]}...{self.address[-10:]}")
        print("=" * 50)
        
        self.collect_and_save()
        
        schedule.every(interval_minutes).minutes.do(self.collect_and_save)
        
        while True:
            schedule.run_pending()
            time.sleep(30)

if __name__ == "__main__":
    monitor = MinerMonitor(debug=True)
    monitor.run_forever(interval_minutes=5)