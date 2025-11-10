"""
TTS (Text-to-Speech) モジュール

pyttsx3を使用して、翻訳されたテキストを音声で読み上げます。
"""

from typing import Optional
from threading import Thread, Lock
from queue import Queue

# pyttsx3 のインポート（オプショナル）
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    print("Warning: pyttsx3 is not available. Install with 'pip install pyttsx3'")


class TextToSpeech:
    """
    テキスト読み上げクラス（pyttsx3使用）

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

        self.engine = None
        self.speech_queue = Queue()
        self.speech_thread = None
        self.is_running = False
        self.lock = Lock()

        if not self.config.enabled:
            print("TTS is disabled")
            return

        if not PYTTSX3_AVAILABLE:
            print("TTS is enabled but pyttsx3 is not available")
            return

        # TTSエンジンの初期化
        self._init_engine()

        # 音声再生スレッドの開始
        self._start_speech_thread()

    def _init_engine(self):
        """pyttsx3エンジンを初期化"""
        try:
            print(f"Initializing TTS engine: {self.config.engine}")

            self.engine = pyttsx3.init()

            # 読み上げ速度の設定
            self.engine.setProperty('rate', self.config.rate)

            # 音量の設定
            self.engine.setProperty('volume', self.config.volume)

            # 音声の設定（指定されている場合）
            if self.config.voice:
                self.engine.setProperty('voice', self.config.voice)
            else:
                # デフォルト音声を使用（日本語音声がある場合は自動選択）
                voices = self.engine.getProperty('voices')
                if self.debug:
                    print(f"Available voices: {len(voices)}")
                    for voice in voices:
                        print(f"  - {voice.id}: {voice.name} ({voice.languages})")

                # 日本語音声を探す
                japanese_voice = None
                for voice in voices:
                    if 'ja' in str(voice.languages).lower() or 'japanese' in voice.name.lower():
                        japanese_voice = voice
                        break

                if japanese_voice:
                    self.engine.setProperty('voice', japanese_voice.id)
                    if self.debug:
                        print(f"Selected Japanese voice: {japanese_voice.name}")

            print("TTS engine initialized successfully")

        except Exception as e:
            print(f"Failed to initialize TTS engine: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _start_speech_thread(self):
        """音声再生スレッドを開始"""
        self.is_running = True
        self.speech_thread = Thread(target=self._speech_worker, daemon=True)
        self.speech_thread.start()

    def _speech_worker(self):
        """音声再生ワーカースレッド"""
        try:
            while self.is_running:
                # キューからテキストを取得
                text = self.speech_queue.get()

                if text is None:  # 終了シグナル
                    break

                # テキストを読み上げ
                try:
                    with self.lock:
                        self.engine.say(text)
                        self.engine.runAndWait()
                except Exception as e:
                    if self.debug:
                        print(f"TTS playback error: {e}")

        except Exception as e:
            if self.debug:
                print(f"Speech worker error: {e}")
                import traceback
                traceback.print_exc()

    def speak(self, text: str):
        """
        テキストを音声で読み上げる

        Args:
            text: 読み上げるテキスト
        """
        if not self.config.enabled or self.engine is None:
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

        # エンジンを停止
        if self.engine is not None:
            try:
                self.engine.stop()
            except:
                pass
