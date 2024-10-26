from dataclasses import dataclass

@dataclass
class LanguageConfig:
    """言語設定を管理するデータクラス"""
    source_lang: str  # 音声認識および翻訳元の言語
    target_lang: str  # 翻訳先言語
    
    @staticmethod
    def get_language_name(lang_code: str) -> str:
        """言語コードから言語名を取得"""
        LANGUAGE_NAMES = {
            'ja': '日本語',
            'en': '英語',
            'zh': '中国語',
            'ko': '韓国語',
            'fr': 'フランス語',
            'de': 'ドイツ語',
            'es': 'スペイン語',
            'it': 'イタリア語',
        }
        return LANGUAGE_NAMES.get(lang_code, lang_code)

