import sys
import os
import datetime
import threading
import queue
import time
import gc

if sys.platform == 'darwin':
    from mlx_lm import load, generate
else:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, logging

class Translation:
    def __init__(self, translation_queue, args):
        self.translation_queue = translation_queue
        self.args = args
        self.last_reload_time = time.time()
        self.reload_interval = 7200  # 120分ごとにモデルを再ロード
        if sys.platform == 'darwin':
            self.reload_interval = 60  # 1分ごとにモデルを再ロード
        self.consecutive_errors = 0
        self.max_consecutive_errors = 1
        self.error_cooldown = 2  # エラー後の待機時間（秒）
        self.failed_translations = []  # エラーとなった原文を保存するリスト
        self.llm_model = None
        self.llm_tokenizer = None
        self.batch_size = args.batch_size if hasattr(args, 'batch_size') else 5  # デフォルト値は5

        if sys.platform == 'darwin':
            self.generation_params = {
                "temp": 0.8,
                "top_p": 0.95,
                "max_tokens": 256,
                "repetition_penalty": 1.1,
                "repetition_context_size": 20,
            }
        else:
            self.generation_params = {
                "do_sample": True,
                "temperature": 0.8,
                "top_p": 0.95,
                "top_k": 40,
                "max_new_tokens": 256,
                "repetition_penalty": 1.1,
            }
        self.load_model()

        os.makedirs(self.args.output_dir, exist_ok=True)
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = os.path.join(self.args.output_dir,
                                          f"translated_audio_log_{current_time}.txt")
        self.bilingual_log_file_path = os.path.join(self.args.output_dir,
                                                    f"bilingual_translation_log_{current_time}.txt")


    def load_model(self):
        try:
            if sys.platform == 'darwin':
                del self.llm_model
                del self.llm_tokenizer
                gc.collect()
                self.llm_model, self.llm_tokenizer = load(path_or_hf_repo=self.args.llm_model)
            else:
                del self.llm_model
                del self.llm_tokenizer
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
                self.llm_tokenizer = AutoTokenizer.from_pretrained(
                    self.args.llm_model,
                    trust_remote_code=True
                )
                #logging.disable_progress_bar()
                self.llm_model = AutoModelForCausalLM.from_pretrained(
                    self.args.llm_model,
                    torch_dtype="auto",
                    device_map="auto",
                    low_cpu_mem_usage=True,
                    trust_remote_code=True,
                )

        except Exception as e:
            print(f"モデルの再ロード中にエラーが発生しました: {e}")
            raise

    def translation_thread(self, is_running):
        while is_running.is_set():
            try:
                # バッチ処理の準備
                texts_to_translate = []
            
                # 失敗した翻訳の再処理を優先
                while self.failed_translations and len(texts_to_translate) < self.batch_size:
                    texts_to_translate.append(self.failed_translations.pop(0))
                    if self.args.debug:
                        print(f"\n再翻訳を試みます: {texts_to_translate[-1]}\n")

                # キューから新しいテキストを追加
                while len(texts_to_translate) < self.batch_size:
                    try:
                        text = self.translation_queue.get_nowait()
                        texts_to_translate.append(text)
                    except queue.Empty:
                        if self.args.debug:
                            print("翻訳キューが空です")
                        break
                
                if not texts_to_translate:
                    time.sleep(0.1)  # キューが空の場合、短い待機時間を設ける
                    continue

                translated_texts = []
                bilingual_texts = []
                for text in texts_to_translate:
                    processed_text = self.preprocess_text(text)
                    translated_text = self.translate_text(processed_text)
                
                    if self.is_valid_translation(translated_text):
                        print(f"\n翻訳: {translated_text}\n")
                        translated_texts.append(translated_text)
                        bilingual_texts.append(f"原文: {processed_text}\n翻訳: {translated_text}\n")
                        self.consecutive_errors = 0
                    else:
                        if self.args.debug:
                            print(f"\n翻訳エラー: 有効な翻訳を生成できませんでした。原文: {text}\n")
                        self.handle_translation_error(text)
                
                # 認識結果をファイルに追記
                if translated_texts:
                    with open(self.log_file_path, "a", encoding="utf-8") as log_file:
                        log_file.write("\n".join(translated_texts) + "\n")

                # バイリンガルログをファイルに追記
                if bilingual_texts:
                    with open(self.bilingual_log_file_path, "a", encoding="utf-8") as bilingual_log_file:
                        bilingual_log_file.write("\n".join(bilingual_texts) + "\n")

            except Exception as e:
                print(f"\nエラー (翻訳スレッド): {e}", flush=True)
                time.sleep(1)
            
            self.check_model_reload()

    def translate_text(self, text):
        prompt = f"以下の英語を日本語に翻訳してください。翻訳のみを出力し、余計な説明は不要です:\n\n{text}\n\n日本語訳:"

        if hasattr(self.llm_tokenizer, "apply_chat_template") and self.llm_tokenizer.chat_template is not None:
            messages = [{"role": "user", "content": prompt}]
            prompt = self.llm_tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        if sys.platform == 'darwin':
            response = generate(
                self.llm_model,
                self.llm_tokenizer,
                prompt=prompt,
                **self.generation_params
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
                output_ids[0][input_ids.size(1) :],
                skip_special_tokens=True
            )

        return response.strip()

    @staticmethod
    def is_valid_translation(text):
        return bool(text) and len(set(text)) > 1 and not text.startswith('!!!') and not text.endswith('!!!')

    def handle_translation_error(self, text):
        self.consecutive_errors += 1
        self.failed_translations.append(text)
        if self.consecutive_errors >= self.max_consecutive_errors:
            if self.args.debug:
                print("連続エラーが発生しました。モデルを再ロードします。")
            self.load_model()
            self.consecutive_errors = 0
        time.sleep(self.error_cooldown)

    def check_model_reload(self):
        current_time = time.time()
        if current_time - self.last_reload_time > self.reload_interval:
            if self.args.debug:
                print("定期的なモデル再ロードを実行します。")
            self.load_model()
            self.last_reload_time = current_time

    @staticmethod
    def preprocess_text(text):
        #text = text.replace("...", " ")
        #text = text.replace("&", "and")
        #
        #if not text.endswith(('.', '!', '?')):
        #    text += '.'
        #
        return text.strip()

