import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import io
import wave
import time
import pyaudio
import threading
import queue
from dataclasses import dataclass
from typing import Optional
import torch
import numpy as np
from transformers import AutoTokenizer
from parler_tts import ParlerTTSForConditionalGeneration

@dataclass
class TTSConfig:
    model_tag: str = "parler-tts/parler-tts-mini-v1"
    device: str = "cuda:0" if torch.cuda.is_available() else "cpu"
    voice_description: str = "The voice is clear and natural, with a professional tone and moderate pace."
    max_length: int = 512

class TextToSpeech:
    def __init__(self, config: TTSConfig, tts_queue: queue, args):
        self.config = config
        self.tts_queue = tts_queue
        self.args = args
        self.audio = pyaudio.PyAudio()
        self.is_speaking = False

        # モデルの初期化
        self._initialize_model()

    def _initialize_model(self) -> None:
        try:
            if self.args.debug:
                print("Loading TTS model...")

            # モデルとトークナイザーの初期化
            self.model = ParlerTTSForConditionalGeneration.from_pretrained(
                self.config.model_tag
            ).to(self.config.device)

            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_tag)

            if self.args.debug:
                print("TTS model loaded successfully")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize TTS model: {e}")

    def _generate_audio(self, text: str) -> np.ndarray:
        try:
            with torch.no_grad():
                # テキストのエンコード
                description_tokens = self.tokenizer(
                    self.config.voice_description,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_length,
                ).to(self.config.device)

                # テキストのエンコード
                prompt_tokens = self.tokenizer(
                    text,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_length,
                ).to(self.config.device)

                # デバッグ情報の出力
                if self.args.debug:
                    print(f"Description tokens shape: {description_tokens.input_ids.shape}")
                    print(f"Prompt tokens shape: {prompt_tokens.input_ids.shape}")

                # 音声の生成
                generation = self.model.generate(
                    input_ids=description_tokens.input_ids,
                    prompt_input_ids=prompt_tokens.input_ids,
                    attention_mask=description_tokens.attention_mask,
                    do_sample=True,
                    temperature=0.8,
                    max_length=1024,
                    repetition_penalty=1.2
                )

                # numpy配列に変換
                audio_arr = generation.cpu().numpy().squeeze()

                return audio_arr

        except Exception as e:
            raise RuntimeError(f"Failed to generate audio: {e}")

    def _play_audio(self, wav_data: np.ndarray) -> None:
        """音声データを再生"""
        try:
            # 音声データの正規化
            max_val = np.abs(wav_data).max()
            if max_val > 0:
                wav_data = wav_data / max_val
            wav_data = (wav_data * 32767).astype(np.int16)

            # PyAudioストリームの設定
            stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.model.config.sampling_rate,  # モデルの設定から取得
                output=True
            )

            # チャンク単位で再生
            chunk_size = 1024
            self.is_speaking = True

            for i in range(0, len(wav_data), chunk_size):
                if not self.is_speaking:
                    break
                chunk = wav_data[i:i + chunk_size].tobytes()
                stream.write(chunk)

            self.is_speaking = False
            stream.stop_stream()
            stream.close()

        except Exception as e:
            self.is_speaking = False
            raise RuntimeError(f"Failed to play audio: {e}")

    def tts_thread(self, is_running: threading.Event) -> None:
        while is_running.is_set():
            try:
                # キューからテキストを取得
                text = self.tts_queue.get(timeout=0.1)

                if self.args.debug:
                    print(f"\nGenerating speech for: {text}\n")

                try:
                    # 音声の生成と再生
                    wav_data = self._generate_audio(text)
                    self._play_audio(wav_data)

                except Exception as e:
                    print(f"\nTTS Error: {e}", flush=True)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"\nError (TTS thread): {e}", flush=True)
                time.sleep(1)

    def stop_speaking(self) -> None:
        self.is_speaking = False

    def __del__(self):
        if hasattr(self, 'audio'):
            self.audio.terminate()

