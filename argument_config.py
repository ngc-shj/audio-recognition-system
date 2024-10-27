import sys
import argparse
from typing import Optional

def setup_model_args(parser: argparse.ArgumentParser) -> None:
    """音声認識モデル関連の引数を設定"""
    model_group = parser.add_argument_group('ASR Model Settings')
    if sys.platform == 'darwin':
        model_group.add_argument(
            "--model-path",
            type=str,
            default="mlx-community/whisper-large-v3-turbo",
            help="Path or HuggingFace repo for the Whisper model"
        )
    model_group.add_argument(
        "--model-size",
        default="large-v3-turbo",
        choices=["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo", "turbo"],
        help="Model size for Whisper (default: large-v3-turbo)"
    )

def setup_llm_args(parser: argparse.ArgumentParser) -> None:
    """翻訳用LLMモデル関連の引数を設定"""
    llm_group = parser.add_argument_group('Translation LLM Settings')
    if sys.platform == 'darwin':
        llm_group.add_argument(
            "--llm-model",
            type=str,
            default="mlx-community/llm-jp-3-3.7b-instruct",
            help="Path or HuggingFace repo for the translation LLM model"
        )
    else:
        llm_group.add_argument(
            "--llm-model",
            type=str,
            default="llm-jp/llm-jp-3-3.7b-instruct",
            help="Path to the local LLM model for translation"
        )
    llm_group.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Batch size for translation processing"
    )

def setup_audio_args(parser: argparse.ArgumentParser) -> None:
    """音声入力関連の引数を設定"""
    audio_group = parser.add_argument_group('Audio Settings')
    audio_group.add_argument(
        "--format",
        type=str,
        default="int16",
        choices=['int8', 'int16', 'int32', 'float32'],
        help="Audio format (default: int16)"
    )
    audio_group.add_argument(
        "--rate",
        type=int,
        default=16000,
        help="Sample rate (default: 16000)"
    )
    audio_group.add_argument(
        "--channels",
        type=int,
        default=1,
        help="Number of channels (default: 1)"
    )
    audio_group.add_argument(
        "--chunk",
        type=int,
        default=1024,
        help="Chunk size (default: 1024)"
    )
    audio_group.add_argument(
        "--input-device",
        type=int,
        help="Input device index (default: auto-detect Black Hole)"
    )
    audio_group.add_argument(
        "--buffer-duration",
        type=float,
        default=5.0,
        help="Duration of audio buffer in seconds (default: 5.0)"
    )

def setup_language_args(parser: argparse.ArgumentParser, translation: bool = False) -> None:
    """言語関連の引数を設定"""
    lang_group = parser.add_argument_group('Language Settings')
    lang_group.add_argument(
        "--source-lang",
        type=str,
        default="en",
        help="Source language for speech recognition (e.g., 'en', 'ja')"
    )
    if translation:
        lang_group.add_argument(
            "--target-lang",
            type=str,
            default="ja",
            help="Target language for translation (e.g., 'en', 'ja')"
        )

def setup_output_args(parser: argparse.ArgumentParser) -> None:
    """出力関連の引数を設定"""
    output_group = parser.add_argument_group('Output Settings')
    output_group.add_argument(
        "--output-dir",
        type=str,
        default="logs",
        help="Directory where log files will be saved (default: 'logs')"
    )
    output_group.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

def setup_tts_args(parser: argparse.ArgumentParser) -> None:
    """TTS関連の引数を設定"""
    tts_group = parser.add_argument_group('TTS Settings')
    tts_group.add_argument(
        "--tts-enabled",
        action="store_true",
        help="Enable text-to-speech output"
    )
    tts_group.add_argument(
        "--tts-model",
        type=str,
        default="parler-tts/parler-tts-mini-v1",
        help="Model tag for Parler TTS"
    )
    tts_group.add_argument(
        "--tts-device",
        type=str,
        default="cpu",
        choices=["cpu", "cuda"],
        help="Device for TTS inference"
    )
    tts_group.add_argument(
        "--voice-description",
        type=str,
        default="The voice is clear and natural, with a professional tone and moderate pace.",
        help="Description of the voice characteristics for TTS"
    )

def get_parser_transcription() -> argparse.ArgumentParser:
    """文字起こし用の引数パーサーを取得"""
    parser = argparse.ArgumentParser(
        description="Real-time Audio Transcription",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    setup_model_args(parser)
    setup_audio_args(parser)
    setup_language_args(parser, translation=False)
    setup_output_args(parser)
    
    return parser

def get_parser_translation() -> argparse.ArgumentParser:
    """翻訳付き文字起こし用の引数パーサーを取得"""
    parser = argparse.ArgumentParser(
        description="Real-time Audio Recognition with Translation and TTS",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    setup_model_args(parser)
    setup_audio_args(parser)
    setup_language_args(parser, translation=True)
    setup_output_args(parser)
    setup_llm_args(parser)
    setup_tts_args(parser)
    
    return parser

def parse_args_transcription() -> argparse.Namespace:
    """文字起こし用の引数をパース"""
    return get_parser_transcription().parse_args()

def parse_args_translation() -> argparse.Namespace:
    """翻訳付き文字起こし用の引数をパース"""
    return get_parser_translation().parse_args()

