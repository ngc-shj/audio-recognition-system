"""
Web UI Server for Audio Recognition System

FastAPI-based web server with WebSocket support for real-time
speech recognition and translation display.

This server can also start the audio recognition system automatically.
"""

import asyncio
import json
import sys
import signal
import argparse
import threading
import shutil
import os
from pathlib import Path
from typing import Dict, List, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import yaml

# Logging
from utils.logger import setup_logger

# Setup logger
logger = setup_logger(__name__)

# Global shutdown flag
shutdown_requested = False

# PyAudio import for device enumeration (optional, with fallback)
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logger.warning(" PyAudio not available. Audio device enumeration will be limited.")


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
        self.config_path = "config.yaml"  # Config file path

server_state = ServerState()


# Pydantic models for API requests
class ConfigUpdateRequest(BaseModel):
    updates: Dict

# WebSocket接続の管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """全接続クライアントにメッセージをブロードキャスト"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")


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
                logger.info(f"\nStop request received. Running: {server_state.is_recognition_running}, System: {server_state.recognition_system is not None}")

                if server_state.is_recognition_running:
                    # すぐにフラグをクリアして、UIが正しい状態を表示できるようにする
                    server_state.is_recognition_running = False

                    if server_state.recognition_system:
                        logger.info("Stopping recognition system via is_running.clear()...")
                        # is_running Eventをクリアして停止
                        server_state.recognition_system.is_running.clear()

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
                        # システムインスタンスがまだキャプチャされていない場合
                        logger.warning(" System instance not yet captured. Waiting...")
                        # 少し待ってから再試行
                        import asyncio
                        await asyncio.sleep(0.5)
                        if server_state.recognition_system:
                            logger.info("System instance now available. Stopping...")
                            server_state.recognition_system.is_running.clear()
                            await websocket.send_json({
                                "type": "status",
                                "message": "Recognition stopped",
                                "status": "stopped"
                            })
                            await manager.broadcast({
                                "type": "status",
                                "message": "Recognition stopped",
                                "status": "stopped"
                            })
                        else:
                            logger.error("Could not capture system instance")
                            await websocket.send_json({
                                "type": "error",
                                "message": "Could not stop recognition: system not ready"
                            })
                            # エラーの場合でもフラグを再設定（リトライできるように）
                            server_state.is_recognition_running = True
                else:
                    logger.info("Recognition is not running")
                    await websocket.send_json({
                        "type": "status",
                        "message": "Recognition not running",
                        "status": "stopped"
                    })

            elif message_type == "settings":
                # 設定変更
                settings = data.get("settings", {})

                # サーバー設定を更新
                if "source_lang" in settings:
                    server_state.config["source_lang"] = settings["source_lang"]
                if "target_lang" in settings:
                    server_state.config["target_lang"] = settings["target_lang"]
                if "tts_enabled" in settings:
                    server_state.config["tts_enabled"] = settings["tts_enabled"]

                logger.info(f"Settings updated: {server_state.config}")

                # 設定変更確認を返す
                await websocket.send_json({
                    "type": "settings_updated",
                    "settings": settings,
                    "message": "Settings will be applied on next start"
                })

                # 全クライアントに設定変更を通知
                await manager.broadcast({
                    "type": "settings_updated",
                    "settings": settings
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
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


@app.get("/api/config/full")
async def get_full_config():
    """
    完全なconfig.yaml設定を取得

    Returns:
        config.yamlの全内容（dict形式）
    """
    try:
        with open(server_state.config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        return {"status": "success", "config": config_data}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Config file not found: {server_state.config_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading config: {str(e)}")


@app.post("/api/config/update")
async def update_config(request: ConfigUpdateRequest):
    """
    config.yaml設定を更新

    Args:
        request: ConfigUpdateRequest containing nested dict updates
            Example: {"updates": {"tts.rate": "+50%", "translation.generation.darwin.temperature": 0.9}}

    Returns:
        Success status and updated values
    """
    try:
        # Load current config
        with open(server_state.config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        # Apply updates (support nested paths with dot notation)
        updated_keys = []
        for key_path, value in request.updates.items():
            keys = key_path.split('.')
            target = config_data

            # Navigate to the nested location
            for key in keys[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]

            # Set the value
            final_key = keys[-1]
            target[final_key] = value
            updated_keys.append(key_path)

        # Write back to file
        with open(server_state.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # Broadcast config change to all clients
        await manager.broadcast({
            "type": "config_updated",
            "updated_keys": updated_keys,
            "message": "Configuration updated successfully"
        })

        return {
            "status": "success",
            "updated_keys": updated_keys,
            "message": "Config updated. Restart recognition for changes to take effect."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")


@app.get("/api/audio/devices")
async def get_audio_devices():
    """
    オーディオデバイスリストを取得

    Returns:
        入力デバイスと出力デバイスのリスト
    """
    if not PYAUDIO_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "PyAudio is not installed. Cannot enumerate audio devices.",
            "input_devices": [],
            "output_devices": []
        }

    try:
        p = pyaudio.PyAudio()
        input_devices = []
        output_devices = []

        # デバイス情報を取得
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
                device = {
                    "index": i,
                    "name": info.get('name', 'Unknown'),
                    "max_input_channels": info.get('maxInputChannels', 0),
                    "max_output_channels": info.get('maxOutputChannels', 0),
                    "default_sample_rate": int(info.get('defaultSampleRate', 0))
                }

                # 入力デバイス
                if device["max_input_channels"] > 0:
                    input_devices.append({
                        "index": device["index"],
                        "name": device["name"],
                        "channels": device["max_input_channels"],
                        "sample_rate": device["default_sample_rate"]
                    })

                # 出力デバイス
                if device["max_output_channels"] > 0:
                    output_devices.append({
                        "index": device["index"],
                        "name": device["name"],
                        "channels": device["max_output_channels"],
                        "sample_rate": device["default_sample_rate"]
                    })

            except Exception as e:
                logger.error(f"Error getting device {i} info: {e}")
                continue

        # Get default devices before terminating PyAudio
        default_input_idx = None
        default_output_idx = None

        try:
            default_input_idx = p.get_default_input_device_info()['index']
        except Exception:
            pass

        try:
            default_output_idx = p.get_default_output_device_info()['index']
        except Exception:
            pass

        p.terminate()

        return {
            "status": "success",
            "input_devices": input_devices,
            "output_devices": output_devices,
            "default_input": default_input_idx,
            "default_output": default_output_idx
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enumerating audio devices: {str(e)}")


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
                        logger.info("System instance captured for stop control")
                        break

            # インスタンスキャプチャ用スレッドを開始
            capture_thread = threading.Thread(target=check_and_store_instance, daemon=True)
            capture_thread.start()

            # メイン関数を実行（ブロッキング）
            main_module.main()
    except KeyboardInterrupt:
        logger.info("\nRecognition system interrupted")
    except Exception as e:
        logger.info(f"Error starting recognition system: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # スレッド終了時にステータスを更新
        server_state.is_recognition_running = False
        server_state.recognition_system = None
        logger.info("Recognition system stopped")


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
    # config.yamlが存在しない場合、config.yaml.exampleからコピー
    if not os.path.exists(config_path):
        example_path = config_path + ".example"
        if os.path.exists(example_path):
            try:
                shutil.copy2(example_path, config_path)
                logger.info(f"初回起動: {example_path} を {config_path} にコピーしました。")
            except Exception as e:
                logger.warning(f" 設定ファイルのコピーに失敗しました: {e}")
                logger.info(f"手動で {example_path} を {config_path} にコピーしてください。")
        else:
            logger.warning(f" {config_path} と {example_path} が見つかりません。")
            logger.warning("設定ファイルが必要です。")

    web_ui_url = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"

    # サーバー設定を保存
    server_state.config_path = config_path  # Save config path for API endpoints
    server_state.config["mode"] = mode
    if source_lang:
        server_state.config["source_lang"] = source_lang
    if target_lang:
        server_state.config["target_lang"] = target_lang

    # 音声認識システムを別スレッドで起動
    if start_recognition:
        mode_name = "音声認識＋翻訳" if mode == "translation" else "音声認識のみ"
        logger.info(f"\n{mode_name}システムを起動しています...")
        recognition_thread = threading.Thread(
            target=run_recognition_system,
            args=(config_path, source_lang, target_lang, web_ui_url, mode),
            daemon=True
        )
        recognition_thread.start()
        server_state.is_recognition_running = True
        server_state.recognition_thread = recognition_thread
        logger.info(f"{mode_name}システムが起動しました\n")

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        """Handle Ctrl+C gracefully"""
        global shutdown_requested
        if shutdown_requested:
            logger.warning("Force shutdown requested")
            sys.exit(1)

        shutdown_requested = True
        logger.info("")
        logger.info("="*60)
        logger.info("Shutting down gracefully... (Press Ctrl+C again to force)")
        logger.info("="*60)

        # Stop recognition system if running
        if server_state.is_recognition_running and server_state.recognition_system:
            logger.info("Stopping recognition system...")
            server_state.recognition_system.is_running.clear()
            server_state.is_recognition_running = False

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Configure uvicorn logging to match our format
    import logging

    # Create uvicorn log config with our custom format
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
        },
    }

    logger.info(f"Starting Web UI server at http://{host}:{port}")

    # Run uvicorn with graceful shutdown support
    try:
        uvicorn.run(app, host=host, port=port, log_level="info", log_config=log_config)
    except KeyboardInterrupt:
        logger.info("Server shutdown complete")
    finally:
        # Final cleanup
        if server_state.is_recognition_running and server_state.recognition_system:
            server_state.recognition_system.is_running.clear()
        logger.info("Web UI server stopped")


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
