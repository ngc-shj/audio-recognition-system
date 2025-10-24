#!/usr/bin/env python3
"""
Audio Recognition System with Translation (Clean Unified)
音声認識＋翻訳システム（クリーン統合版完全対応）
"""

import sys
import argparse
import threading
import time
import queue
from pathlib import Path

# クリーン統合版ConfigManager
from config_manager import ConfigManager

# 既存モジュール（クリーン対応版）
from audio.capture import AudioCapture
from audio.processing import AudioProcessing
from recognition.speech_recognition import SpeechRecognition
from translation.translator import Translation
from utils.resource_manager import ResourceManager


class AudioRecognitionSystem:
    """音声認識＋翻訳システムのメインクラス"""
    
    def __init__(self, audio_capture, audio_processing, speech_recognition, 
                 translation, resource_manager, debug=False):
        self.audio_capture = audio_capture
        self.audio_processing = audio_processing
        self.speech_recognition = speech_recognition
        self.translation = translation
        self.resource_manager = resource_manager
        self.debug = debug
        self.is_running = threading.Event()
        self.is_running.set()

    def run(self):
        """システムを起動"""
        threads = [
            threading.Thread(target=self.audio_capture.capture_thread, args=(self.is_running,)),
            threading.Thread(target=self.audio_processing.processing_thread, args=(self.is_running,)),
            threading.Thread(target=self.speech_recognition.recognition_thread, args=(self.is_running,)),
            threading.Thread(target=self.translation.translation_thread, args=(self.is_running,))
        ]
        
        print("\n" + "="*60)
        print("音声認識＋翻訳システムを起動しています...")
        print("="*60)
        if self.debug:
            print("デバッグモード: 有効")
        
        for thread in threads:
            thread.start()
        
        print("システムが起動しました。終了するには Ctrl+C を押してください。\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n" + "="*60)
            print("終了しています。しばらくお待ちください...")
            print("="*60)
            self.is_running.clear()
        
        for thread in threads:
            thread.join()
        
        print("\nプログラムを終了しました。\n")


def parse_arguments():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="Real-time Audio Recognition with Translation (Clean Unified)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="設定ファイルのパス"
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="production",
        choices=["development", "production", "testing"],
        help="使用するプロファイル"
    )
    parser.add_argument(
        "--source-lang",
        type=str,
        help="音声認識の入力言語 (例: 'en', 'ja')"
    )
    parser.add_argument(
        "--target-lang",
        type=str,
        help="翻訳の出力言語 (例: 'en', 'ja')"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="ログファイルの出力ディレクトリ"
    )
    parser.add_argument(
        "--model-size",
        type=str,
        choices=["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo", "turbo"],
        help="Whisperモデルのサイズ"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="翻訳のバッチサイズ"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグモードを有効化"
    )
    
    return parser.parse_args()


def main():
    """メイン関数"""
    args = parse_arguments()
    
    # 設定ファイルの存在確認
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"エラー: 設定ファイルが見つかりません: {config_path}")
        print(f"   カレントディレクトリ: {Path.cwd()}")
        print(f"\nヒント: --config オプションで設定ファイルのパスを指定してください")
        sys.exit(1)
    
    try:
        # =====================================
        # ConfigManagerの初期化
        # =====================================
        print(f"\n設定を読み込んでいます...")
        print(f"   設定ファイル: {config_path}")
        print(f"   プロファイル: {args.profile}")
        
        config = ConfigManager(
            config_path=str(config_path),
            profile=args.profile
        )
        
        # コマンドライン引数による上書き
        if args.output_dir:
            config._config['output']['directory'] = args.output_dir
            config._output = None  # キャッシュをクリア
            print(f"   出力ディレクトリを上書き: {args.output_dir}")
        
        if args.batch_size:
            config._config['translation']['batch_size'] = args.batch_size
            config._translation = None  # キャッシュをクリア
            print(f"   バッチサイズを上書き: {args.batch_size}")
        
        if args.model_size:
            platform = config.platform
            config._config['models']['asr'][platform]['model_size'] = args.model_size
            print(f"   モデルサイズを上書き: {args.model_size}")
        
        if args.debug:
            config._config['debug']['enabled'] = True
            print(f"   デバッグモードを上書き: 有効")
        
        # 言語設定の上書き
        if args.source_lang:
            config._config['language']['source'] = args.source_lang
            config._language = None  # キャッシュをクリア
            print(f"   入力言語を上書き: {args.source_lang}")
        
        if args.target_lang:
            config._config['language']['target'] = args.target_lang
            config._language = None  # キャッシュをクリア
            print(f"   出力言語を上書き: {args.target_lang}")
        
        # =====================================
        # 設定の表示
        # =====================================
        print(f"\nシステム設定:")
        print(f"   言語: {config.language.source} → {config.language.target}")
        print(f"   音声: {config.audio.sample_rate}Hz, {config.audio.channels}ch, {config.audio.format_str}")
        print(f"   ASRモデル: {config.get_model_config('asr').model_size}")
        print(f"   翻訳モデル: {config.get_model_config('translation').model_path}")
        print(f"   バッチサイズ: {config.translation.batch_size}")
        print(f"   出力先: {config.output.directory}")
        
        debug_mode = config.is_debug_enabled()
        
        # =====================================
        # リソースマネージャー
        # =====================================
        resource_manager = ResourceManager(config)
        
        # =====================================
        # キューの作成
        # =====================================
        audio_queue = queue.Queue()
        processing_queue = queue.Queue()
        translation_queue = queue.Queue()
        
        # =====================================
        # コンポーネントの初期化
        # =====================================
        print(f"\nコンポーネントを初期化しています...")
        
        # 直接AudioConfigデータクラスを渡す
        audio_capture = AudioCapture(config.audio, audio_queue, config.audio)
        audio_processing = AudioProcessing(config.audio, audio_queue, processing_queue)
        speech_recognition = SpeechRecognition(
            config.audio, 
            processing_queue, 
            translation_queue,
            config,  # ConfigManagerを渡す
            config.language,
            debug=debug_mode
        )
        translation = Translation(
            translation_queue, 
            config,  # ConfigManagerを渡す
            config.language,
            debug=debug_mode
        )
        
        # =====================================
        # システムの起動
        # =====================================
        system = AudioRecognitionSystem(
            audio_capture, 
            audio_processing, 
            speech_recognition,
            translation, 
            resource_manager, 
            debug=debug_mode
        )
        system.run()
        
    except FileNotFoundError as e:
        print(f"\nエラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n予期しないエラーが発生しました: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
