"""
Web UI Server for Audio Recognition System

FastAPI-based web server with WebSocket support for real-time
speech recognition and translation display.

This server can also start the audio recognition system automatically.
"""

import asyncio
import json
import sys
import argparse
import threading
from pathlib import Path
from typing import Dict, List, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn


app = FastAPI(title="Audio Recognition System Web UI")

# グローバル設定とステート
class ServerState:
    def __init__(self):
        self.config = {
            "mode": "translation",
            "source_lang": "en",
            "target_lang": "ja",
        }
        self.recognition_thread = None
        self.is_recognition_running = False
        self.recognition_system = None  # AudioTranscriptionSystem instance

server_state = ServerState()

# WebSocket接続の管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """全接続クライアントにメッセージをブロードキャスト"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to client: {e}")


manager = ConnectionManager()


# 静的ファイルのサービング
web_dir = Path(__file__).parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.get("/")
async def get():
    """メインページを返す"""
    html_file = web_dir / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(), status_code=200)
    else:
        return HTMLResponse(
            content="""
            <html>
                <head><title>Audio Recognition System</title></head>
                <body>
                    <h1>Audio Recognition System Web UI</h1>
                    <p>Web UI files not found. Please create web/index.html</p>
                </body>
            </html>
            """,
            status_code=200
        )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocketエンドポイント"""
    await manager.connect(websocket)
    try:
        while True:
            # クライアントからのメッセージを受信
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "ping":
                # Pongを返す
                await websocket.send_json({"type": "pong"})

            elif message_type == "start":
                # 音声認識開始
                if not server_state.is_recognition_running:
                    # 設定を取得
                    settings = data.get("settings", {})
                    mode = settings.get("mode") or server_state.config.get("mode", "translation")
                    source_lang = settings.get("source_lang") or server_state.config.get("source_lang")
                    target_lang = settings.get("target_lang") or server_state.config.get("target_lang")

                    # サーバー設定を更新
                    server_state.config["mode"] = mode
                    server_state.config["source_lang"] = source_lang
                    server_state.config["target_lang"] = target_lang

                    # 認識システムを起動
                    web_ui_url = "http://localhost:8000"
                    recognition_thread = threading.Thread(
                        target=run_recognition_system,
                        args=("config.yaml", source_lang, target_lang, web_ui_url, mode),
                        daemon=True
                    )
                    recognition_thread.start()
                    server_state.is_recognition_running = True
                    server_state.recognition_thread = recognition_thread

                    await websocket.send_json({
                        "type": "status",
                        "message": "Recognition started",
                        "status": "running"
                    })
                    # 全クライアントに通知
                    await manager.broadcast({
                        "type": "status",
                        "message": "Recognition started",
                        "status": "running"
                    })
                else:
                    await websocket.send_json({
                        "type": "status",
                        "message": "Recognition already running",
                        "status": "running"
                    })

            elif message_type == "stop":
                # 音声認識停止
                if server_state.is_recognition_running and server_state.recognition_system:
                    print("\nStopping recognition system...")
                    # is_running Eventをクリアして停止
                    server_state.recognition_system.is_running.clear()
                    server_state.is_recognition_running = False

                    await websocket.send_json({
                        "type": "status",
                        "message": "Recognition stopped",
                        "status": "stopped"
                    })
                    # 全クライアントに通知
                    await manager.broadcast({
                        "type": "status",
                        "message": "Recognition stopped",
                        "status": "stopped"
                    })
                else:
                    await websocket.send_json({
                        "type": "status",
                        "message": "Recognition not running",
                        "status": "stopped"
                    })

            elif message_type == "settings":
                # 設定変更
                settings = data.get("settings", {})
                await websocket.send_json({
                    "type": "settings_updated",
                    "settings": settings
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.get("/api/status")
async def get_status():
    """システムステータスを取得"""
    return {
        "status": "running",
        "connections": len(manager.active_connections),
        "recognition_active": server_state.is_recognition_running
    }


@app.get("/api/config")
async def get_config():
    """現在の設定を取得"""
    return server_state.config


@app.post("/api/broadcast")
async def broadcast_message(message: dict):
    """
    メッセージをブロードキャスト（内部API）

    音声認識・翻訳システムからこのAPIを呼び出して
    WebSocketクライアントにメッセージを送信する
    """
    await manager.broadcast(message)
    return {"status": "ok"}


def run_recognition_system(config_path: str = "config.yaml",
                          source_lang: Optional[str] = None,
                          target_lang: Optional[str] = None,
                          web_ui_url: str = "http://localhost:8000",
                          mode: str = "translation"):
    """
    音声認識システムを別スレッドで起動

    Args:
        config_path: 設定ファイルのパス
        source_lang: 音源言語
        target_lang: 翻訳先言語
        web_ui_url: Web UIサーバーのURL
        mode: 動作モード ('translation' or 'transcript')
    """
    try:
        # モードに応じてメインスクリプトを選択
        import importlib.util
        if mode == "transcript":
            script_path = "main_transcription_only.py"
        else:
            script_path = "main_with_translation.py"

        spec = importlib.util.spec_from_file_location("main_module", script_path)
        if spec and spec.loader:
            main_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(main_module)

            # コマンドライン引数を構築
            sys.argv = [script_path, "--web-ui", "--web-ui-url", web_ui_url]
            if config_path:
                sys.argv.extend(["--config", config_path])
            if source_lang:
                sys.argv.extend(["--source-lang", source_lang])
            if mode == "translation" and target_lang:
                sys.argv.extend(["--target-lang", target_lang])

            # メイン関数を実行（ブロッキング）
            # システムインスタンスは別スレッドで定期的にチェック
            def check_and_store_instance():
                """定期的に_system_instanceをチェックしてserver_stateに保存"""
                import time
                for _ in range(50):  # 最大5秒待機
                    time.sleep(0.1)
                    if hasattr(main_module, '_system_instance') and main_module._system_instance:
                        server_state.recognition_system = main_module._system_instance
                        print("System instance captured for stop control")
                        break

            # インスタンスキャプチャ用スレッドを開始
            capture_thread = threading.Thread(target=check_and_store_instance, daemon=True)
            capture_thread.start()

            # メイン関数を実行（ブロッキング）
            main_module.main()
    except KeyboardInterrupt:
        print("\nRecognition system interrupted")
    except Exception as e:
        print(f"Error starting recognition system: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # スレッド終了時にステータスを更新
        server_state.is_recognition_running = False
        server_state.recognition_system = None
        print("Recognition system stopped")


def run_server(host: str = "0.0.0.0", port: int = 8000,
               start_recognition: bool = False,
               config_path: str = "config.yaml",
               source_lang: Optional[str] = None,
               target_lang: Optional[str] = None,
               mode: str = "translation"):
    """
    Web UIサーバーを起動

    Args:
        host: ホストアドレス
        port: ポート番号
        start_recognition: 音声認識システムも起動するか
        config_path: 設定ファイルのパス
        source_lang: 音源言語
        target_lang: 翻訳先言語
        mode: 動作モード ('translation' or 'transcript')
    """
    web_ui_url = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"

    # サーバー設定を保存
    server_state.config["mode"] = mode
    if source_lang:
        server_state.config["source_lang"] = source_lang
    if target_lang:
        server_state.config["target_lang"] = target_lang

    # 音声認識システムを別スレッドで起動
    if start_recognition:
        mode_name = "音声認識＋翻訳" if mode == "translation" else "音声認識のみ"
        print(f"\n{mode_name}システムを起動しています...")
        recognition_thread = threading.Thread(
            target=run_recognition_system,
            args=(config_path, source_lang, target_lang, web_ui_url, mode),
            daemon=True
        )
        recognition_thread.start()
        server_state.is_recognition_running = True
        server_state.recognition_thread = recognition_thread
        print(f"{mode_name}システムが起動しました\n")

    print(f"Starting Web UI server at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio Recognition System Web UI Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--start-recognition", action="store_true",
                       help="Start audio recognition system automatically")
    parser.add_argument("--mode", type=str, default="translation",
                       choices=["translation", "transcript"],
                       help="Recognition mode: 'translation' (with translation) or 'transcript' (recognition only)")
    parser.add_argument("--config", type=str, default="config.yaml",
                       help="Configuration file path")
    parser.add_argument("--source-lang", type=str, help="Source language (e.g., 'en', 'ja')")
    parser.add_argument("--target-lang", type=str, help="Target language (e.g., 'ja', 'en')")

    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        start_recognition=args.start_recognition,
        config_path=args.config,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        mode=args.mode
    )
