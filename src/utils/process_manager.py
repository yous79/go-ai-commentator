import os
import signal
import subprocess
import time
import psutil

def kill_process_on_port(port):
    """指定されたポートを使用しているプロセスを強制終了する"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections(kind='inet'):
                if conn.laddr.port == port:
                    print(f"Cleaning up process {proc.info['name']} (PID: {proc.info['pid']}) on port {port}")
                    proc.send_signal(signal.SIGTERM)
                    time.sleep(0.5)
                    if proc.is_running():
                        proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def kill_legacy_katago():
    """残存している KataGo プロセスを掃除する"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if "katago" in proc.info['name'].lower():
                print(f"Cleaning up legacy KataGo process (PID: {proc.info['pid']})")
                proc.kill()
        except:
            pass
