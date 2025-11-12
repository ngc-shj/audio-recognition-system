"""
Translation Module
翻訳モジュール
"""

import sys
import os
import re
import datetime
import queue
import time
import gc
import torch
from collections import deque
from typing import Dict, Optional

# Logging
from utils.logger import setup_logger

if sys.platform == 'darwin':
    try:
        from mlx_lm import load, generate
        from mlx_lm.sample_utils import make_sampler, make_logits_processors
    except ImportError as e:
        logger.info(f"ERROR: Failed to import MLX sampling utilities: {e}", file=sys.stderr)
        raise
else:
    from transformers import AutoModelForCausalLM, AutoTokenizer, logging

# GGUF形式のモデルをサポート
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    logger.info("INFO: llama-cpp-python not available. GGUF models will not be supported.")

# OpenAI互換APIクライアントのサポート
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.info("INFO: openai package not available. API server mode will not be supported.")


# Setup logger
logger = setup_logger(__name__)

class Translation:
    """
    翻訳クラス
    
    ConfigManagerから設定を取得し、LLMで翻訳を実行します。
    """
    
    def __init__(self, translation_queue, config_manager, lang_config, debug=False, tts=None, web_ui=None):
        """
        Args:
            translation_queue: 翻訳待ちテキストのキュー
            config_manager: ConfigManager または互換アダプター
            lang_config: LanguageConfig データクラス
            debug: デバッグモード
            tts: TextToSpeech インスタンス（オプショナル）
            web_ui: WebUIBridge インスタンス（オプショナル）
        """
        self.translation_queue = translation_queue
        self.lang_config = lang_config
        self.debug = debug
        self.tts = tts  # TTS機能
        self.web_ui = web_ui  # Web UI Bridge

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

            # セキュリティ設定: trust_remote_code の取得（デフォルト: False）
            self.trust_remote_code = getattr(model_config, 'trust_remote_code', False)

            # API設定の取得
            api_config = model_config.api
            self.use_api = api_config.enabled
            self.api_base_url = api_config.base_url
            self.api_key = api_config.api_key
            self.api_model = api_config.model
            self.api_timeout = api_config.timeout
            self.api_max_retries = api_config.max_retries

            # GGUF設定の取得
            gguf_config = model_config.gguf
            self.use_gguf = gguf_config.enabled
            self.gguf_model_path = gguf_config.model_path
            self.gguf_model_file = gguf_config.model_file
            self.gguf_n_ctx = gguf_config.n_ctx
            self.gguf_n_gpu_layers = gguf_config.n_gpu_layers
            self.gguf_n_threads = gguf_config.n_threads
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

            # セキュリティ設定: trust_remote_code（デフォルト: False）
            self.trust_remote_code = getattr(config_manager, 'trust_remote_code', False)

            # デフォルトではAPI・GGUFを無効化
            self.use_api = False
            self.use_gguf = False

        # 状態管理
        self.consecutive_errors = 0
        self.failed_translations = []
        self.last_reload_time = time.time()
        
        # コンテキスト管理
        self.context_window = deque(maxlen=self.context_window_size)
        
        # モデル / APIクライアント
        self.llm_model = None
        self.llm_tokenizer = None
        self.api_client = None  # OpenAI APIクライアント
        self.model_type = None  # 'transformers', 'mlx', 'gguf', 'api'のいずれか
        self.is_gpt_oss = False  # GPT-OSSモデルかどうか
        
        # プロンプトテンプレート
        self.prompt_template = self._setup_translation_prompt()
        
        # MLXサンプラー（macOSのみ）
        if sys.platform == 'darwin':
            # config.yamlから取得
            temp = self.generation_params.get('temperature', 0.8)
            top_p = self.generation_params.get('top_p', 1.0)
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
            return {"max_tokens": 4096}
        else:
            return {
                "do_sample": True,
                "temperature": 0.8,
                "top_p": 1.0,
                "top_k": 0,
                "max_new_tokens": 4096,
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
        
        logger.info(f"翻訳ログ: {self.log_file_path}")
        logger.info(f"対訳ログ: {self.bilingual_log_file_path}")

    def load_model(self):
        """翻訳モデル/APIクライアントのロード"""
        try:
            # 既存モデルのクリーンアップ（メモリ解放を保証）
            if hasattr(self, 'llm_model') and self.llm_model is not None:
                del self.llm_model
                self.llm_model = None
            if hasattr(self, 'llm_tokenizer') and self.llm_tokenizer is not None:
                del self.llm_tokenizer
                self.llm_tokenizer = None
            if hasattr(self, 'api_client') and self.api_client is not None:
                del self.api_client
                self.api_client = None

            # ガベージコレクションを強制実行してメモリを確実に解放
            import gc
            gc.collect()

            # APIサーバーを使用する場合
            if self.use_api:
                if not OPENAI_AVAILABLE:
                    raise ImportError(
                        "openai package is required for API mode. "
                        "Install it with: pip install openai"
                    )

                logger.info(f"APIサーバーに接続中: {self.api_base_url}")
                logger.info(f"使用モデル: {self.api_model}")

                # OpenAI互換APIクライアントの初期化
                self.api_client = OpenAI(
                    base_url=self.api_base_url,
                    api_key=self.api_key or "dummy-key",  # LM Studioなどではapi_keyが不要
                    timeout=self.api_timeout,
                    max_retries=self.api_max_retries
                )
                self.llm_model = None
                self.llm_tokenizer = None
                self.model_type = 'api'
                self.is_gpt_oss = False  # APIモードではGPT-OSSパース不要

                logger.info("APIクライアントの初期化完了")
                return

            # GGUF形式のモデルを使用するかどうかを判定
            if self.use_gguf and LLAMA_CPP_AVAILABLE:
                logger.info(f"翻訳モデルをロード中 (GGUF): {self.gguf_model_path}/{self.gguf_model_file}")
                
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
                
                # GGUFモデルのパスを構築
                if os.path.isfile(self.gguf_model_path):
                    # ローカルファイルパスの場合
                    model_full_path = self.gguf_model_path
                else:
                    # Hugging Faceリポジトリの場合
                    from huggingface_hub import hf_hub_download
                    model_full_path = hf_hub_download(
                        repo_id=self.gguf_model_path,
                        filename=self.gguf_model_file
                    )
                
                # llama-cpp-pythonでモデルをロード
                self.llm_model = Llama(
                    model_path=model_full_path,
                    n_ctx=self.gguf_n_ctx,
                    n_gpu_layers=self.gguf_n_gpu_layers,
                    n_threads=self.gguf_n_threads,
                    verbose=self.debug
                )
                self.llm_tokenizer = None  # GGUFでは内部でトークナイザーが管理される
                self.model_type = 'gguf'
                
                # GPT-OSSモデルかどうかを判定
                self.is_gpt_oss = 'gpt-oss' in self.gguf_model_path.lower()
                logger.info(f"翻訳モデルのロード完了 (GGUF){' [GPT-OSS]' if self.is_gpt_oss else ''}")
            elif sys.platform == 'darwin':
                # macOS: MLXを使用
                logger.info(f"翻訳モデルをロード中 (MLX): {self.model_path}")
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                gc.collect()
                self.llm_model, self.llm_tokenizer = load(path_or_hf_repo=self.model_path)
                self.model_type = 'mlx'
                
                # GPT-OSSモデルかどうかを判定
                self.is_gpt_oss = 'gpt-oss' in self.model_path.lower()
                logger.info(f"翻訳モデルのロード完了 (MLX){' [GPT-OSS]' if self.is_gpt_oss else ''}")
            else:
                # Linux/Windows: transformersを使用
                logger.info(f"翻訳モデルをロード中 (Transformers): {self.model_path}")
                
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
                
                self.llm_tokenizer = AutoTokenizer.from_pretrained(
                    self.model_path,
                    trust_remote_code=self.trust_remote_code
                )
                self.llm_model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    torch_dtype="auto",
                    device_map="auto",
                    low_cpu_mem_usage=True,
                    trust_remote_code=self.trust_remote_code,
                )
                self.model_type = 'transformers'
                
                # GPT-OSSモデルかどうかを判定
                self.is_gpt_oss = 'gpt-oss' in self.model_path.lower()
                logger.info(f"翻訳モデルのロード完了 (Transformers){' [GPT-OSS]' if self.is_gpt_oss else ''}")

        except Exception as e:
            logger.info(f"モデルの再ロード中にエラーが発生しました: {e}")
            raise

    def translation_thread(self, is_running):
        """翻訳スレッドのメイン処理"""
        logger.info(f"翻訳スレッド開始 ({self.lang_config.source} → {self.lang_config.target})")
        
        while is_running.is_set():
            try:
                texts_to_translate = []
            
                # 失敗した翻訳の再処理を優先
                while self.failed_translations and len(texts_to_translate) < self.batch_size:
                    texts_to_translate.append(self.failed_translations.pop(0))
                    if self.debug:
                        logger.info(f"\n再翻訳を試みます: {texts_to_translate[-1]}\n")

                # キューから新しいテキストを追加
                # 最初のアイテムはtimeout付きで待機（CPU効率化）
                if not texts_to_translate:
                    try:
                        item = self.translation_queue.get(timeout=1.0)  # 0.1秒→1.0秒に変更でCPU使用率削減
                        if isinstance(item, dict):
                            texts_to_translate.append(item)
                        else:
                            texts_to_translate.append({'text': item, 'pair_id': None})
                    except queue.Empty:
                        if not is_running.is_set():
                            break
                        continue

                # 残りのアイテムはノンブロッキングで取得
                while len(texts_to_translate) < self.batch_size:
                    try:
                        item = self.translation_queue.get_nowait()
                        if isinstance(item, dict):
                            texts_to_translate.append(item)
                        else:
                            texts_to_translate.append({'text': item, 'pair_id': None})
                    except queue.Empty:
                        break

                # バッチ翻訳の実行（複数テキストをまとめて処理）
                translated_texts = []
                bilingual_texts = []
                processed_items = [
                    (item, self.preprocess_text(item['text'])) for item in texts_to_translate
                ]

                for item, processed_text in processed_items:
                    original_text = item['text']
                    pair_id = item.get('pair_id')

                    translated_text = self.translate_text(processed_text)

                    if self.is_valid_translation(translated_text):
                        # Web UIモードではstdoutに出力しない
                        if not self.web_ui:
                            # 翻訳結果はログではなく標準出力
                            print(f"\n翻訳: {translated_text}\n")
                        translated_texts.append(translated_text)
                        bilingual_texts.append(
                            f"原文 ({self.lang_config.source}): {processed_text}\n"
                            f"訳文 ({self.lang_config.target}): {translated_text}\n"
                        )
                        self.context_window.append(processed_text)
                        self.consecutive_errors = 0

                        # TTS: 翻訳後のテキストを読み上げ
                        if self.tts is not None:
                            try:
                                self.tts.speak(translated_text)
                            except Exception as e:
                                if self.debug:
                                    logger.info(f"TTS error: {e}")

                        # Web UIに送信（pair_idも送信）
                        if self.web_ui:
                            self.web_ui.send_translated_text(translated_text, processed_text, pair_id)
                    else:
                        if self.debug:
                            logger.info(f"\n翻訳エラー: 有効な翻訳を生成できませんでした。原文: {original_text}\n")
                        self.handle_translation_error(item)
                
                # ファイルに記録（バッチ書き込みでI/O効率化）
                if translated_texts or bilingual_texts:
                    try:
                        # 両方のログをまとめて開く（I/Oコストを削減）
                        files = {}
                        if translated_texts:
                            files['translated'] = (self.log_file_path, "\n".join(translated_texts) + "\n")
                        if bilingual_texts:
                            files['bilingual'] = (self.bilingual_log_file_path, "\n".join(bilingual_texts) + "\n")

                        for log_type, (file_path, content) in files.items():
                            with open(file_path, "a", encoding="utf-8") as f:
                                f.write(content)
                    except IOError as e:
                        logger.error(f"ログ書き込みエラー: {e}")

            except Exception as e:
                logger.error(f"エラー (翻訳スレッド): {e}")
                time.sleep(0.5)
            
            self.check_model_reload()
        
        logger.info("翻訳スレッド終了")

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

        # チャットテンプレートの適用準備（共通）
        messages = [{"role": "user", "content": prompt}]

        # 翻訳の実行
        if self.model_type == 'api':
            # API経由で推論
            max_tokens = self.generation_params.get('max_new_tokens', 4096)
            temperature = self.generation_params.get('temperature', 0.8)
            top_p = self.generation_params.get('top_p', 1.0)

            try:
                completion = self.api_client.chat.completions.create(
                    model=self.api_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )
                response = completion.choices[0].message.content.strip()

                if self.debug:
                    logger.info(f"[API] Response: {response[:200]}...")

            except Exception as e:
                logger.info(f"API呼び出しエラー: {e}")
                # エラー時は空の応答を返す
                response = ""

        elif self.model_type == 'mlx':
            # macOS: MLXで推論
            # チャットテンプレートの適用
            if hasattr(self.llm_tokenizer, "apply_chat_template") and self.llm_tokenizer.chat_template is not None:
                prompt = self.llm_tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            
            max_tokens = self.generation_params.get('max_tokens', 4096)
            output = generate(
                self.llm_model,
                self.llm_tokenizer,
                prompt=prompt,
                sampler=self.sampler,
                logits_processors=self.logits_processors,
                max_tokens=max_tokens
            )
            response = output.strip()
            
        elif self.model_type == 'gguf':
            # Linux/Windows: GGUF形式で推論
            max_tokens = self.generation_params.get('max_new_tokens', 4096)
            temperature = self.generation_params.get('temperature', 0.8)
            top_p = self.generation_params.get('top_p', 1.0)
            top_k = self.generation_params.get('top_k', 0)
            repeat_penalty = self.generation_params.get('repetition_penalty', 1.1)

            output = self.llm_model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repeat_penalty=repeat_penalty,
            )
            if self.debug:
                logger.info(f"===> GGUF Output:\n{output}\n=== End of GGUF Output")

            response = output['choices'][0]['message']['content'].strip()
            
        else:
            # Linux/Windows: transformersで推論
            # チャットテンプレートの適用
            if hasattr(self.llm_tokenizer, "apply_chat_template") and self.llm_tokenizer.chat_template is not None:
                messages = [{"role": "user", "content": prompt}]
                prompt = self.llm_tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            
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
        
        # デバッグ: 生成された生の出力を表示
        if self.debug and self.is_gpt_oss:
            logger.info(f"[GPT-OSS] Raw output: {response[:200]}...")
        
        # GPT-OSSの場合はチャンネルタグをパース
        if self.is_gpt_oss:
            response = self._parse_gpt_oss_output(response)

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
                logger.info("連続エラーが発生しました。モデルを再ロードします。")
            self.load_model()
            self.consecutive_errors = 0
        
        time.sleep(self.error_cooldown)

    def check_model_reload(self):
        """定期的なモデル再ロードのチェック"""
        # APIモードでは再ロード不要
        if self.model_type == 'api':
            return

        current_time = time.time()
        if current_time - self.last_reload_time > self.reload_interval:
            if self.debug:
                logger.info("定期的なモデル再ロードを実行します。")
            self.load_model()
            self.last_reload_time = current_time

    @staticmethod
    def preprocess_text(text):
        """テキストの前処理"""
        return text.strip()

    def _parse_gpt_oss_output(self, output: str) -> str:
        """
        GPT-OSSモデルの出力からチャンネルタグを除去し、最終的な翻訳結果を抽出

        GPT-OSSは以下のような形式で出力する:
        <|start|>assistant<|channel|>analysis<|message|>思考内容<|end|>
        <|start|>assistant<|channel|>final<|message|>最終回答<|end|>

        この関数は最終チャンネル（final）の内容のみを抽出する
        """
        if not output:
            return output

        # チャンネルタグが含まれていない場合はそのまま返す
        if '<|channel|>' not in output and '<|start|>' not in output:
            return output

        # finalチャンネルの内容を抽出
        final_match = re.search(
            r'(?:<\|start\|>assistant)?<\|channel\|>final<\|message\|>(.*?)(?:<\|end\|>|$)',
            output,
            re.DOTALL
        )

        if final_match:
            result = final_match.group(1).strip()
            if self.debug:
                logger.info(f"[GPT-OSS] Final channel extracted: {result[:100]}...")
            return result

        # finalチャンネルが見つからない場合、すべてのチャンネルタグを削除
        clean_output = re.sub(
            r'<\|(?:start\|>(?:[^<]*<\|)?|end\|>|message\|>|channel\|>[^<]*)',
            '', 
            output
        )
        clean_output = re.sub(r'\s+', ' ', clean_output).strip()

        if self.debug:
            logger.info(f"[GPT-OSS] Fallback cleaning applied: {clean_output[:100]}...")

        # クリーニング後も空の場合はエラーメッセージ
        return clean_output if clean_output else ""
