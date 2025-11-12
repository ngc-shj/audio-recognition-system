"""
Audio Capture Module (Clean Config Compatible)
音声キャプチャモジュール（クリーン統合版対応）
"""

import pyaudio
import numpy as np
import time
import queue
from typing import Optional, Any
from threading import Event

# Logging
from utils.logger import setup_logger


# Setup logger
logger = setup_logger(__name__)

class AudioCapture:
    """
    音声キャプチャクラス
    
    AudioConfigデータクラスを使用してPyAudioストリームを管理します。
    """
    
    def __init__(
        self,
        audio_config: Any,
        audio_queue: queue.Queue,
        config_manager: Optional[Any] = None
    ) -> None:
        """
        Args:
            audio_config: AudioConfig データクラス
            audio_queue: 音声データを格納するキュー
            config_manager: ConfigManager（オプション、input_device取得用）
        """
        self.audio_config = audio_config
        self.audio_queue = audio_queue
        
        # input_deviceの取得
        if config_manager and hasattr(config_manager, 'input_device'):
            input_device = config_manager.input_device
        elif hasattr(audio_config, 'input_device'):
            input_device = audio_config.input_device
        else:
            input_device = None

        input_device_index = self.get_input_device_index(input_device)
        if input_device_index is None:
            raise ValueError("適切な入力デバイスが見つかりません。手動で指定してください。")

        self.input_device_index = input_device_index

    def audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudioストリームのコールバック関数"""
        audio_data = np.frombuffer(in_data, dtype=self.audio_config.numpy_dtype)
        self.audio_queue.put(audio_data)
        return (in_data, pyaudio.paContinue)

    def capture_thread(self, is_running: Event) -> None:
        """音声キャプチャスレッドのメイン処理"""
        audio = None
        stream = None

        try:
            audio = pyaudio.PyAudio()

            stream = audio.open(
                format=self.audio_config.format,
                channels=self.audio_config.channels,
                rate=self.audio_config.sample_rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.audio_config.chunk_size,
                stream_callback=self.audio_callback
            )

            logger.info(f"音声キャプチャスレッド開始 (デバイスインデックス: {self.input_device_index})")

            stream.start_stream()

            while is_running.is_set():
                time.sleep(0.1)

        except Exception as e:
            logger.error(f"音声キャプチャエラー: {e}")
        finally:
            # Ensure proper cleanup even if an exception occurs
            if stream is not None:
                try:
                    if stream.is_active():
                        stream.stop_stream()
                    # Give the audio callback time to complete before closing
                    # This prevents crashes during Python shutdown (especially with Python 3.13 GIL)
                    time.sleep(0.2)
                    stream.close()
                except Exception as e:
                    logger.error(f"ストリームクローズエラー: {e}")

            if audio is not None:
                try:
                    audio.terminate()
                except Exception as e:
                    logger.error(f"PyAudio終了エラー: {e}")

            logger.info("音声キャプチャスレッド終了")

    @staticmethod
    def get_input_device_index(input_device: Optional[int]) -> Optional[int]:
        """
        入力デバイスのインデックスを取得
        
        Args:
            input_device: 指定されたデバイスインデックス（Noneの場合は自動検出）
        
        Returns:
            デバイスインデックス
        """
        if input_device is not None:
            return input_device

        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            device_name = info["name"].lower()
            
            # 仮想オーディオデバイスを自動検出
            if any(keyword in device_name for keyword in [
                "blackhole",
                "stereo mix",
                "ステレオ ミキサー",
                "soundflower"
            ]):
                p.terminate()
                return i
        
        p.terminate()
        return None

