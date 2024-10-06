import pyaudio
import numpy as np
import queue
import time
from collections import deque
import noisereduce as nr
from scipy import signal

class AudioProcessing:
    def __init__(self, config, audio_queue, processing_queue):
        self.config = config
        self.audio_queue = audio_queue
        self.processing_queue = processing_queue

    def processing_thread(self, is_running):
        buffer = deque(maxlen=self.config.BUFFER_SIZE)
        silence_start = None
        last_voice_activity = time.time()
        
        while is_running.is_set():
            try:
                data = self.audio_queue.get(timeout=0.1)
                buffer.extend(data)
                
                if self.has_voice_activity(data):
                    last_voice_activity = time.time()
                    silence_start = None
                elif silence_start is None:
                    silence_start = time.time()
                
                if len(buffer) >= self.config.BUFFER_SIZE:
                    current_time = time.time()
                    if current_time - last_voice_activity < self.config.SILENCE_DURATION:
                        audio_data = np.array(buffer)
                        processed_audio = self.preprocess_audio(audio_data)
                        self.processing_queue.put(processed_audio)
                    
                    overlap = int(self.config.BUFFER_SIZE * 0.05)
                    for _ in range(self.config.BUFFER_SIZE - overlap):
                        buffer.popleft()
            
            except queue.Empty:
                pass
            except Exception as e:
                print(f"\nエラー (処理スレッド): {e}", flush=True)

    def has_voice_activity(self, audio_data):
        normalized_data = self.normalize_audio(audio_data)
        rms = np.sqrt(np.mean(normalized_data**2))
        return rms > self.config.VOICE_ACTIVITY_THRESHOLD

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

    def preprocess_audio(self, audio_data):
        reduced_noise = nr.reduce_noise(y=audio_data, sr=self.config.RATE)
        sos = signal.butter(10, [300, 3000], btype='band', fs=self.config.RATE, output='sos')
        filtered_audio = signal.sosfilt(sos, reduced_noise)
        return filtered_audio

