import subprocess
import json
import sys
import os
import time
import threading

def read_stream(process):
    """サーバーからの出力を読み取るスレッド"""
    for line in process.stdout:
        line = line.strip()
        if line:
            try:
                msg = json.loads(line)
                # デバッグ用に簡略化して表示
                if "result" in msg:
                    print(f"\n[SERVER RESPONSE] ID={msg.get('id')}: Success")
                    # 結果の中身を整形して表示
                    res_content = msg["result"].get("content", [])
                    for item in res_content:
                        if item.get("type") == "text":
                            print(f"--- CONTENT ---\n{item['text'][:500]}...\n----------------")
                else:
                    print(f"\n[SERVER MESSAGE] {line[:200]}...")
            except:
                print(f"[RAW] {line}")

def run_verification():
    server_script = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    
    # 1. Start Server
    print(f"Starting MCP Server: {server_script}")
    process = subprocess.Popen(
        [sys.executable, server_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=False
    )

    # Output reader thread
    t = threading.Thread(target=read_stream, args=(process,), daemon=True)
    t.start()

    try:
        # 2. Initialize (MCP Handshake)
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {"name": "verify_client", "version": "1.0"}
            }
        }
        print("\n[CLIENT] Sending 'initialize'...")
        process.stdin.write((json.dumps(init_req) + "\n").encode('utf-8'))
        process.stdin.flush()
        time.sleep(1)

        # 3. Initialized Notification
        print("\n[CLIENT] Sending 'notifications/initialized'...")
        msg = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + "\n"
        process.stdin.write(msg.encode('utf-8'))
        process.stdin.flush()
        time.sleep(1)

        # 4. List Tools
        print("\n[CLIENT] Requesting 'tools/list'...")
        msg = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }) + "\n"
        process.stdin.write(msg.encode('utf-8'))
        process.stdin.flush()
        time.sleep(2)

        # 5. Call Tool: detect_shapes (Using a sample history)
        # Empty board test
        print("\n[CLIENT] Calling tool 'detect_shapes' (Empty Board)...")
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "detect_shapes",
                "arguments": {
                    "history": [],
                    "board_size": 19
                }
            }
        }
        process.stdin.write((json.dumps(call_req) + "\n").encode('utf-8'))
        process.stdin.flush()
        time.sleep(5)

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        process.terminate()
        process.wait()
        print("Server stopped.")

if __name__ == "__main__":
    run_verification()
