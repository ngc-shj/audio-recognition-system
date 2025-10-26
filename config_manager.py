"""
設定管理モジュール

YAMLファイルから設定を読み込み、プラットフォーム依存の設定を適切に処理します。
環境変数、コマンドライン引数、プロファイル機能をサポートします。
"""

import sys
import os
import yaml
import pyaudio
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AudioConfig:
    """音声設定データクラス"""
    format_str: str
    format: int
    sample_rate: int
    channels: int
    chunk_size: int
    buffer_duration: float
    numpy_dtype: type
    buffer_size: int
    silence_threshold: float
    voice_activity_threshold: float
    silence_duration: float
    input_device: Optional[int] = None


@dataclass
class ModelConfig:
    """モデル設定データクラス"""
    model_path: str
    model_size: Optional[str] = None


@dataclass
class TranslationConfig:
    """翻訳設定データクラス"""
    enabled: bool
    batch_size: int
    context_window_size: int
    context_separator: str
    generation_params: Dict[str, Any]
    reload_interval: int
    max_consecutive_errors: int
    error_cooldown: int


@dataclass
class OutputConfig:
    """出力設定データクラス"""
    directory: str
    recognized_audio: bool
    translated_text: bool
    bilingual_log: bool
    timestamp_format: str


@dataclass
class LanguageConfig:
    """言語設定データクラス"""
    source: str
    target: str
    
    # 後方互換性のためのエイリアス
    @property
    def source_lang(self) -> str:
        """後方互換性: source_lang → source"""
        return self.source
    
    @property
    def target_lang(self) -> str:
        """後方互換性: target_lang → target"""
        return self.target
    
    @staticmethod
    def get_language_name(lang_code: str) -> str:
        """
        言語コードから言語名を取得
        
        Args:
            lang_code: 言語コード ('en', 'ja', etc.)
        
        Returns:
            言語名
        """
        language_names = {
            'ja': '日本語',
            'en': '英語',
            'zh': '中国語',
            'ko': '韓国語',
            'fr': 'フランス語',
            'de': 'ドイツ語',
            'es': 'スペイン語',
            'it': 'イタリア語',
            'ru': 'ロシア語',
            'ar': 'アラビア語',
            'pt': 'ポルトガル語',
            'hi': 'ヒンディー語',
        }
        return language_names.get(lang_code, lang_code)


@dataclass
class ResourceConfig:
    """リソース設定データクラス"""
    min_threads: int
    max_threads: int


class ConfigManager:
    """
    統合設定管理クラス（クリーン版）
    
    YAMLファイルから設定を読み込み、すべての設定を型安全なデータクラスで提供します。
    後方互換性は考慮せず、モダンでシンプルなAPIを提供します。
    
    使用例:
        config = ConfigManager()
        print(config.audio.sample_rate)
        print(config.translation.batch_size)
        print(config.language.source)
    """
    
    def __init__(self, config_path: Optional[str] = None, profile: str = "production"):
        """
        Args:
            config_path: 設定ファイルのパス（Noneの場合はデフォルト）
            profile: 使用するプロファイル名 (development, production, testing)
        """
        self.profile = profile
        self.platform = self._detect_platform()
        
        # 設定ファイルの読み込み
        if config_path is None:
            config_path = self._find_default_config()
        
        self._config = self._load_config(config_path)
        
        # プロファイルの適用
        self._apply_profile()
        
        # 環境変数による上書き
        self._apply_env_overrides()
        
        # 設定データクラスの初期化（遅延ロード用のキャッシュ）
        self._audio = None
        self._translation = None
        self._output = None
        self._language = None
        self._resources = None
    
    @staticmethod
    def _detect_platform() -> str:
        """プラットフォームを検出"""
        if sys.platform == 'darwin':
            return 'darwin'
        return 'default'
    
    @staticmethod
    def _find_default_config() -> str:
        """デフォルトの設定ファイルを探す"""
        possible_paths = [
            'config.yaml',
            'config/config.yaml',
            'configs/config.yaml',
            os.path.join(os.path.dirname(__file__), 'config.yaml'),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        raise FileNotFoundError(
            "設定ファイルが見つかりません。以下のパスを確認してください:\n" + 
            "\n".join(f"  - {p}" for p in possible_paths)
        )
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """YAML設定ファイルを読み込む"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"設定ファイルを読み込みました: {config_path}")
            return config
        except Exception as e:
            raise RuntimeError(f"設定ファイルの読み込みに失敗しました: {e}")
    
    def _apply_profile(self):
        """プロファイル設定を適用"""
        if 'profiles' in self._config and self.profile in self._config['profiles']:
            profile_config = self._config['profiles'][self.profile]
            self._deep_merge(self._config, profile_config)
            print(f"プロファイルを適用しました: {self.profile}")
    
    def _deep_merge(self, base: Dict, override: Dict):
        """辞書を再帰的にマージ"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _apply_env_overrides(self):
        """環境変数による設定の上書き"""
        env_mappings = {
            'AUDIO_SAMPLE_RATE': ('audio', 'sample_rate'),
            'AUDIO_CHANNELS': ('audio', 'channels'),
            'MODEL_SIZE': ('models', 'asr', self.platform, 'model_size'),
            'TRANSLATION_BATCH_SIZE': ('translation', 'batch_size'),
            'OUTPUT_DIR': ('output', 'directory'),
            'DEBUG': ('debug', 'enabled'),
        }
        
        for env_var, config_path in env_mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                # 型変換
                if env_var in ['AUDIO_SAMPLE_RATE', 'AUDIO_CHANNELS', 'TRANSLATION_BATCH_SIZE']:
                    value = int(value)
                elif env_var == 'DEBUG':
                    value = value.lower() in ('true', '1', 'yes')
                
                self._set_nested_value(config_path, value)
    
    def _set_nested_value(self, path: tuple, value: Any):
        """ネストされた設定値をセット"""
        current = self._config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """
        設定値を取得（プラットフォーム依存の値を自動選択）
        
        Args:
            *keys: 設定キーのパス
            default: デフォルト値
        
        Returns:
            設定値
        """
        current = self._config
        
        for key in keys:
            if not isinstance(current, dict):
                return default
            
            # プラットフォーム依存の設定を優先
            if self.platform in current and key != self.platform:
                platform_value = current[self.platform].get(key) if isinstance(current[self.platform], dict) else None
                if platform_value is not None:
                    return platform_value
            
            if key in current:
                current = current[key]
            else:
                return default
        
        # プラットフォーム固有の値がある場合はそれを返す
        if isinstance(current, dict) and self.platform in current:
            return current[self.platform]
        
        return current
    
    # =====================================
    # 設定取得メソッド（型安全）
    # =====================================
    
    @staticmethod
    def _get_format_from_string(format_str: str) -> int:
        """フォーマット文字列からPyAudioのフォーマット定数に変換"""
        format_dict = {
            'int8': pyaudio.paInt8,
            'int16': pyaudio.paInt16,
            'int32': pyaudio.paInt32,
            'float32': pyaudio.paFloat32
        }
        return format_dict.get(format_str.lower(), pyaudio.paInt16)
    
    @staticmethod
    def _get_numpy_dtype(format: int):
        """PyAudioフォーマットからNumPyのdtypeに変換"""
        dtype_map = {
            pyaudio.paInt8: np.int8,
            pyaudio.paInt16: np.int16,
            pyaudio.paInt32: np.int32,
            pyaudio.paFloat32: np.float32,
        }
        if format not in dtype_map:
            raise ValueError(f"Unsupported audio format: {format}")
        return dtype_map[format]
    
    @property
    def audio(self) -> AudioConfig:
        """音声設定を取得（キャッシュあり）"""
        if self._audio is None:
            format_str = self.get('audio', 'format')
            format_val = self._get_format_from_string(format_str)
            sample_rate = self.get('audio', 'sample_rate')
            buffer_duration = self.get('audio', 'buffer_duration')
            
            self._audio = AudioConfig(
                format_str=format_str,
                format=format_val,
                sample_rate=sample_rate,
                channels=self.get('audio', 'channels'),
                chunk_size=self.get('audio', 'chunk_size'),
                buffer_duration=buffer_duration,
                numpy_dtype=self._get_numpy_dtype(format_val),
                buffer_size=int(sample_rate * buffer_duration),
                silence_threshold=self.get('audio', 'voice_detection', 'silence_threshold'),
                voice_activity_threshold=self.get('audio', 'voice_detection', 'voice_activity_threshold'),
                silence_duration=self.get('audio', 'voice_detection', 'silence_duration'),
                input_device=self.get('audio', 'input_device'),
            )
        
        return self._audio
    
    def get_model_config(self, model_type: str) -> ModelConfig:
        """
        モデル設定を取得
        
        Args:
            model_type: 'asr' または 'translation'
        
        Returns:
            ModelConfig
        """
        # models.asr または models.translation を取得
        if 'models' not in self._config or model_type not in self._config['models']:
            return ModelConfig(model_path=None, model_size=None)
        
        model_config = self._config['models'][model_type]
        
        # プラットフォーム固有の設定を取得
        if self.platform in model_config:
            platform_config = model_config[self.platform]
        elif 'default' in model_config:
            platform_config = model_config['default']
        else:
            platform_config = {}
        
        return ModelConfig(
            model_path=platform_config.get('model_path'),
            model_size=platform_config.get('model_size')
        )
    
    @property
    def translation(self) -> TranslationConfig:
        """翻訳設定を取得（キャッシュあり）"""
        if self._translation is None:
            # プラットフォーム固有の生成パラメータを取得
            gen_config = self._config.get('translation', {}).get('generation', {})
            if self.platform in gen_config:
                gen_params = gen_config[self.platform]
            elif 'default' in gen_config:
                gen_params = gen_config['default']
            else:
                gen_params = {}
            
            # reload_intervalの取得
            reload_config = self._config.get('models', {}).get('translation', {}).get('reload', {})
            if self.platform == 'darwin' and 'interval_seconds_darwin' in reload_config:
                reload_interval = reload_config['interval_seconds_darwin']
            else:
                reload_interval = reload_config.get('interval_seconds', 3600)
            
            # error_handlingの取得
            error_config = self._config.get('models', {}).get('translation', {}).get('error_handling', {})
            
            self._translation = TranslationConfig(
                enabled=self._config.get('translation', {}).get('enabled', True),
                batch_size=self._config.get('translation', {}).get('batch_size', 5),
                context_window_size=self._config.get('translation', {}).get('context', {}).get('window_size', 8),
                context_separator=self._config.get('translation', {}).get('context', {}).get('separator', '\n'),
                generation_params=gen_params,
                reload_interval=reload_interval,
                max_consecutive_errors=error_config.get('max_consecutive_errors', 5),
                error_cooldown=error_config.get('error_cooldown_seconds', 10),
            )
        
        return self._translation
    
    @property
    def output(self) -> OutputConfig:
        """出力設定を取得（キャッシュあり）"""
        if self._output is None:
            self._output = OutputConfig(
                directory=self.get('output', 'directory'),
                recognized_audio=self.get('output', 'logging', 'recognized_audio'),
                translated_text=self.get('output', 'logging', 'translated_text'),
                bilingual_log=self.get('output', 'logging', 'bilingual_log'),
                timestamp_format=self.get('output', 'filename_format', 'timestamp'),
            )
        
        return self._output
    
    @property
    def language(self) -> LanguageConfig:
        """言語設定を取得（キャッシュあり）"""
        if self._language is None:
            self._language = LanguageConfig(
                source=self.get('language', 'source'),
                target=self.get('language', 'target')
            )
        
        return self._language
    
    @property
    def resources(self) -> ResourceConfig:
        """リソース設定を取得（キャッシュあり）"""
        if self._resources is None:
            self._resources = ResourceConfig(
                min_threads=self.get('resources', 'threads', 'min', default=2),
                max_threads=self.get('resources', 'threads', 'max', default=8),
            )
        
        return self._resources
    
    def is_debug_enabled(self) -> bool:
        """デバッグモードが有効か"""
        return self.get('debug', 'enabled', default=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書として取得（デバッグ用）"""
        return self._config.copy()
    
    def __repr__(self):
        """デバッグ用の文字列表現"""
        return (
            f"ConfigManager("
            f"profile={self.profile}, "
            f"platform={self.platform})"
        )


# 使用例とテスト
if __name__ == "__main__":
    print("=== ConfigManager (クリーン統合版) のテスト ===\n")
    
    # 初期化
    config = ConfigManager(profile="development")
    
    print(f"基本情報:")
    print(f"  プロファイル: {config.profile}")
    print(f"  プラットフォーム: {config.platform}")
    
    print("\n🎵 音声設定:")
    audio = config.audio
    print(f"  サンプルレート: {audio.sample_rate} Hz")
    print(f"  チャンネル: {audio.channels}")
    print(f"  フォーマット: {audio.format_str}")
    print(f"  バッファサイズ: {audio.buffer_size}")
    print(f"  NumPy dtype: {audio.numpy_dtype}")
    
    print("\nモデル設定:")
    asr_model = config.get_model_config('asr')
    print(f"  ASRモデル: {asr_model.model_path}")
    print(f"  モデルサイズ: {asr_model.model_size}")
    
    trans_model = config.get_model_config('translation')
    print(f"  翻訳モデル: {trans_model.model_path}")
    
    print("\n翻訳設定:")
    trans = config.translation
    print(f"  有効: {trans.enabled}")
    print(f"  バッチサイズ: {trans.batch_size}")
    print(f"  コンテキストウィンドウ: {trans.context_window_size}")
    
    print("\n言語設定:")
    lang = config.language
    print(f"  {lang.source} → {lang.target}")
    
    print("\n出力設定:")
    output = config.output
    print(f"  ディレクトリ: {output.directory}")
    print(f"  音声認識ログ: {output.recognized_audio}")
    print(f"  翻訳ログ: {output.translated_text}")
    
    print("\nリソース設定:")
    res = config.resources
    print(f"  スレッド: {res.min_threads}-{res.max_threads}")
    
    print("\nすべての設定が型安全に取得できます！")

