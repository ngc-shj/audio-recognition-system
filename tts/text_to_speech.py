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
        self.output_device_index = None

        if not self.config.enabled:
            print("TTS is disabled")
            return

        if not EDGE_TTS_AVAILABLE:
            print("TTS is enabled but edge-tts is not available")
            return

        if not PYAUDIO_AVAILABLE:
            print("TTS is enabled but pyaudio is not available for playback")
            return

        # 出力デバイスの検索
        if self.config.output_device:
            self.output_device_index = self._find_output_device(self.config.output_device)
            if self.output_device_index is None:
                print(f"Warning: Output device '{self.config.output_device}' not found. Using default device.")

        # 設定の表示
        if self.debug:
            print(f"Initializing TTS engine: {self.config.engine}")
            print(f"  Voice: {self.config.voice}")
            print(f"  Rate: {self.config.rate}")
            print(f"  Volume: {self.config.volume}")
            print(f"  Pitch: {self.config.pitch}")
            print(f"  Output Device: {self.config.output_device or 'Default'}")
            if self.output_device_index is not None:
                print(f"  Output Device Index: {self.output_device_index}")

        print("TTS engine initialized successfully")

        # 音声再生スレッドの開始
        self._start_speech_thread()

    def _find_output_device(self, device_name: str) -> Optional[int]:
        """
        デバイス名から出力デバイスのインデックスを検索

        Args:
            device_name: デバイス名

        Returns:
            デバイスインデックス、見つからない場合はNone
        """
        try:
            p = pyaudio.PyAudio()
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info['maxOutputChannels'] > 0 and device_name.lower() in info['name'].lower():
                    p.terminate()
                    return i
            p.terminate()
        except Exception as e:
            if self.debug:
                print(f"Error finding output device: {e}")
        return None

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

            # 音声再生
            if self.output_device_index is not None:
                # PyAudioで指定デバイスに再生
                self._play_audio_pyaudio(audio_data)
            else:
                # デフォルトデバイスに再生（afplay使用）
                self._play_audio_afplay(audio_data)

        except Exception as e:
            if self.debug:
                print(f"Synthesis error: {e}")
                import traceback
                traceback.print_exc()

    def _play_audio_pyaudio(self, audio_data: bytes):
        """
        PyAudioで音声データを指定デバイスに再生

        Args:
            audio_data: MP3音声データ
        """
        try:
            # ffmpegを使ってMP3をWAVに変換
            import tempfile
            import os
            import subprocess

            # 一時ファイルにMP3を保存
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as mp3_file:
                mp3_file.write(audio_data)
                mp3_path = mp3_file.name

            # WAVファイルのパス
            wav_path = mp3_path.replace('.mp3', '.wav')

            try:
                # ffmpegでMP3をWAVに変換
                subprocess.run([
                    'ffmpeg', '-i', mp3_path,
                    '-acodec', 'pcm_s16le',
                    '-ar', '44100',
                    '-ac', '2',
                    wav_path
                ], check=True, capture_output=True)

                # WAVファイルを読み込んで再生
                with wave.open(wav_path, 'rb') as wf:
                    # PyAudioで再生
                    p = pyaudio.PyAudio()

                    stream = p.open(
                        format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True,
                        output_device_index=self.output_device_index
                    )

                    # オーディオデータを再生
                    data = wf.readframes(1024)
                    while data:
                        stream.write(data)
                        data = wf.readframes(1024)

                    # クリーンアップ
                    stream.stop_stream()
                    stream.close()
                    p.terminate()

            finally:
                # 一時ファイルを削除
                try:
                    os.unlink(mp3_path)
                except:
                    pass
                try:
                    os.unlink(wav_path)
                except:
                    pass

        except Exception as e:
            if self.debug:
                print(f"PyAudio playback error: {e}")
                import traceback
                traceback.print_exc()
            # フォールバック
            self._play_audio_afplay(audio_data)

    def _play_audio_afplay(self, audio_data: bytes):
        """
        音声データをデフォルトデバイスで再生（afplay使用）

        Args:
            audio_data: MP3音声データ
        """
        try:
            import tempfile
            import os
            import subprocess

            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # macOSの場合はafplayコマンドを使用（より簡単）
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
