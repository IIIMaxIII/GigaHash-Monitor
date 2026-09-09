import subprocess
import time
import os
import signal
import sys
import psutil
from datetime import datetime
import threading
import atexit
import shutil

class ProcessManager:
    def __init__(self):
        self.processes = {}
        self.running = True
        self.monitor_interval = 10
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.script_dir, 'data')
        self.db_path = os.path.join(self.data_dir, 'history.db')
        
        atexit.register(self.cleanup)
    
    def cleanup(self):
        self.stop_all()
    
    def find_process_by_script(self, script_name):
        """Находит процесс по имени скрипта"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if script_name in cmdline and 'python' in cmdline:
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None
    
    def clear_database(self):
        """Полностью удаляет базу данных"""
        print("\n🗑️ Очистка базы данных...")
        print("-" * 40)
        
        # Проверяем существование
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                print(f"✅ Удален файл: {self.db_path}")
            except Exception as e:
                print(f"❌ Ошибка удаления: {e}")
                return False
        else:
            print(f"ℹ️ Файл БД не найден: {self.db_path}")
        
        # Проверяем папку data
        if os.path.exists(self.data_dir):
            try:
                # Проверяем, есть ли ещё файлы в папке
                files = os.listdir(self.data_dir)
                if files:
                    print(f"📁 В папке data остались файлы: {files}")
                else:
                    print(f"📁 Папка data пуста")
            except Exception as e:
                print(f"⚠️ Ошибка проверки папки: {e}")
        
        print("✅ Очистка БД завершена")
        return True
    
    def stop_all(self):
        """Останавливает все процессы"""
        print("\n" + "=" * 50)
        print("🛑 Остановка всех процессов...")
        
        # Останавливаем через менеджер
        for name in list(self.processes.keys()):
            self.stop_process(name)
        
        # Ищем и убиваем зависшие процессы
        print("\n🔍 Поиск зависших процессов...")
        for script in ['monitor.py', 'dashboard.py']:
            proc = self.find_process_by_script(script)
            if proc:
                try:
                    print(f"  🧹 Убиваем {script} (PID: {proc.pid})")
                    proc.kill()
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  ⚠️ Ошибка убийства {script}: {e}")
            else:
                print(f"  ✅ {script} не найден")
        
        # Дополнительная очистка для Windows
        if sys.platform == 'win32':
            try:
                subprocess.run(['taskkill', '/F', '/FI', 'WINDOWTITLE eq monitor*'], 
                             capture_output=True, timeout=5)
                subprocess.run(['taskkill', '/F', '/FI', 'WINDOWTITLE eq dashboard*'], 
                             capture_output=True, timeout=5)
            except:
                pass
        
        self.processes.clear()
        print("\n✅ Все процессы остановлены")
    
    def stop_process(self, name):
        """Останавливает процесс"""
        if name in self.processes:
            process_info = self.processes[name]
            pid = process_info.get('pid', process_info['process'].pid)
            
            try:
                print(f"  🛑 Остановка {name} (PID: {pid})...")
                
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    time.sleep(2)
                    if proc.is_running():
                        proc.kill()
                except:
                    pass
                
                if sys.platform == 'win32':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], 
                                 capture_output=True, timeout=5)
                
                del self.processes[name]
                print(f"  ✅ {name} остановлен")
                return True
                
            except Exception as e:
                print(f"  ⚠️ Ошибка остановки {name}: {e}")
                return False
        return False
    
    def start_process(self, name, script, args=[]):
        """Запускает процесс"""
        try:
            print(f"  🚀 Запуск {name}...")
            
            script_path = os.path.join(self.script_dir, script)
            
            if not os.path.exists(script_path):
                print(f"  ❌ Файл {script_path} не найден!")
                return False
            
            existing = self.find_process_by_script(script)
            if existing:
                print(f"  ⚠️ {name} уже запущен (PID: {existing.pid})")
                return True
            
            if sys.platform == 'win32':
                process = subprocess.Popen(
                    ['python', script_path] + args,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    cwd=self.script_dir
                )
            else:
                process = subprocess.Popen(
                    ['python3', script_path] + args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=self.script_dir,
                    start_new_session=True
                )
            
            time.sleep(2)
            
            if process.poll() is None:
                self.processes[name] = {
                    'process': process,
                    'script': script,
                    'args': args,
                    'start_time': datetime.now(),
                    'restarts': 0,
                    'pid': process.pid
                }
                print(f"  ✅ {name} запущен (PID: {process.pid})")
                return True
            else:
                print(f"  ❌ {name} не запустился (код: {process.returncode})")
                return False
            
        except Exception as e:
            print(f"  ❌ Ошибка запуска {name}: {e}")
            return False
    
    def run(self):
        """Запускает монитор и дашборд"""
        print("\n" + "=" * 50)
        print("⚡ GigaHash Monitor Manager")
        print("=" * 50)
        print(f"🕐 Запуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📁 Папка: {self.script_dir}")
        print("=" * 50)
        
        if not os.path.exists(os.path.join(self.script_dir, 'monitor.py')):
            print("❌ monitor.py не найден!")
        if not os.path.exists(os.path.join(self.script_dir, 'dashboard.py')):
            print("❌ dashboard.py не найден!")
        
        print("\n🚀 Запуск процессов...")
        
        success1 = self.start_process('monitor', 'monitor.py')
        time.sleep(2)
        
        success2 = self.start_process('dashboard', 'dashboard.py')
        
        print("\n" + "=" * 50)
        if success1 and success2:
            print("✅ Все процессы запущены")
        else:
            print("⚠️ Некоторые процессы не запустились")
        print("📊 Дашборд: http://localhost:5000")
        print("=" * 50 + "\n")

def show_menu():
    print("\n" + "=" * 50)
    print("⚡ GigaHash Monitor Manager")
    print("=" * 50)
    print("1. 🚀 Запустить все процессы")
    print("2. 🛑 Остановить все процессы")
    print("3. 🔄 Перезапустить все процессы")
    print("4. 📊 Статус процессов")
    print("5. 🧹 Очистить БД и перезапустить")
    print("6. ❌ Выход")
    print("=" * 50)

def main():
    manager = ProcessManager()
    
    # Обработка аргументов командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == 'stop':
            manager.stop_all()
            return
        elif sys.argv[1] == 'restart':
            manager.stop_all()
            time.sleep(2)
            manager.run()
            return
        elif sys.argv[1] == 'status':
            print("\n📊 Статус процессов:")
            print("=" * 40)
            for script in ['monitor.py', 'dashboard.py']:
                proc = manager.find_process_by_script(script)
                if proc:
                    print(f"✅ {script} работает (PID: {proc.pid})")
                else:
                    print(f"❌ {script} не запущен")
            print("=" * 40)
            return
        elif sys.argv[1] == 'start':
            manager.run()
            return
        elif sys.argv[1] == 'clear':
            manager.stop_all()
            time.sleep(2)
            manager.clear_database()
            time.sleep(1)
            manager.run()
            return
    
    # Интерактивное меню
    while True:
        show_menu()
        choice = input("\nВыберите действие (1-6): ").strip()
        
        if choice == '1':
            manager.run()
            input("\nНажмите Enter для продолжения...")
        
        elif choice == '2':
            manager.stop_all()
            input("\nНажмите Enter для продолжения...")
        
        elif choice == '3':
            print("\n🔄 Перезапуск...")
            manager.stop_all()
            time.sleep(2)
            manager.run()
            input("\nНажмите Enter для продолжения...")
        
        elif choice == '4':
            print("\n📊 Статус процессов:")
            print("=" * 40)
            for script in ['monitor.py', 'dashboard.py']:
                proc = manager.find_process_by_script(script)
                if proc:
                    print(f"✅ {script} работает (PID: {proc.pid})")
                else:
                    print(f"❌ {script} не запущен")
            print("=" * 40)
            input("\nНажмите Enter для продолжения...")
        
        elif choice == '5':
            print("\n" + "=" * 50)
            print("🧹 ОЧИСТКА БД И ПЕРЕЗАПУСК")
            print("=" * 50)
            
            # 1. Останавливаем процессы
            manager.stop_all()
            time.sleep(2)
            
            # 2. Очищаем БД
            manager.clear_database()
            time.sleep(1)
            
            # 3. Запускаем заново
            print("\n🚀 Запуск процессов...")
            manager.run()
            
            input("\nНажмите Enter для продолжения...")
        
        elif choice == '6':
            manager.stop_all()
            print("\n👋 До свидания!")
            break
        
        else:
            print("\n❌ Неверный выбор. Попробуйте снова.")
            time.sleep(1)

if __name__ == "__main__":
    main()