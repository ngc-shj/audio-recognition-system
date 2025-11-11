"""
Web UI Bridge

Bridges the audio recognition/translation system with the Web UI
by sending real-time updates via WebSocket.
"""

import asyncio
import json
from typing import Optional
from datetime import datetime
import requests


class WebUIBridge:
    """
    Web UIとの橋渡しクラス

    音声認識・翻訳システムからの出力をWeb UIにリアルタイムで送信します。
    """

    def __init__(self, server_url: str = "http://localhost:8000", enabled: bool = True):
        """
        Args:
            server_url: Web UIサーバーのURL
            enabled: Web UI連携を有効にするか
        """
        self.server_url = server_url
        self.enabled = enabled
        self.broadcast_url = f"{server_url}/api/broadcast"

    def send_recognized_text(self, text: str, language: str = "en", pair_id: Optional[str] = None):
        """
        認識されたテキストを送信

        Args:
            text: 認識されたテキスト
            language: 言語コード
            pair_id: ペアID（翻訳と紐付けるため）
        """
        if not self.enabled:
            return

        message = {
            "type": "recognized",
            "text": text,
            "language": language,
            "pair_id": pair_id or datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        self._broadcast(message)

    def send_translated_text(self, text: str, source_text: Optional[str] = None, pair_id: Optional[str] = None):
        """
        翻訳されたテキストを送信

        Args:
            text: 翻訳されたテキスト
            source_text: 元のテキスト（オプション）
            pair_id: ペアID（認識テキストと紐付けるため）
        """
        if not self.enabled:
            return

        message = {
            "type": "translated",
            "text": text,
            "source_text": source_text,
            "pair_id": pair_id or datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        self._broadcast(message)

    def send_status(self, status: str, message: str):
        """
        ステータス更新を送信

        Args:
            status: ステータス（running, stopped, error等）
            message: ステータスメッセージ
        """
        if not self.enabled:
            return

        data = {
            "type": "status",
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self._broadcast(data)

    def send_error(self, error_message: str):
        """
        エラーメッセージを送信

        Args:
            error_message: エラーメッセージ
        """
        if not self.enabled:
            return

        message = {
            "type": "error",
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        }
        self._broadcast(message)

    def _broadcast(self, message: dict):
        """
        メッセージをブロードキャスト

        Args:
            message: 送信するメッセージ
        """
        try:
            response = requests.post(
                self.broadcast_url,
                json=message,
                timeout=1.0  # タイムアウトを短く設定
            )
            if response.status_code != 200:
                print(f"Failed to broadcast message: {response.status_code}")
        except requests.exceptions.RequestException as e:
            # Web UIサーバーが起動していない場合などは無視
            pass
        except Exception as e:
            print(f"Error broadcasting message: {e}")
