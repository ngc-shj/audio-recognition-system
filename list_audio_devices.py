import pyaudio

def list_audio_devices():
    p = pyaudio.PyAudio()
    
    print("Input Devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"  Device {i}: {info['name']}")
            print(f"    Max Input Channels: {info['maxInputChannels']}")
            print(f"    Default Sample Rate: {info['defaultSampleRate']}")
            print()

    print("\nOutput Devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxOutputChannels'] > 0:
            print(f"  Device {i}: {info['name']}")
            print(f"    Max Output Channels: {info['maxOutputChannels']}")
            print(f"    Default Sample Rate: {info['defaultSampleRate']}")
            print()

    p.terminate()

if __name__ == "__main__":
    list_audio_devices()

