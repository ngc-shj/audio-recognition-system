"""
Web UI Server for Audio Recognition System

FastAPI-based web server with WebSocket support for real-time
speech recognition and translation display.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn


app = FastAPI(title="Audio Recognition System Web UI")

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
                await websocket.send_json({
                    "type": "status",
                    "message": "Recognition started",
                    "status": "running"
                })

            elif message_type == "stop":
                # 音声認識停止
                await websocket.send_json({
                    "type": "status",
                    "message": "Recognition stopped",
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
        "recognition_active": False
    }


@app.post("/api/broadcast")
async def broadcast_message(message: dict):
    """
    メッセージをブロードキャスト（内部API）

    音声認識・翻訳システムからこのAPIを呼び出して
    WebSocketクライアントにメッセージを送信する
    """
    await manager.broadcast(message)
    return {"status": "ok"}


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Web UIサーバーを起動"""
    print(f"Starting Web UI server at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
