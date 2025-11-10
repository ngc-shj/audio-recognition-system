"""
Audio Normalization Utilities
音声正規化ユーティリティ

オーディオフォーマットに応じた音声データの正規化処理を提供します。
複数のモジュールで使用される共通ロジックをここに集約。
"""

import numpy as np
import pyaudio


def get_normalization_factor(audio_format: int) -> float:
    """
    オーディオフォーマットに応じた正規化係数を取得

    Args:
        audio_format: PyAudio フォーマット定数（pyaudio.paInt16など）

    Returns:
        正規化係数（float）

    Raises:
        ValueError: サポートされていないオーディオフォーマットの場合
    """
    format_factors = {
        pyaudio.paFloat32: 1.0,
        pyaudio.paInt8: 128.0,
        pyaudio.paInt16: 32768.0,
        pyaudio.paInt32: 2147483648.0,
    }

    if audio_format not in format_factors:
        raise ValueError(
            f"Unsupported audio format: {audio_format}. "
            f"Supported formats: {list(format_factors.keys())}"
        )

    return format_factors[audio_format]


def normalize_audio(audio_data: np.ndarray, audio_format: int) -> np.ndarray:
    """
    音声データを正規化（-1.0 ~ 1.0の範囲）

    Args:
        audio_data: 音声データ（NumPy array）
        audio_format: PyAudio フォーマット定数（pyaudio.paInt16など）

    Returns:
        正規化された音声データ（float32、-1.0 ~ 1.0）

    Raises:
        ValueError: サポートされていないオーディオフォーマットの場合
    """
    if audio_format == pyaudio.paFloat32:
        # 既にfloatの場合はクリッピング
        return np.clip(audio_data, -1.0, 1.0)
    elif audio_format == pyaudio.paInt8:
        return audio_data.astype(np.float32) / 128.0
    elif audio_format == pyaudio.paInt16:
        return audio_data.astype(np.float32) / 32768.0
    elif audio_format == pyaudio.paInt32:
        return audio_data.astype(np.float32) / 2147483648.0
    else:
        raise ValueError(
            f"Unsupported audio format: {audio_format}. "
            f"Supported: paFloat32, paInt8, paInt16, paInt32"
        )


def denormalize_audio(audio_data: np.ndarray, audio_format: int) -> np.ndarray:
    """
    正規化された音声データを元のフォーマットに戻す

    Args:
        audio_data: 正規化された音声データ（float32、-1.0 ~ 1.0）
        audio_format: PyAudio フォーマット定数（変換先フォーマット）

    Returns:
        変換されたオーディオデータ

    Raises:
        ValueError: サポートされていないオーディオフォーマットの場合
    """
    factor = get_normalization_factor(audio_format)

    if audio_format == pyaudio.paFloat32:
        return np.clip(audio_data, -1.0, 1.0)
    elif audio_format == pyaudio.paInt8:
        return np.clip(audio_data * factor, -128, 127).astype(np.int8)
    elif audio_format == pyaudio.paInt16:
        return np.clip(audio_data * factor, -32768, 32767).astype(np.int16)
    elif audio_format == pyaudio.paInt32:
        return np.clip(
            audio_data * factor, -2147483648, 2147483647
        ).astype(np.int32)
    else:
        raise ValueError(f"Unsupported audio format: {audio_format}")
