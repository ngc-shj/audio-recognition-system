#!/usr/bin/env python3
"""
Audio Transcription System
音声文字起こしシステム
"""

import sys
import argparse
import threading
import time
import queue
from pathlib import Path

from config_manager import ConfigManager

from audio.capture import AudioCapture
from audio.processing import AudioProcessing
from recognition.speech_recognition import SpeechRecognition
from utils.resource_manager import ResourceManager

# Web UI Bridge (オプショナル)
try:
    from web_ui_bridge import WebUIBridge
    WEB_UI_AVAILABLE = True
except ImportError:
    WEB_UI_AVAILABLE = False


class AudioTranscriptionSystem:
    """音声文字起こしシステムのメインクラス"""
    
    def __init__(self, audio_capture, audio_processing, speech_recognition, 
                 resource_manager, debug=False):
        self.audio_capture = audio_capture
        self.audio_processing = audio_processing
        self.speech_recognition = speech_recognition
        self.resource_manager = resource_manager
        self.debug = debug
        self.is_running = threading.Event()
        self.is_running.set()

    def run(self):
        """システムを起動"""
        threads = [
            threading.Thread(target=self.audio_capture.capture_thread, args=(self.is_running,)),
            threading.Thread(target=self.audio_processing.processing_thread, args=(self.is_running,)),
            threading.Thread(target=self.speech_recognition.recognition_thread, args=(self.is_running,))
        ]
        
        print("\n" + "="*60)
        print("音声文字起こしシステムを起動しています...")
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

        # スレッド終了を待機（タイムアウト: 2秒）
        for thread in threads:
            thread.join(timeout=2.0)

        print("\nプログラムを終了しました。\n")


def parse_arguments():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="Real-time Audio Transcription (Clean Unified)",
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
        "--debug",
        action="store_true",
        help="デバッグモードを有効化"
    )
    parser.add_argument(
        "--web-ui",
        action="store_true",
        help="Web UIとの連携を有効化"
    )
    parser.add_argument(
        "--web-ui-url",
        type=str,
        default="http://localhost:8000",
        help="Web UIサーバーのURL"
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
        
        # コマンドライン引数による上書き（公式 API を使用）
        if args.output_dir:
            config.set_output_dir(args.output_dir)
            print(f"   出力ディレクトリを上書き: {args.output_dir}")

        if args.model_size:
            # ASRモデルサイズの上書き（platform 固有）
            if 'models' not in config._config:
                config._config['models'] = {}
            if 'asr' not in config._config['models']:
                config._config['models']['asr'] = {}
            if config.platform not in config._config['models']['asr']:
                config._config['models']['asr'][config.platform] = {}
            config._config['models']['asr'][config.platform]['model_size'] = args.model_size
            print(f"   モデルサイズを上書き: {args.model_size}")

        if args.debug:
            config.set_debug(True)
            print(f"   デバッグモードを上書き: 有効")

        # 言語設定の上書き（公式 API を使用）
        if args.source_lang:
            config.set_language(args.source_lang, config.language.target)
            print(f"   入力言語を上書き: {args.source_lang}")
        
        # =====================================
        # 設定の表示
        # =====================================
        print(f"\nシステム設定:")
        print(f"   言語: {config.language.source}")
        print(f"   音声: {config.audio.sample_rate}Hz, {config.audio.channels}ch, {config.audio.format_str}")
        print(f"   ASRモデル: {config.get_model_config('asr').model_size}")
        print(f"   出力先: {config.output.directory}")
        
        debug_mode = config.is_debug_enabled()

        # =====================================
        # Web UI Bridge の初期化
        # =====================================
        web_ui = None
        if args.web_ui and WEB_UI_AVAILABLE:
            try:
                web_ui = WebUIBridge(
                    server_url=args.web_ui_url,
                    enabled=True
                )
                print(f"\nWeb UI連携を有効化しました: {args.web_ui_url}")
                web_ui.send_status("stopped", "System initialized")
            except Exception as e:
                print(f"Warning: Web UI Bridge initialization failed: {e}")
                web_ui = None
        elif args.web_ui and not WEB_UI_AVAILABLE:
            print("\nWarning: Web UI Bridge is not available. Install required dependencies.")

        # =====================================
        # リソースマネージャー
        # =====================================
        resource_manager = ResourceManager(config)
        
        # =====================================
        # キューの作成
        # =====================================
        audio_queue = queue.Queue()
        processing_queue = queue.Queue()
        
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
            None,  # 翻訳なし
            config,  # ConfigManagerを渡す
            config.language,
            debug=debug_mode,
            web_ui=web_ui  # Web UI Bridge
        )
        
        # =====================================
        # システムの起動
        # =====================================
        system = AudioTranscriptionSystem(
            audio_capture, 
            audio_processing, 
            speech_recognition,
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
