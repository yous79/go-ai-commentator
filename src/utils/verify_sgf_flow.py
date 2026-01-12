import subprocess
import sys
import time
import os
import re
import threading

def verify_flow(sgf_path):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)
    main_py = os.path.join(src_dir, "main.py")
    full_sgf_path = os.path.abspath(sgf_path)
    
    print(f"=== 最終フロー検証（1手目以降のOwnershipを確実に検知） ===")
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    
    proc = None
    success_flag = threading.Event()
    error_flag = threading.Event()

    def read_output(process):
        nonlocal success_flag, error_flag
        for line in iter(process.stdout.readline, ''):
            if not line: break
            clean_line = line.strip()
            if clean_line:
                print(f"  [APP]: {clean_line}")
                
                # [MOVE X] Ownership data detected というログを監視
                match = re.search(r"DEBUG: \[MOVE (\d+)\] Ownership data detected", clean_line)
                if match:
                    move_num = int(match.group(1))
                    if move_num > 0:
                        print(f"\n>> 検証成功：Move {move_num} で有効な勢力圏データを検知しました。")
                        success_flag.set()
                
                if "ERROR" in clean_line.upper() or "Exception" in clean_line:
                    if "start_queue_monitor" not in clean_line:
                        error_flag.set()

    try:
        # アプリ起動
        proc = subprocess.Popen([sys.executable, main_py, full_sgf_path],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, cwd=src_dir, encoding='utf-8', env=env)

        reader = threading.Thread(target=read_output, args=(proc,), daemon=True)
        reader.start()

        # 並列解析が進んで1手目以降が埋まるのをじっくり待つ (最大120秒)
        timeout = 120
        start_time = time.time()
        while time.time() - start_time < timeout:
            if success_flag.is_set(): break
            if error_flag.is_set(): break
            if proc.poll() is not None: break
            time.sleep(1)
        else:
            print("\n!! 検証失敗：タイムアウト（有効な手番でのデータ検知なし）。")

    finally:
        if proc and proc.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            proc.wait()

    return success_flag.is_set()

if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    test_sgf = os.path.join(root_dir, "test.sgf")
    if verify_flow(test_sgf):
        print("\n[RESULT] 検証パス")
        sys.exit(0)
    else:
        print("\n[RESULT] 検証失敗")
        sys.exit(1)