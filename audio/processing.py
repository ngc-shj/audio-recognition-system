"""
Audio Processing Module
音声処理モジュール
"""

import pyaudio
import numpy as np
import queue
import time
from collections import deque
import noisereduce as nr
from scipy import signal

# 共通の音声正規化関数
from utils.audio_normalization import normalize_audio


class AudioProcessing:
    """
    音声処理クラス

    AudioConfigデータクラスを使用して音声データを処理します。
    フィルタ係数はコンストラクタで事前計算し、毎バッファでの再計算を回避。
    """

    def __init__(self, audio_config, audio_queue, processing_queue):
        """
        Args:
            audio_config: AudioConfig データクラス
            audio_queue: 入力音声データのキュー
            processing_queue: 処理済み音声データのキュー
        """
        self.config = audio_config
        self.audio_queue = audio_queue
        self.processing_queue = processing_queue

        # パフォーマンス最適化：バンドパスフィルタ係数を初期化時に計算
        self._butter_sos = signal.butter(
            10,
            [300, 3000],
            btype='band',
            fs=self.config.sample_rate,
            output='sos'
        )

    def processing_thread(self, is_running):
        """音声処理スレッドのメイン処理"""
        buffer = deque(maxlen=self.config.buffer_size)
        silence_start = None
        last_voice_activity = time.time()
        
        print("音声処理スレッド開始")
        
        while is_running.is_set():
            try:
                data = self.audio_queue.get(timeout=0.2)
                buffer.extend(data)
                
                if self.has_voice_activity(data):
                    last_voice_activity = time.time()
                    silence_start = None
                elif silence_start is None:
                    silence_start = time.time()
                
                if len(buffer) >= self.config.buffer_size:
                    current_time = time.time()
                    if current_time - last_voice_activity < self.config.silence_duration:
                        audio_data = np.array(buffer)
                        processed_audio = self.preprocess_audio(audio_data)
                        self.processing_queue.put(processed_audio)
                    
                    # オーバーラップ処理
                    overlap = int(self.config.buffer_size * 0.05)
                    for _ in range(self.config.buffer_size - overlap):
                        buffer.popleft()
            
            except queue.Empty:
                pass
            except Exception as e:
                print(f"\nエラー (処理スレッド): {e}", flush=True)
        
        print("音声処理スレッド終了")

    def has_voice_activity(self, audio_data):
        """
        音声アクティビティ検出
        
        Args:
            audio_data: 音声データ
        
        Returns:
            音声が検出されたかどうか
        """
        normalized_data = self.normalize_audio(audio_data)
        rms = np.sqrt(np.mean(normalized_data**2))
        return rms > self.config.voice_activity_threshold

    def normalize_audio(self, audio_data):
        """
        音声データを正規化

        Args:
            audio_data: 音声データ

        Returns:
            正規化された音声データ（-1.0 ~ 1.0）

        Note:
            実装は utils.audio_normalization.normalize_audio に委譲
        """
        return normalize_audio(audio_data, self.config.format)

    def preprocess_audio(self, audio_data):
        """
        音声データの前処理（ノイズ除去、バンドパスフィルタ）

        Args:
            audio_data: 音声データ

        Returns:
            前処理済み音声データ
        """
        # ノイズ除去
        reduced_noise = nr.reduce_noise(y=audio_data, sr=self.config.sample_rate)

        # バンドパスフィルタ（300Hz ~ 3000Hz）
        # 注: フィルタ係数は __init__ で事前計算済み（パフォーマンス最適化）
        filtered_audio = signal.sosfilt(self._butter_sos, reduced_noise)

        return filtered_audio

