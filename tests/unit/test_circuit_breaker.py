import os
import sys
import time
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.api_client import GoAPIClient, CircuitState

def test_circuit_breaker():
    print("Testing API Circuit Breaker Logic...")
    
    # シングルトンのため、既存のインスタンスを取得してURLを書き換える
    client = GoAPIClient()
    client.base_url = "http://127.0.0.1:9999" # 存在しないポート
    client.breaker.state = CircuitState.CLOSED # 状態をリセット
    client.breaker.failure_count = 0
    
    # 1-2回目の失敗（まだCLOSED）
    print("Request 1 (Expect Failure)...")
    client.health_check()
    print(f"  Current State: {client.breaker.state}")
    
    print("Request 2 (Expect Failure)...")
    client.health_check()
    print(f"  Current State: {client.breaker.state}")

    # 3回目の失敗（ここでOPENに遷移するはず）
    print("Request 3 (Expect Failure -> OPEN)...")
    client.health_check()
    print(f"  Current State: {client.breaker.state}")
    
    if client.breaker.state == CircuitState.OPEN:
        print("SUCCESS: Circuit Breaker OPENED after failures.")
    else:
        print(f"FAILED: State is {client.breaker.state}, expected OPEN.")
        return

    # 遮断中のリクエスト（通信を試みずに即座に失敗するはず）
    start_time = time.time()
    print("Request 4 (Expect Immediate Block)...")
    res = client.health_check()
    elapsed = time.time() - start_time
    print(f"  Immediate: {elapsed < 0.1}, Result: {res}")
    
    if elapsed < 0.1:
        print("SUCCESS: Request blocked immediately (Fail-fast).")
    else:
        print(f"FAILED: Request took too long ({elapsed:.2f}s).")

if __name__ == "__main__":
    test_circuit_breaker()
