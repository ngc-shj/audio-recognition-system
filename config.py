import pyaudio
import numpy as np

class AudioConfig:
    def __init__(self, args):
        self.FORMAT = self.get_format_from_string(args.format)
        self.CHANNELS = args.channels
        self.RATE = args.rate
        self.CHUNK = args.chunk
        self.NUMPY_DTYPE = self.get_numpy_dtype(self.FORMAT)
        self.BUFFER_DURATION = args.buffer_duration
        self.BUFFER_SIZE = int(self.RATE * self.BUFFER_DURATION)
        self.SILENCE_THRESHOLD = 0.005
        self.VOICE_ACTIVITY_THRESHOLD = 0.01
        self.SILENCE_DURATION = 1.0

    @staticmethod
    def get_format_from_string(format_str):
        format_dict = {
            'int8': pyaudio.paInt8,
            'int16': pyaudio.paInt16,
            'int32': pyaudio.paInt32,
            'float32': pyaudio.paFloat32
        }
        return format_dict.get(format_str.lower(), pyaudio.paInt16)

    @staticmethod
    def get_numpy_dtype(format):
        if format == pyaudio.paInt8:
            return np.int8
        elif format == pyaudio.paInt16:
            return np.int16
        elif format == pyaudio.paInt32:
            return np.int32
        elif format == pyaudio.paFloat32:
            return np.float32
        else:
            raise ValueError(f"Unsupported audio format: {format}")

