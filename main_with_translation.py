import sys
import argparse
import threading
import time
import queue
from config import AudioConfig
from audio.capture import AudioCapture
from audio.processing import AudioProcessing
from recognition.speech_recognition import SpeechRecognition
from translation.translator import Translation
from utils.resource_manager import ResourceManager
from language_config import LanguageConfig
from argument_config import parse_args_translation
from tts.melo import TextToSpeech, TTSConfig

class AudioRecognitionSystem:
    def __init__(self, audio_capture, audio_processing, speech_recognition, translation, tts, resource_manager):
        self.audio_capture = audio_capture
        self.audio_processing = audio_processing
        self.speech_recognition = speech_recognition
        self.translation = translation
        self.tts = tts
        self.resource_manager = resource_manager
        self.is_running = threading.Event()
        self.is_running.set()

    def run(self):
        threads = [
            threading.Thread(target=self.audio_capture.capture_thread, args=(self.is_running,)),
            threading.Thread(target=self.audio_processing.processing_thread, args=(self.is_running,)),
            threading.Thread(target=self.speech_recognition.recognition_thread, args=(self.is_running,)),
            threading.Thread(target=self.translation.translation_thread, args=(self.is_running,))
        ]
        if self.tts:
            threads.append(threading.Thread(target=self.tts.tts_thread, args=(self.is_running,)))

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
    args = parse_args_translation()
    config = AudioConfig(args)
    lang_config = LanguageConfig(
        source_lang=args.source_lang,
        target_lang=args.target_lang
    )
    resource_manager = ResourceManager()
    
    audio_queue = queue.Queue()
    processing_queue = queue.Queue()
    translation_queue = queue.Queue()
    tts_queue = queue.Queue() if args.tts_enabled else None
    
    audio_capture = AudioCapture(config, audio_queue, args)
    audio_processing = AudioProcessing(config, audio_queue, processing_queue)
    speech_recognition = SpeechRecognition(config, processing_queue, translation_queue, args, lang_config)
    translation = Translation(translation_queue, args, lang_config, tts_queue)

    if args.tts_enabled:
        tts_config = TTSConfig.from_args(args)
        tts = TextToSpeech(tts_config, tts_queue, args)
    else:
        tts = None
    
    system = AudioRecognitionSystem(
        audio_capture, audio_processing, speech_recognition, translation, tts, resource_manager
    )
    system.run()

if __name__ == "__main__":
    main()

