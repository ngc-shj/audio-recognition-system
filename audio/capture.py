import pyaudio
import numpy as np
import time

class AudioCapture:
    def __init__(self, config, audio_queue):
        self.config = config
        self.audio_queue = audio_queue

    def audio_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=self.config.NUMPY_DTYPE)
        self.audio_queue.put(audio_data)
        return (in_data, pyaudio.paContinue)

    def capture_thread(self, is_running):
        audio = pyaudio.PyAudio()
        input_device_index = self.get_input_device_index()

        if input_device_index is None:
            print("適切な入力デバイスが見つかりません。手動で指定してください。")
            return

        stream = audio.open(format=self.config.FORMAT,
                            channels=self.config.CHANNELS,
                            rate=self.config.RATE,
                            input=True,
                            input_device_index=input_device_index,
                            frames_per_buffer=self.config.CHUNK,
                            stream_callback=self.audio_callback)
        
        print(f"音声キャプチャスレッド開始 (デバイスインデックス: {input_device_index})")
        
        stream.start_stream()
        
        while is_running.is_set():
            time.sleep(0.1)
        
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        print("音声キャプチャスレッド終了")

    @staticmethod
    def get_input_device_index():
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if "blackhole" in info["name"].lower():
                return i
        return None

