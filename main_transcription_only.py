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

# Logging
from utils.logger import setup_logger

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

# グローバルシステムインスタンス（Web UIから停止するため）
_system_instance = None

# Setup logger
logger = setup_logger(__name__)


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
        
        logger.info("")
        logger.info("="*60)
        logger.info("音声文字起こしシステムを起動しています...")
        logger.info("="*60)
        if self.debug:
            logger.info("デバッグモード: 有効")
        
        for thread in threads:
            thread.start()
        
        logger.info("システムが起動しました。終了するには Ctrl+C を押してください。\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("")
            logger.info("="*60)
            logger.info("終了しています。しばらくお待ちください...")
            logger.info("="*60)
            self.is_running.clear()

        # スレッド終了を待機（タイムアウト: 3秒）
        # Longer timeout to ensure PyAudio callbacks complete properly
        for thread in threads:
            thread.join(timeout=3.0)

        logger.info("")
        logger.info("プログラムを終了しました。\n")


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
        logger.error(f" 設定ファイルが見つかりません: {config_path}")
        logger.info(f"   カレントディレクトリ: {Path.cwd()}")
        logger.info("")
        logger.info(f"ヒント: --config オプションで設定ファイルのパスを指定してください")
        sys.exit(1)
    
    try:
        # =====================================
        # ConfigManagerの初期化
        # =====================================
        logger.info("")
        logger.info(f"設定を読み込んでいます...")
        logger.info(f"   設定ファイル: {config_path}")
        logger.info(f"   プロファイル: {args.profile}")
        
        config = ConfigManager(
            config_path=str(config_path),
            profile=args.profile
        )
        
        # コマンドライン引数による上書き（公式 API を使用）
        if args.output_dir:
            config.set_output_dir(args.output_dir)
            logger.info(f"   出力ディレクトリを上書き: {args.output_dir}")

        if args.model_size:
            # ASRモデルサイズの上書き（platform 固有）
            if 'models' not in config._config:
                config._config['models'] = {}
            if 'asr' not in config._config['models']:
                config._config['models']['asr'] = {}
            if config.platform not in config._config['models']['asr']:
                config._config['models']['asr'][config.platform] = {}
            config._config['models']['asr'][config.platform]['model_size'] = args.model_size
            logger.info(f"   モデルサイズを上書き: {args.model_size}")

        if args.debug:
            config.set_debug(True)
            logger.info(f"   デバッグモードを上書き: 有効")

        # 言語設定の上書き（公式 API を使用）
        if args.source_lang:
            config.set_language(args.source_lang, config.language.target)
            logger.info(f"   入力言語を上書き: {args.source_lang}")
        
        # =====================================
        # 設定の表示
        # =====================================
        logger.info("")
        logger.info(f"システム設定:")
        logger.info(f"   言語: {config.language.source}")
        logger.info(f"   音声: {config.audio.sample_rate}Hz, {config.audio.channels}ch, {config.audio.format_str}")
        logger.info(f"   ASRモデル: {config.get_model_config('asr').model_size}")
        logger.info(f"   出力先: {config.output.directory}")
        
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
                logger.info("")
                logger.info(f"Web UI連携を有効化しました: {args.web_ui_url}")
                # Note: Web UIサーバー側で"running"ステータスを送信するため、
                # ここでは初期ステータスを送信しない
                # web_ui.send_status("stopped", "System initialized")
            except Exception as e:
                logger.warning(f" Web UI Bridge initialization failed: {e}")
                web_ui = None
        elif args.web_ui and not WEB_UI_AVAILABLE:
            logger.info("\nWarning: Web UI Bridge is not available. Install required dependencies.")

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
        logger.info("")
        logger.info(f"コンポーネントを初期化しています...")
        
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
        global _system_instance
        _system_instance = AudioTranscriptionSystem(
            audio_capture,
            audio_processing,
            speech_recognition,
            resource_manager,
            debug=debug_mode
        )
        _system_instance.run()
        
    except FileNotFoundError as e:
        logger.info("")
        logger.info(f"エラー: {e}")
        sys.exit(1)
    except Exception as e:
        logger.info("")
        logger.info(f"予期しないエラーが発生しました: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
