import asyncio
import itertools
import json
import os
import platform
import socket
import ssl
import subprocess
import sys
import time
from datetime import datetime
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from colorama import Fore, Style

if getattr(sys, 'frozen', False):
    script_dir = os.path.dirname(sys.executable)
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))

config_path = os.path.join(script_dir, 'config.json')

def load_config():
    try:
        with open(config_path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default_config = {
            "monitor_settings": {
                "interval": 60,
                "timeout": 5,
                "valid_status_codes": [200, 201, 202, 204, 300, 301, 302, 303, 307, 308],
                "sorted": True
            },
            "websites": [
                "ya.ru",
                "google.com",
                "example.com",
                "vk.com",
                "youtube.com",
                "github.com",
                "store.steampowered.com",
                "steamcommunity.com",
                "t.me",
                "discord.com",
                "pikabu.ru",
                "x.com",
                "anime.reactor.cc",
                "pixiv.net"
            ],
            "Monitor": {
                "logging_enabled": False,
                "log_file_path": "monitor.log"
            }
        }
        with open(config_path, 'w', encoding='utf-8') as config_file:
            json.dump(default_config, config_file, ensure_ascii=False, indent=4)
        print(f"Файл конфигурации создан по пути: {config_path}")
        return default_config

def print_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    c = os.get_terminal_size().columns
    t = [
        Fore.CYAN + '=' * c,
        'МОНИТОРИНГ ДОСТУПНОСТИ САЙТОВ'.center(c),
        'Версия 1.1.7'.center(c),
        '=' * c + Style.RESET_ALL
    ]
    print('\n'.join(t))

def get_dns_settings():
    try:
        if platform.system() == "Windows":
            r = subprocess.run("ipconfig /all", capture_output=True, text=True, shell=True, encoding="cp866")
            d = [line.strip() for line in r.stdout.splitlines() if "DNS-серверы" in line or "DNS Servers" in line]
        else:
            r = subprocess.run(["nmcli", "dev", "show"], capture_output=True, text=True)
            d = [line.strip() for line in r.stdout.splitlines() if "IP4.DNS" in line]
        print(f"{Fore.CYAN}Текущие настройки DNS:{Style.RESET_ALL}")
        for i in d:
            print(f"{Fore.GREEN}{i}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Ошибка при получении настроек DNS: {e}{Style.RESET_ALL}")

async def measure_ping_time(domain):
    try:
        s = time.time()
        await asyncio.to_thread(socket.create_connection, (domain, 80), timeout=5)
        return round((time.time() - s) * 1000, 2)
    except Exception:
        return None

async def check_website(url, config):
    ms = config.get("monitor_settings", {})
    t = ms.get("timeout", 5)
    v = ms.get("valid_status_codes", [200])
    c = ssl.create_default_context()
    try:
        ip = await asyncio.to_thread(socket.gethostbyname, url)
    except Exception:
        return {"url": url, "ip": "N/A", "status": f"[{Fore.RED}{'N/A'.center(10)}{Style.RESET_ALL}]", "code": "DNS_ERROR"}
    try:
        async with ClientSession(connector=TCPConnector(ssl=c)) as s:
            async with s.get(f"https://{url}", timeout=ClientTimeout(total=t)) as r:
                ok = r.status in v
                co = Fore.GREEN if ok else Fore.RED
                return {
                    "url": url,
                    "ip": ip,
                    "status": f"[{co}{('ДОСТУПЕН' if ok else 'НЕДОСТУПЕН').center(10)}{Style.RESET_ALL}]",
                    "code": r.status
                }
    except asyncio.TimeoutError:
        return {
            "url": url,
            "ip": ip,
            "status": f"[{Fore.RED}{'НЕДОСТУПЕН'.center(10)}{Style.RESET_ALL}]",
            "code": "T/O"
        }
    except Exception:
        return {
            "url": url,
            "ip": ip,
            "status": f"[{Fore.RED}{'НЕДОСТУПЕН'.center(10)}{Style.RESET_ALL}]",
            "code": "ERR"
        }

async def check_internet():
    try:
        await asyncio.to_thread(socket.create_connection, ("8.8.8.8", 53), timeout=5)
        return True
    except Exception:
        return False

def check_network_interfaces():
    try:
        if platform.system() == "Windows":
            result = subprocess.run("netsh interface show interface", capture_output=True, text=True, shell=True, encoding="cp866")
            lines = result.stdout.splitlines()
            active_interfaces = [line for line in lines if "Подключен" in line or "Connected" in line]
        else:
            result = subprocess.run(["nmcli", "device", "status"], capture_output=True, text=True)
            lines = result.stdout.splitlines()
            active_interfaces = [line for line in lines if "connected" in line]
        if active_interfaces:
            print(f"{Fore.GREEN}Активные сетевые интерфейсы:{Style.RESET_ALL}")
            for interface in active_interfaces:
                print(interface)
        else:
            print(f"{Fore.RED}Нет активных сетевых интерфейсов.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Ошибка при проверке сетевых интерфейсов: {e}{Style.RESET_ALL}")

async def loading_animation():
    for char in itertools.cycle('|/-\\'):
        sys.stdout.write(f'\r{Fore.MAGENTA}Выполняется тестирование {char}...{Style.RESET_ALL}')
        sys.stdout.flush()
        await asyncio.sleep(0.2)

async def log_website_statuses(results, pings, config):
    try:
        monitor_cfg = config.get("Monitor", {})
        if monitor_cfg.get("logging_enabled", False):
            log_path = os.path.join(script_dir, monitor_cfg.get("log_file_path", "monitor.log"))
            log_data = []
            for res, ping in zip(results, pings):
                log_entry = {
                    "url": res["url"],
                    "ip": res["ip"],
                    "status": "ДОСТУПЕН" if "[\x1b[32m" in res["status"] else "НЕДОСТУПЕН",
                    "code": res["code"],
                    "ping": f"{ping:.2f} мс" if ping is not None else "N/A"
                }
                log_data.append(log_entry)
            with open(log_path, 'a', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "results": log_data
                }, f, ensure_ascii=False, indent=4)
                f.write("\n")
    except Exception as e:
        print(f"{Fore.RED}Ошибка при записи лога: {e}{Style.RESET_ALL}")

async def monitor_websites(config):
    ms = config.get("monitor_settings", {})
    w = config.get("websites", [])
    if ms.get("sorted", False):
        w = sorted(w)
    i = ms.get("interval", 60)
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_banner()
        print(f"{Fore.YELLOW}Мониторинг начался в: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}\n")
        loading_task = asyncio.create_task(loading_animation())
        try:
            tasks = [check_website(site, config) for site in w]
            results = await asyncio.gather(*tasks)
        finally:
            loading_task.cancel()
            await asyncio.sleep(0.1)
            print('\r' + ' ' * 80 + '\r')
        pt = [measure_ping_time(r["url"]) for r in results]
        pr = await asyncio.gather(*pt)
        md = max(len(r["url"]) for r in results)
        mi = max(len(r["ip"]) for r in results)
        mp = max((len(f"{p:.2f} мс") for p in pr if p is not None), default=0)
        up_count = 0
        for res, ping in zip(results, pr):
            if "[\x1b[32m" in res["status"]:
                up_count += 1
            if ping is None:
                po = f"{Fore.RED}{'N/A'.ljust(mp)}{Style.RESET_ALL}"
            else:
                if ping < 100:
                    po = f"{Fore.GREEN}{f'{ping:.2f} мс'.ljust(mp)}{Style.RESET_ALL}"
                elif ping < 300:
                    po = f"{Fore.YELLOW}{f'{ping:.2f} мс'.ljust(mp)}{Style.RESET_ALL}"
                else:
                    po = f"{Fore.RED}{f'{ping:.2f} мс'.ljust(mp)}{Style.RESET_ALL}"
            cc = Fore.YELLOW if res["code"] == "T/O" else (Fore.RED if res["code"] == "ERR" else Style.RESET_ALL)
            print(f"{res['status']} {res['url']:<{md}} -> {res['ip']:<{mi}} [Код: {cc}{res['code']}{Style.RESET_ALL} // {po}]")
        print(f"\nИтого доступно {up_count} из {len(results)} сайтов.")
        if up_count == 0:
            online = await check_internet()
            if not online:
                print(f"{Fore.RED}Вероятно, у вас нет интернет-соединения{Style.RESET_ALL}")
                check_network_interfaces()
        await log_website_statuses(results, pr, config)
        print(f"{Fore.MAGENTA}Следующая проверка начнётся через {i} секунд...{Style.RESET_ALL}\n")
        await asyncio.sleep(i)

def print_config_info(cfg):
    w = cfg.get("websites", [])
    ms = cfg.get("monitor_settings", {})
    mc = cfg.get("Monitor", {})
    s = ms.get("sorted", False)
    i = ms.get("interval", 60)
    t = ms.get("timeout", 5)
    v = ms.get("valid_status_codes", [])
    le = mc.get("logging_enabled", False)
    lp = mc.get("log_file_path", "monitor.log")
    print(f"{Fore.YELLOW}Конфигурация загружена!{Style.RESET_ALL}")
    print(f"Обработано {len(w)} сайтов.")
    print(f"Сортировка: {s}")
    print(f"Интервал проверок: {i} c.")
    print(f"Таймаут запросов: {t} c.")
    print(f"Валидные коды ответа: {v}")
    print(f"Логгирование: {le}")
    if le:
        print(f"Файл лога: {lp}")
    time.sleep(10)

def main():
    config = load_config()
    print_banner()
    print_config_info(config)
    get_dns_settings()
    try:
        asyncio.run(monitor_websites(config))
    except KeyboardInterrupt:
        print(f"{Fore.RED}Мониторинг остановлен пользователем. Завершение работы...{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
