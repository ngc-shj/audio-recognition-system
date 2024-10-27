import os
import time
import pyaudio
import threading
import queue
import argparse
from dataclasses import dataclass
from typing import Optional
import numpy as np
from melo.api import TTS

@dataclass
class TTSConfig:
    """MeloTTS設定を管理するデータクラス"""
    language: str = "JP"
    device: str = "auto"
    speed: float = 1.0
    sdp_ratio: float = 0.2
    noise_scale: float = 0.6
    noise_scale_w: float = 0.8
    quiet: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'TTSConfig':
        return cls(
            language=args.tts_language,
            device=args.tts_device,
            speed=args.tts_speed,
            sdp_ratio=args.tts_sdp_ratio,
            noise_scale=args.tts_noise_scale,
            noise_scale_w=args.tts_noise_scale_w,
            quiet=args.tts_quiet or not args.debug
        )

class TextToSpeech:
    def __init__(self, config: TTSConfig, tts_queue: queue, args):
        self.config = config
        self.tts_queue = tts_queue
        self.args = args
        self.audio = pyaudio.PyAudio()
        self.is_speaking = False
        
        self._initialize_model()

    def _initialize_model(self) -> None:
        try:
            if self.args.debug:
                print("Loading TTS model...")

            self.model = TTS(
                language=self.config.language,
                device=self.config.device
            )
            self.speaker_id = self.model.hps.data.spk2id[self.config.language]

            if self.args.debug:
                print("TTS model loaded successfully")
                print(f"Speaker ID: {self.speaker_id}")
                print(f"Device: {self.config.device}")

        except Exception as e:
            if self.args.debug:
                import traceback
                print(f"Initialization error details:\n{traceback.format_exc()}")
            raise RuntimeError(f"Failed to initialize TTS model: {e}")

    def _generate_audio(self, text: str) -> np.ndarray:
        try:
            if self.args.debug:
                print(f"Generating audio for text: {text}")

            # tts_to_fileメソッドを使用して直接numpy配列を取得
            audio_data = self.model.tts_to_file(
                text=text,
                speaker_id=self.speaker_id,
                output_path=None,
                sdp_ratio=self.config.sdp_ratio,
                noise_scale=self.config.noise_scale,
                noise_scale_w=self.config.noise_scale_w,
                speed=self.config.speed,
                quiet=self.config.quiet
            )

            if self.args.debug:
                print(f"Generated audio array shape: {audio_data.shape}")
                print(f"Audio range: [{audio_data.min()}, {audio_data.max()}]")

            # float32からint16に変換
            audio_data = np.clip(audio_data, -1.0, 1.0)
            audio_data = (audio_data * 32767).astype(np.int16)

            return audio_data

        except Exception as e:
            if self.args.debug:
                import traceback
                print(f"Generation error details:\n{traceback.format_exc()}")
            raise RuntimeError(f"Failed to generate audio: {e}")

    def _play_audio(self, wav_data: np.ndarray) -> None:
        try:
            if self.args.debug:
                print("Starting audio playback")
                print(f"Audio data shape: {wav_data.shape}")
            
            stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.model.hps.data.sampling_rate,
                output=True
            )
            
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

            if self.args.debug:
                print("Audio playback completed")

        except Exception as e:
            self.is_speaking = False
            if self.args.debug:
                import traceback
                print(f"Playback error details:\n{traceback.format_exc()}")
            raise RuntimeError(f"Failed to play audio: {e}")

    def tts_thread(self, is_running: threading.Event) -> None:
        while is_running.is_set():
            try:
                text = self.tts_queue.get(timeout=0.1)
                
                if self.args.debug:
                    print(f"\nProcessing text for TTS: {text}\n")
                
                try:
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

