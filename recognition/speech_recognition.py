import mlx_whisper
import queue
import wave
import time
import numpy as np
import pyaudio
import queue

class SpeechRecognition:
    def __init__(self, config, processing_queue, translation_queue, args):
        self.config = config
        self.processing_queue = processing_queue
        self.translation_queue = translation_queue
        self.args = args

    def recognition_thread(self, is_running):
        last_text = ""
        last_text_time = 0
        while is_running.is_set():
            try:
                audio_data = self.processing_queue.get(timeout=1)
                normalized_audio = self.normalize_audio(audio_data)
                
                if self.args.debug:
                    print("\n音声認識処理開始")
                    self.save_audio_debug(audio_data, f"debug_audio_{time.time()}.wav")
                
                try:
                    result = mlx_whisper.transcribe(normalized_audio,
                                                    language=self.args.language,
                                                    path_or_hf_repo=self.args.model_path)
                except Exception as e:
                    print(f"音声認識エラー: {e}")
                    continue
                
                text = result['text'].strip()
                
                current_time = time.time()
                if text and (text != last_text or current_time - last_text_time > 5):
                    self.print_with_strictly_controlled_linebreaks(text)
                    last_text_time = current_time
                    self.translation_queue.put(text)
                elif self.args.debug:
                    print("処理後のテキストが空か、直前の文と同じため出力をスキップします")
            
            except queue.Empty:
                if self.args.debug:
                    print("認識キューが空です")
            except Exception as e:
                print(f"\nエラー (認識スレッド): {e}", flush=True)

    def normalize_audio(self, audio_data):
        if self.config.FORMAT == pyaudio.paFloat32:
            return np.clip(audio_data, -1.0, 1.0)
        elif self.config.FORMAT == pyaudio.paInt8:
            return audio_data.astype(np.float32) / 128.0
        elif self.config.FORMAT == pyaudio.paInt16:
            return audio_data.astype(np.float32) / 32768.0
        elif self.config.FORMAT == pyaudio.paInt32:
            return audio_data.astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported audio format: {self.config.FORMAT}")

    def save_audio_debug(self, audio_data, filename):
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.config.CHANNELS)
            wf.setsampwidth(pyaudio.get_sample_size(self.config.FORMAT))
            wf.setframerate(self.config.RATE)
            wf.writeframes(audio_data.tobytes())

    @staticmethod
    def is_sentence_end(word):
        return word.endswith(('.', '!', '?')) and not word.endswith('...')

    @staticmethod
    def print_with_strictly_controlled_linebreaks(text):
        words = text.split()
        buffer = []
        for i, word in enumerate(words):
            buffer.append(word)
            
            if SpeechRecognition.is_sentence_end(word):
                print(' '.join(buffer), end='')
                if SpeechRecognition.is_sentence_end(word):
                    print('\n', end='', flush=True)
                else:
                    print(' ', end='', flush=True)
                buffer = []
            elif i == len(words) - 1:
                print(' '.join(buffer), end='', flush=True)
                buffer = []
        
        if buffer:
            print(' '.join(buffer), end='', flush=True)

