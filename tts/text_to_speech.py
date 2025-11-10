"""
TTS (Text-to-Speech) モジュール

edge-ttsを使用して、翻訳されたテキストを音声で読み上げます。
"""

import asyncio
import io
from typing import Optional
from threading import Thread, Lock
from queue import Queue

# edge-tts のインポート（オプショナル）
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("Warning: edge-tts is not available. Install with 'pip install edge-tts'")

# PyAudio のインポート（音声再生用）
try:
    import pyaudio
    import wave
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("Warning: pyaudio is not available. Audio playback will not work.")


class TextToSpeech:
    """
    テキスト読み上げクラス（edge-tts使用）

    翻訳されたテキストをリアルタイムで音声に変換して再生します。
    """

    def __init__(self, tts_config, debug=False):
        """
        Args:
            tts_config: TTS設定（TTSConfig）
            debug: デバッグモード
        """
        self.config = tts_config
        self.debug = debug

        self.speech_queue = Queue()
        self.speech_thread = None
        self.is_running = False
        self.lock = Lock()

        if not self.config.enabled:
            print("TTS is disabled")
            return

        if not EDGE_TTS_AVAILABLE:
            print("TTS is enabled but edge-tts is not available")
            return

        if not PYAUDIO_AVAILABLE:
            print("TTS is enabled but pyaudio is not available for playback")
            return

        # 設定の表示
        if self.debug:
            print(f"Initializing TTS engine: {self.config.engine}")
            print(f"  Voice: {self.config.voice}")
            print(f"  Rate: {self.config.rate}")
            print(f"  Volume: {self.config.volume}")
            print(f"  Pitch: {self.config.pitch}")

        print("TTS engine initialized successfully")

        # 音声再生スレッドの開始
        self._start_speech_thread()

    def _start_speech_thread(self):
        """音声再生スレッドを開始"""
        self.is_running = True
        self.speech_thread = Thread(target=self._speech_worker, daemon=True)
        self.speech_thread.start()

    def _speech_worker(self):
        """音声再生ワーカースレッド"""
        try:
            # asyncioイベントループを作成
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            while self.is_running:
                # キューからテキストを取得
                text = self.speech_queue.get()

                if text is None:  # 終了シグナル
                    break

                # テキストを読み上げ
                try:
                    loop.run_until_complete(self._synthesize_and_play(text))
                except Exception as e:
                    if self.debug:
                        print(f"TTS playback error: {e}")
                        import traceback
                        traceback.print_exc()

            loop.close()

        except Exception as e:
            if self.debug:
                print(f"Speech worker error: {e}")
                import traceback
                traceback.print_exc()

    async def _synthesize_and_play(self, text: str):
        """
        テキストを音声合成して再生

        Args:
            text: 読み上げるテキスト
        """
        try:
            # edge-ttsで音声合成
            communicate = edge_tts.Communicate(
                text,
                self.config.voice,
                rate=self.config.rate,
                volume=self.config.volume,
                pitch=self.config.pitch
            )

            # 音声データをメモリに保存
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            if not audio_data:
                if self.debug:
                    print("No audio data generated")
                return

            # PyAudioで再生
            self._play_audio(audio_data)

        except Exception as e:
            if self.debug:
                print(f"Synthesis error: {e}")
                import traceback
                traceback.print_exc()

    def _play_audio(self, audio_data: bytes):
        """
        音声データを再生

        Args:
            audio_data: MP3音声データ
        """
        try:
            # MP3データをWAVに変換（簡易的にpydubを使わずに再生）
            # edge-ttsはMP3形式で出力するため、PyAudioで直接再生するには
            # pydubまたはffmpegが必要ですが、ここでは一時ファイルを使用
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # macOSの場合はafplayコマンドを使用（より簡単）
                import subprocess
                subprocess.run(['afplay', temp_file_path], check=True)
            except Exception as e:
                if self.debug:
                    print(f"afplay error: {e}, trying alternative method")
                # 他のプラットフォームではmpvなどを使用
                try:
                    subprocess.run(['mpv', '--no-video', temp_file_path], check=True)
                except Exception as e2:
                    if self.debug:
                        print(f"mpv error: {e2}")
                    print("Audio playback failed. Please install 'afplay' (macOS) or 'mpv'")
            finally:
                # 一時ファイルを削除
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

        except Exception as e:
            if self.debug:
                print(f"Playback error: {e}")
                import traceback
                traceback.print_exc()

    def speak(self, text: str):
        """
        テキストを音声で読み上げる

        Args:
            text: 読み上げるテキスト
        """
        if not self.config.enabled:
            return

        if not EDGE_TTS_AVAILABLE or not PYAUDIO_AVAILABLE:
            return

        if not text or len(text.strip()) == 0:
            return

        try:
            # テキストをキューに追加
            self.speech_queue.put(text)

            if self.debug:
                print(f"TTS: Queued text: {text[:50]}...")

        except Exception as e:
            if self.debug:
                print(f"TTS error: {e}")
                import traceback
                traceback.print_exc()

    def stop(self):
        """TTS再生を停止"""
        self.is_running = False
        if self.speech_queue is not None:
            self.speech_queue.put(None)  # 終了シグナル
        if self.speech_thread is not None:
            self.speech_thread.join(timeout=2.0)
