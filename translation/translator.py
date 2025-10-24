"""
Translation Module
翻訳モジュール
"""

import sys
import os
import datetime
import queue
import time
import gc
import torch
from collections import deque
from typing import Dict

if sys.platform == 'darwin':
    try:
        from mlx_lm import load, generate
        from mlx_lm.sample_utils import make_sampler, make_logits_processors
    except ImportError as e:
        print(f"ERROR: Failed to import MLX sampling utilities: {e}", file=sys.stderr)
        raise
else:
    from transformers import AutoModelForCausalLM, AutoTokenizer, logging


class Translation:
    """
    翻訳クラス
    
    ConfigManagerから設定を取得し、LLMで翻訳を実行します。
    """
    
    def __init__(self, translation_queue, config_manager, lang_config, debug=False):
        """
        Args:
            translation_queue: 翻訳待ちテキストのキュー
            config_manager: ConfigManager または互換アダプター
            lang_config: LanguageConfig データクラス
            debug: デバッグモード
        """
        self.translation_queue = translation_queue
        self.lang_config = lang_config
        self.debug = debug

        # ConfigManagerから設定を取得
        if hasattr(config_manager, 'translation'):
            # ConfigManagerの場合
            trans_config = config_manager.translation
            model_config = config_manager.get_model_config('translation')
            output_config = config_manager.output
            
            self.batch_size = trans_config.batch_size
            self.context_window_size = trans_config.context_window_size
            self.context_separator = trans_config.context_separator
            self.reload_interval = trans_config.reload_interval
            self.max_consecutive_errors = trans_config.max_consecutive_errors
            self.error_cooldown = trans_config.error_cooldown
            self.generation_params = trans_config.generation_params
            self.model_path = model_config.model_path
            self.output_dir = output_config.directory
        else:
            # 互換アダプターの場合
            self.batch_size = getattr(config_manager, 'batch_size', 5)
            self.context_window_size = 8
            self.context_separator = "\n"
            self.reload_interval = 3600 if sys.platform != 'darwin' else 60
            self.max_consecutive_errors = 5
            self.error_cooldown = 10
            self.generation_params = self._setup_default_generation_params()
            self.model_path = getattr(config_manager, 'llm_model', None)
            self.output_dir = getattr(config_manager, 'output_dir', 'logs')

        # 状態管理
        self.consecutive_errors = 0
        self.failed_translations = []
        self.last_reload_time = time.time()
        
        # コンテキスト管理
        self.context_window = deque(maxlen=self.context_window_size)
        
        # モデル
        self.llm_model = None
        self.llm_tokenizer = None
        
        # プロンプトテンプレート
        self.prompt_template = self._setup_translation_prompt()
        
        # MLXサンプラー（macOSのみ）
        if sys.platform == 'darwin':
            # config.yamlから取得
            temp = self.generation_params.get('temperature', 0.8)
            top_p = self.generation_params.get('top_p', 0.95)
            rep_penalty = self.generation_params.get('repetition_penalty', 1.1)
            rep_context = self.generation_params.get('repetition_context_size', 20)
            
            self.sampler = make_sampler(temp=temp, top_p=top_p)
            self.logits_processors = make_logits_processors(
                repetition_penalty=rep_penalty,
                repetition_context_size=rep_context
            )
        else:
            self.sampler = None
            self.logits_processors = None
        
        # モデルのロード
        self.load_model()
        
        # 出力ファイルの設定
        self._setup_output_files()

    def _setup_default_generation_params(self) -> Dict:
        """デフォルトの生成パラメータを設定"""
        if sys.platform == 'darwin':
            return {"max_tokens": 256}
        else:
            return {
                "do_sample": True,
                "temperature": 0.8,
                "top_p": 0.95,
                "top_k": 40,
                "max_new_tokens": 256,
                "repetition_penalty": 1.1,
            }

    def _setup_translation_prompt(self) -> str:
        """翻訳方向に応じたプロンプトテンプレートを設定"""
        from config_manager import LanguageConfig
        
        # 言語名の取得
        source_name = LanguageConfig.get_language_name(self.lang_config.source)
        target_name = LanguageConfig.get_language_name(self.lang_config.target)
        return (
            f"以下の{source_name}を文脈を考慮して適切な{target_name}に翻訳してください。"
            f"文脈を考慮しつつ、自然な{target_name}になるよう翻訳してください。"
            f"翻訳のみを出力し、説明や注記などの出力は一切不要です。\n\n"
            f"Previous context:\n"
            f"{{context}}\n\n"
            f"Current text to translate:\n"
            f"{{text}}\n\n"
            f"{target_name}訳:"
        )
    
    def _setup_output_files(self):
        """出力ファイルの設定"""
        os.makedirs(self.output_dir, exist_ok=True)
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        direction_suffix = f"{self.lang_config.source}-{self.lang_config.target}"
        self.log_file_path = os.path.join(
            self.output_dir,
            f"translated_text_log_{direction_suffix}_{current_time}.txt"
        )
        self.bilingual_log_file_path = os.path.join(
            self.output_dir,
            f"bilingual_translation_log_{direction_suffix}_{current_time}.txt"
        )
        
        print(f"翻訳ログ: {self.log_file_path}")
        print(f"対訳ログ: {self.bilingual_log_file_path}")

    def load_model(self):
        """翻訳モデルのロード"""
        try:
            print(f"翻訳モデルをロード中: {self.model_path}")
            
            # 既存モデルのクリーンアップ
            del self.llm_model
            del self.llm_tokenizer
            
            if sys.platform == 'darwin':
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                gc.collect()
                self.llm_model, self.llm_tokenizer = load(path_or_hf_repo=self.model_path)
            else:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
                
                self.llm_tokenizer = AutoTokenizer.from_pretrained(
                    self.model_path,
                    trust_remote_code=True
                )
                self.llm_model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    torch_dtype="auto",
                    device_map="auto",
                    low_cpu_mem_usage=True,
                    trust_remote_code=True,
                )
            
            print(f"翻訳モデルのロード完了")

        except Exception as e:
            print(f"モデルの再ロード中にエラーが発生しました: {e}")
            raise

    def translation_thread(self, is_running):
        """翻訳スレッドのメイン処理"""
        print(f"翻訳スレッド開始 ({self.lang_config.source} → {self.lang_config.target})")
        
        while is_running.is_set():
            try:
                texts_to_translate = []
            
                # 失敗した翻訳の再処理を優先
                while self.failed_translations and len(texts_to_translate) < self.batch_size:
                    texts_to_translate.append(self.failed_translations.pop(0))
                    if self.debug:
                        print(f"\n再翻訳を試みます: {texts_to_translate[-1]}\n")

                # キューから新しいテキストを追加
                while len(texts_to_translate) < self.batch_size:
                    try:
                        text = self.translation_queue.get_nowait()
                        texts_to_translate.append(text)
                    except queue.Empty:
                        if self.debug:
                            print("翻訳キューが空です")
                        break
                
                if not texts_to_translate:
                    time.sleep(0.1)
                    continue

                # バッチ翻訳の実行
                translated_texts = []
                bilingual_texts = []
                
                for text in texts_to_translate:
                    processed_text = self.preprocess_text(text)
                    translated_text = self.translate_text(processed_text)
                
                    if self.is_valid_translation(translated_text):
                        print(f"\n翻訳: {translated_text}\n")
                        translated_texts.append(translated_text)
                        bilingual_texts.append(
                            f"原文 ({self.lang_config.source}): {processed_text}\n"
                            f"訳文 ({self.lang_config.target}): {translated_text}\n"
                        )
                        self.context_window.append(processed_text)
                        self.consecutive_errors = 0
                    else:
                        if self.debug:
                            print(f"\n翻訳エラー: 有効な翻訳を生成できませんでした。原文: {text}\n")
                        self.handle_translation_error(text)
                
                # ファイルに記録
                if translated_texts:
                    with open(self.log_file_path, "a", encoding="utf-8") as log_file:
                        log_file.write("\n".join(translated_texts) + "\n")

                if bilingual_texts:
                    with open(self.bilingual_log_file_path, "a", encoding="utf-8") as bilingual_log_file:
                        bilingual_log_file.write("\n".join(bilingual_texts) + "\n")

            except Exception as e:
                print(f"\nエラー (翻訳スレッド): {e}", flush=True)
                time.sleep(1)
            
            self.check_model_reload()
        
        print("翻訳スレッド終了")

    def translate_text(self, text):
        """テキストを翻訳"""
        # コンテキストの構築
        context_str = ""
        if self.context_window:
            context_str = self.context_separator.join(self.context_window)

        # プロンプトの構築
        prompt = self.prompt_template.format(
            context=context_str,
            text=text
        )

        # チャットテンプレートの適用
        if hasattr(self.llm_tokenizer, "apply_chat_template") and self.llm_tokenizer.chat_template is not None:
            messages = [{"role": "user", "content": prompt}]
            prompt = self.llm_tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        
        # 翻訳の実行
        if sys.platform == 'darwin':
            # MLXではmax_tokensのみを渡す
            max_tokens = self.generation_params.get('max_tokens', 256)
            response = generate(
                self.llm_model,
                self.llm_tokenizer,
                prompt=prompt,
                sampler=self.sampler,
                logits_processors=self.logits_processors,
                max_tokens=max_tokens
            )
            output_ids = self.llm_tokenizer.encode(
                response,
                add_special_tokens=True,
                return_tensors='pt'
            )
            response = self.llm_tokenizer.decode(
                output_ids[0],
                skip_special_tokens=True
            )
        else:
            input_ids = self.llm_tokenizer.encode(
                prompt,
                add_special_tokens=True,
                return_tensors='pt'
            )
            output_ids = self.llm_model.generate(
                input_ids.to(self.llm_model.device),
                pad_token_id=self.llm_tokenizer.pad_token_id,
                **self.generation_params
            )
            response = self.llm_tokenizer.decode(
                output_ids[0][input_ids.size(1):],
                skip_special_tokens=True
            )

        return response.strip()

    @staticmethod
    def is_valid_translation(text):
        """翻訳が有効かどうかを判定"""
        return bool(text) and len(set(text)) > 1 and not text.startswith('!!!') and not text.endswith('!!!')

    def handle_translation_error(self, text):
        """翻訳エラーの処理"""
        self.consecutive_errors += 1
        self.failed_translations.append(text)
        
        if self.consecutive_errors >= self.max_consecutive_errors:
            if self.debug:
                print("連続エラーが発生しました。モデルを再ロードします。")
            self.load_model()
            self.consecutive_errors = 0
        
        time.sleep(self.error_cooldown)

    def check_model_reload(self):
        """定期的なモデル再ロードのチェック"""
        current_time = time.time()
        if current_time - self.last_reload_time > self.reload_interval:
            if self.debug:
                print("定期的なモデル再ロードを実行します。")
            self.load_model()
            self.last_reload_time = current_time

    @staticmethod
    def preprocess_text(text):
        """テキストの前処理"""
        return text.strip()

