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

    改善版: スマートVADと動的バッファサイズでより適切な文章区切りを実現
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

        # 動的バッファ設定（config.yamlから取得）
        if self.config.dynamic_buffer and self.config.dynamic_buffer.enabled:
            self.use_dynamic_buffer = True
            self.min_buffer_duration = self.config.dynamic_buffer.min_duration
            self.max_buffer_duration = self.config.dynamic_buffer.max_duration
            self.short_pause_duration = self.config.dynamic_buffer.short_pause
            self.medium_pause_duration = self.config.dynamic_buffer.medium_pause
            self.long_pause_duration = self.config.dynamic_buffer.long_pause
        else:
            # 従来の固定バッファ方式
            self.use_dynamic_buffer = False
            self.min_buffer_duration = self.config.buffer_duration
            self.max_buffer_duration = self.config.buffer_duration
            self.short_pause_duration = 0.3
            self.medium_pause_duration = self.config.silence_duration
            self.long_pause_duration = self.config.silence_duration

        self.min_buffer_size = int(self.min_buffer_duration * self.config.sample_rate)
        self.max_buffer_size = int(self.max_buffer_duration * self.config.sample_rate)

        # VAD改善: ゼロ交差率しきい値
        self.zero_crossing_rate_threshold = self.config.zero_crossing_rate_threshold

    def processing_thread(self, is_running):
        """
        改善版音声処理スレッドのメイン処理

        動的バッファサイズとスマートなポーズ検出により、
        より適切な文章区切りで音声を処理します。
        """
        buffer = deque(maxlen=self.max_buffer_size)
        silence_start = None
        last_voice_activity = time.time()
        buffer_start_time = time.time()

        print("音声処理スレッド開始（改善版）")

        while is_running.is_set():
            try:
                data = self.audio_queue.get(timeout=0.2)
                buffer.extend(data)

                current_time = time.time()
                buffer_duration = current_time - buffer_start_time

                # 音声アクティビティの検出
                has_voice = self.has_voice_activity(data)

                if has_voice:
                    last_voice_activity = current_time
                    silence_start = None
                elif silence_start is None:
                    silence_start = current_time

                # ポーズの長さを計算
                pause_duration = 0
                if silence_start is not None:
                    pause_duration = current_time - silence_start

                # セグメント区切りの判定
                should_segment = False
                segment_reason = None

                # 条件1: 最大バッファ長に達した（強制区切り）
                if buffer_duration >= self.max_buffer_duration:
                    should_segment = True
                    segment_reason = "max_duration"

                # 条件2: 最小バッファ長を超え、かつ十分なポーズがある
                elif len(buffer) >= self.min_buffer_size:
                    if pause_duration >= self.medium_pause_duration:
                        should_segment = True
                        segment_reason = "medium_pause"
                    elif pause_duration >= self.long_pause_duration:
                        should_segment = True
                        segment_reason = "long_pause"

                if should_segment:
                    # ポーズ部分を除いたデータを処理
                    if silence_start is not None:
                        # 無音開始時点までのデータを抽出
                        silence_samples = int((current_time - silence_start) * self.config.sample_rate)
                        valid_samples = len(buffer) - silence_samples
                        if valid_samples > 0:
                            audio_data = np.array(list(buffer)[:valid_samples])
                        else:
                            audio_data = np.array(buffer)
                    else:
                        audio_data = np.array(buffer)

                    # 音声データが十分な長さがあれば処理
                    if len(audio_data) >= self.min_buffer_size:
                        processed_audio = self.preprocess_audio(audio_data)
                        self.processing_queue.put(processed_audio)

                    # バッファをクリア
                    buffer.clear()
                    buffer_start_time = current_time
                    silence_start = None

            except queue.Empty:
                # タイムアウト時にもバッファチェック
                if len(buffer) >= self.min_buffer_size:
                    current_time = time.time()
                    if current_time - last_voice_activity >= self.long_pause_duration:
                        audio_data = np.array(buffer)
                        if len(audio_data) > 0:
                            processed_audio = self.preprocess_audio(audio_data)
                            self.processing_queue.put(processed_audio)
                        buffer.clear()
                        buffer_start_time = current_time
            except Exception as e:
                print(f"\nエラー (処理スレッド): {e}", flush=True)

        print("音声処理スレッド終了")

    def has_voice_activity(self, audio_data):
        """
        改善版音声アクティビティ検出

        RMSエネルギーとゼロ交差率を組み合わせた、より精度の高いVAD

        Args:
            audio_data: 音声データ

        Returns:
            音声が検出されたかどうか
        """
        normalized_data = self.normalize_audio(audio_data)

        # エネルギーベースの検出
        rms = np.sqrt(np.mean(normalized_data**2))
        has_energy = rms > self.config.voice_activity_threshold

        # ゼロ交差率による検出（音声の特徴）
        zero_crossings = np.sum(np.abs(np.diff(np.sign(normalized_data)))) / (2 * len(normalized_data))
        has_speech_characteristics = zero_crossings > self.zero_crossing_rate_threshold

        # 両方の条件を満たす場合に音声と判定
        return has_energy and has_speech_characteristics

    def calculate_pause_duration(self, buffer, current_pos):
        """
        現在位置から遡ってポーズ（無音）の長さを計算

        Args:
            buffer: 音声バッファ
            current_pos: 現在の位置

        Returns:
            ポーズの長さ（秒）
        """
        chunk_duration = self.config.chunk_size / self.config.sample_rate
        silence_chunks = 0

        # 現在位置から遡って無音チャンクをカウント
        buffer_list = list(buffer)
        for i in range(min(current_pos, len(buffer_list))):
            chunk_idx = current_pos - i - 1
            if chunk_idx < 0:
                break

            chunk_start = chunk_idx * self.config.chunk_size
            chunk_end = chunk_start + self.config.chunk_size

            if chunk_end > len(buffer_list):
                break

            chunk_data = np.array(buffer_list[chunk_start:chunk_end])

            if not self.has_voice_activity(chunk_data):
                silence_chunks += 1
            else:
                break

        return silence_chunks * chunk_duration

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

