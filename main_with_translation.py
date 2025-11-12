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

# Logging
from utils.logger import setup_logger

# クリーン統合版ConfigManager
from config_manager import ConfigManager

# 既存モジュール（クリーン対応版）
from audio.capture import AudioCapture
from audio.processing import AudioProcessing
from recognition.speech_recognition import SpeechRecognition
from translation.translator import Translation
from utils.resource_manager import ResourceManager

# TTS（オプショナル）
try:
    from tts import TextToSpeech
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# Web UI Bridge（オプショナル）
try:
    from web_ui_bridge import WebUIBridge
    WEB_UI_AVAILABLE = True
except ImportError:
    WEB_UI_AVAILABLE = False

# グローバルシステムインスタンス（Web UIから停止・設定リロードするため）
# スレッドセーフなアクセスを保証するためのロック
import threading
_system_instance = None
_system_instance_lock = threading.Lock()
_config_manager_instance = None

# Setup logger
logger = setup_logger(__name__)


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

        logger.info("="*60)
        logger.info("音声認識＋翻訳システムを起動しています...")
        logger.info("="*60)
        if self.debug:
            logger.info("デバッグモード: 有効")

        for thread in threads:
            thread.start()

        logger.info("システムが起動しました。終了するには Ctrl+C を押してください。")

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

        logger.info("プログラムを終了しました。")


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
        logger.error(f"設定ファイルが見つかりません: {config_path}")
        logger.error(f"   カレントディレクトリ: {Path.cwd()}")
        logger.error("ヒント: --config オプションで設定ファイルのパスを指定してください")
        sys.exit(1)
    
    try:
        # =====================================
        # ConfigManagerの初期化
        # =====================================
        logger.info("設定を読み込んでいます...")
        logger.info(f"   設定ファイル: {config_path}")
        logger.info(f"   プロファイル: {args.profile}")

        config = ConfigManager(
            config_path=str(config_path),
            profile=args.profile
        )

        # グローバル変数に保存（Web UIから設定リロードできるようにする）
        global _config_manager_instance
        _config_manager_instance = config

        # コマンドライン引数による上書き（公式 API を使用）
        if args.output_dir:
            config.set_output_dir(args.output_dir)
            logger.info(f"   出力ディレクトリを上書き: {args.output_dir}")

        if args.batch_size:
            config.set_batch_size(args.batch_size)
            logger.info(f"   バッチサイズを上書き: {args.batch_size}")

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
        if args.source_lang or args.target_lang:
            source = args.source_lang or config.language.source
            target = args.target_lang or config.language.target
            config.set_language(source, target)
            if args.source_lang:
                logger.info(f"   入力言語を上書き: {args.source_lang}")
            if args.target_lang:
                logger.info(f"   出力言語を上書き: {args.target_lang}")
        
        # =====================================
        # 設定の表示
        # =====================================
        logger.info("")
        logger.info("システム設定:")
        logger.info(f"   言語: {config.language.source} → {config.language.target}")
        logger.info(f"   音声: {config.audio.sample_rate}Hz, {config.audio.channels}ch, {config.audio.format_str}")
        logger.info(f"   ASRモデル: {config.get_model_config('asr').model_size}")
        # 翻訳モデルの最終的な「実行対象」を ModelConfig / GGUFConfig から決定（config_manager に準拠）
        tconf = config.get_model_config('translation')  # ModelConfig

        def _is_hub_id(s: str) -> bool:
            return ("/" in s) and ("\\" not in s) and (":" not in s)

        if tconf.gguf and tconf.gguf.enabled:
            # GGUF 優先：repo(=gguf.model_path) + file(=gguf.model_file)
            repo  = (tconf.gguf.model_path or "").strip()
            gfile = (tconf.gguf.model_file or "").strip()
            if repo.lower().endswith(".gguf") and not gfile:
                p = Path(repo)
                logger.info(f"   翻訳モデル: {p.stem}  [GGUF]")
                logger.info(f"   参照元   : {p}")
            else:
                if _is_hub_id(repo):
                    name = Path(gfile).stem or repo
                    src  = f"hf://{repo.rstrip('/')}/{gfile}" if gfile else f"hf://{repo}"
                    logger.info(f"   翻訳モデル: {name}  [GGUF]")
                    logger.info(f"   参照元   : {src}")
                else:
                    p = Path(repo) / gfile if gfile else Path(repo)
                    name = Path(gfile).stem if gfile else (p.stem or p.name)
                    logger.info(f"   翻訳モデル: {name}  [GGUF]")
                    logger.info(f"   参照元   : {p}")
            # 実行パラメータ表示（見える化）
            logger.info(f"   n_ctx    : {tconf.gguf.n_ctx}")
            logger.info(f"   n_gpu_layers: {tconf.gguf.n_gpu_layers}")
            logger.info(f"   n_threads: {tconf.gguf.n_threads}")
        else:
            # 通常（HF/Local）の model_path は ModelConfig.model_path から
            m = tconf.model_path
            if not m:
                logger.info("   翻訳モデル: （未設定）")
                logger.info("   参照元   : （未設定）")
            else:
                s = str(m)
                if _is_hub_id(s):
                    logger.info(f"   翻訳モデル: {s}  [HF Hub]")
                    logger.info(f"   参照元   : hf://{s}")
                else:
                    p = Path(s)
                    logger.info(f"   翻訳モデル: {p.name or s}  [Local]")
                    logger.info(f"   参照元   : {p}")

        logger.info(f"   バッチサイズ: {config.translation.batch_size}")
        logger.info(f"   出力先: {config.output.directory}")
        
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
        logger.info("")
        logger.info("コンポーネントを初期化しています...")
        
        # 直接AudioConfigデータクラスを渡す
        audio_capture = AudioCapture(config.audio, audio_queue, config.audio)
        audio_processing = AudioProcessing(config.audio, audio_queue, processing_queue)
        # Web UI Bridge初期化（オプショナル）- SpeechRecognitionより前に初期化
        web_ui = None
        if args.web_ui and WEB_UI_AVAILABLE:
            try:
                web_ui = WebUIBridge(
                    server_url=args.web_ui_url,
                    enabled=True
                )
                logger.info("")
                logger.info("Web UI連携を有効化しました: {args.web_ui_url}")
                # Note: Web UIサーバー側で"running"ステータスを送信するため、
                # ここでは初期ステータスを送信しない
                # web_ui.send_status("stopped", "System initialized")
            except Exception as e:
                logger.warning(f" Web UI Bridge initialization failed: {e}")
                web_ui = None

        speech_recognition = SpeechRecognition(
            config.audio,
            processing_queue,
            translation_queue,
            config,  # ConfigManagerを渡す
            config.language,
            debug=debug_mode,
            web_ui=web_ui  # Web UIブリッジを渡す
        )
        # TTS初期化（オプショナル）
        tts = None
        if TTS_AVAILABLE and config.tts.enabled:
            try:
                tts = TextToSpeech(
                    config.tts,
                    debug=debug_mode,
                    target_language=config.language.target
                )
            except Exception as e:
                logger.warning(f" TTS initialization failed: {e}")
                tts = None

        translation = Translation(
            translation_queue,
            config,  # ConfigManagerを渡す
            config.language,
            debug=debug_mode,
            tts=tts,  # TTSモジュールを渡す
            web_ui=web_ui  # Web UIブリッジを渡す
        )
        
        # =====================================
        # システムの起動
        # =====================================
        global _system_instance
        with _system_instance_lock:
            _system_instance = AudioRecognitionSystem(
                audio_capture,
                audio_processing,
                speech_recognition,
                translation,
                resource_manager,
                debug=debug_mode
            )
        _system_instance.run()
        
    except FileNotFoundError as e:
        logger.error("")
        logger.error(f"エラー: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error("")
        logger.error(f"予期しないエラーが発生しました: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
