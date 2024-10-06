import argparse
import threading
import time
import queue
from config import AudioConfig
from audio.capture import AudioCapture
from audio.processing import AudioProcessing
from recognition.speech_recognition import SpeechRecognition
from utils.resource_manager import ResourceManager

def parse_arguments():
    parser = argparse.ArgumentParser(description="Real-time Audio Transcription")
    parser.add_argument("--model_path", type=str, default="mlx-community/whisper-large-v3-turbo-q4",
                        help="Path or HuggingFace repo for the Whisper model")
    parser.add_argument("--language", type=str, default="ja",
                        help="Language code for speech recognition (e.g., 'en' for English, 'ja' for Japanese)")
    parser.add_argument("--format", type=str, default="int16",
                        choices=['int8', 'int16', 'int32', 'float32'],
                        help="Audio format (default: int16)")
    parser.add_argument("--rate", type=int, default=16000,
                        help="Sample rate (default: 16000)")
    parser.add_argument("--channels", type=int, default=1,
                        help="Number of channels (default: 1)")
    parser.add_argument("--chunk", type=int, default=1024,
                        help="Chunk size (default: 1024)")
    parser.add_argument("--input_device", type=int, help="Input device index (default: auto-detect Black Hole)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--buffer_duration", type=float, default=2.0,
                        help="Duration of audio buffer in seconds (default: 2.0)")
    return parser.parse_args()

class AudioTranscriptionSystem:
    def __init__(self, audio_capture, audio_processing, speech_recognition, resource_manager):
        self.audio_capture = audio_capture
        self.audio_processing = audio_processing
        self.speech_recognition = speech_recognition
        self.resource_manager = resource_manager
        self.is_running = threading.Event()
        self.is_running.set()

    def run(self):
        threads = [
            threading.Thread(target=self.audio_capture.capture_thread, args=(self.is_running,)),
            threading.Thread(target=self.audio_processing.processing_thread, args=(self.is_running,)),
            threading.Thread(target=self.speech_recognition.recognition_thread, args=(self.is_running,))
        ]
        
        for thread in threads:
            thread.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n終了しています。しばらくお待ちください...")
            self.is_running.clear()
        
        for thread in threads:
            thread.join()
        
        print("プログラムを終了しました。")

def main():
    args = parse_arguments()
    config = AudioConfig(args)
    resource_manager = ResourceManager()
    
    audio_queue = queue.Queue()
    processing_queue = queue.Queue()
    
    audio_capture = AudioCapture(config, audio_queue)
    audio_processing = AudioProcessing(config, audio_queue, processing_queue)
    speech_recognition = SpeechRecognition(config, processing_queue, None, args)
    
    system = AudioTranscriptionSystem(
        audio_capture, audio_processing, speech_recognition, resource_manager
    )
    system.run()

if __name__ == "__main__":
    main()

