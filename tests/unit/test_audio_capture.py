"""
Unit tests for audio.capture module
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import queue
import threading
import sys

# Mock pyaudio and numpy if not available (for CI/CD environments)
try:
    import pyaudio
except ImportError:
    pyaudio = Mock()
    pyaudio.paInt16 = 8
    pyaudio.paContinue = 0
    sys.modules['pyaudio'] = pyaudio

try:
    import numpy as np
except ImportError:
    np = Mock()
    np.int16 = 'int16'
    np.ndarray = object
    sys.modules['numpy'] = np

from audio.capture import AudioCapture


class MockAudioConfig:
    """Mock AudioConfig for testing"""
    def __init__(self):
        self.format = pyaudio.paInt16
        self.channels = 1
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.numpy_dtype = np.int16


class TestAudioCapture(unittest.TestCase):
    """Test cases for AudioCapture class"""

    def setUp(self):
        """Set up test fixtures"""
        self.audio_config = MockAudioConfig()
        self.audio_queue = queue.Queue()

    def test_init_with_specific_device(self):
        """Test initialization with specific device index"""
        with patch.object(AudioCapture, 'get_input_device_index', return_value=1):
            config_manager = Mock()
            config_manager.input_device = 1

            capture = AudioCapture(
                self.audio_config,
                self.audio_queue,
                config_manager
            )

            self.assertEqual(capture.input_device_index, 1)
            self.assertEqual(capture.audio_config, self.audio_config)
            self.assertEqual(capture.audio_queue, self.audio_queue)

    def test_init_without_config_manager(self):
        """Test initialization without config manager"""
        with patch.object(AudioCapture, 'get_input_device_index', return_value=0):
            capture = AudioCapture(
                self.audio_config,
                self.audio_queue
            )

            self.assertIsNotNone(capture.input_device_index)

    def test_init_raises_error_when_no_device_found(self):
        """Test initialization raises error when no device found"""
        with patch.object(AudioCapture, 'get_input_device_index', return_value=None):
            with self.assertRaises(ValueError) as context:
                AudioCapture(
                    self.audio_config,
                    self.audio_queue
                )

            self.assertIn("適切な入力デバイスが見つかりません", str(context.exception))

    def test_audio_callback_puts_data_in_queue(self):
        """Test audio callback puts data in queue"""
        with patch.object(AudioCapture, 'get_input_device_index', return_value=0):
            capture = AudioCapture(
                self.audio_config,
                self.audio_queue
            )

            # Create mock audio data
            in_data = np.random.randint(-32768, 32767, 1024, dtype=np.int16).tobytes()

            # Call callback
            result, status = capture.audio_callback(in_data, 1024, None, None)

            # Verify data was queued
            self.assertFalse(self.audio_queue.empty())
            queued_data = self.audio_queue.get()
            self.assertIsInstance(queued_data, np.ndarray)
            self.assertEqual(queued_data.dtype, np.int16)
            self.assertEqual(status, pyaudio.paContinue)

    @patch('audio.capture.pyaudio.PyAudio')
    def test_capture_thread_cleanup_on_normal_stop(self, mock_pyaudio_class):
        """Test capture thread cleans up properly on normal stop"""
        with patch.object(AudioCapture, 'get_input_device_index', return_value=0):
            # Setup mocks
            mock_pyaudio = MagicMock()
            mock_stream = MagicMock()
            mock_pyaudio_class.return_value = mock_pyaudio
            mock_pyaudio.open.return_value = mock_stream
            mock_stream.is_active.return_value = True

            capture = AudioCapture(
                self.audio_config,
                self.audio_queue
            )

            # Create event and start thread
            is_running = threading.Event()
            is_running.set()

            # Run thread in background
            thread = threading.Thread(
                target=capture.capture_thread,
                args=(is_running,)
            )
            thread.start()

            # Let it run briefly then stop
            threading.Event().wait(0.3)
            is_running.clear()
            thread.join(timeout=2.0)

            # Verify cleanup was called
            mock_stream.stop_stream.assert_called_once()
            mock_stream.close.assert_called_once()
            mock_pyaudio.terminate.assert_called_once()

    @patch('audio.capture.pyaudio.PyAudio')
    def test_capture_thread_cleanup_on_error(self, mock_pyaudio_class):
        """Test capture thread cleans up properly on error"""
        with patch.object(AudioCapture, 'get_input_device_index', return_value=0):
            # Setup mocks to raise error
            mock_pyaudio = MagicMock()
            mock_pyaudio_class.return_value = mock_pyaudio
            mock_pyaudio.open.side_effect = Exception("Test error")

            capture = AudioCapture(
                self.audio_config,
                self.audio_queue
            )

            is_running = threading.Event()
            is_running.set()

            # Should not crash
            capture.capture_thread(is_running)

            # Verify terminate was still called
            mock_pyaudio.terminate.assert_called_once()

    @patch('audio.capture.pyaudio.PyAudio')
    def test_get_input_device_index_finds_blackhole(self, mock_pyaudio_class):
        """Test device detection finds BlackHole device"""
        mock_pyaudio = MagicMock()
        mock_pyaudio_class.return_value = mock_pyaudio
        mock_pyaudio.get_device_count.return_value = 3

        # Mock device info
        def get_device_info(index):
            devices = [
                {'name': 'Built-in Microphone'},
                {'name': 'BlackHole 2ch'},
                {'name': 'Built-in Output'}
            ]
            return devices[index]

        mock_pyaudio.get_device_info_by_index.side_effect = get_device_info

        result = AudioCapture.get_input_device_index(None)

        self.assertEqual(result, 1)
        mock_pyaudio.terminate.assert_called_once()

    @patch('audio.capture.pyaudio.PyAudio')
    def test_get_input_device_index_returns_none_when_not_found(self, mock_pyaudio_class):
        """Test device detection returns None when no suitable device found"""
        mock_pyaudio = MagicMock()
        mock_pyaudio_class.return_value = mock_pyaudio
        mock_pyaudio.get_device_count.return_value = 2

        # Mock device info with no matching devices
        def get_device_info(index):
            devices = [
                {'name': 'Built-in Microphone'},
                {'name': 'Built-in Output'}
            ]
            return devices[index]

        mock_pyaudio.get_device_info_by_index.side_effect = get_device_info

        result = AudioCapture.get_input_device_index(None)

        self.assertIsNone(result)
        mock_pyaudio.terminate.assert_called_once()

    @patch('audio.capture.pyaudio.PyAudio')
    def test_get_input_device_index_returns_provided_device(self, mock_pyaudio_class):
        """Test device detection returns provided device index"""
        result = AudioCapture.get_input_device_index(5)

        self.assertEqual(result, 5)
        # Should not create PyAudio instance when device is provided
        mock_pyaudio_class.assert_not_called()


class TestAudioCaptureIntegration(unittest.TestCase):
    """Integration tests for AudioCapture with real PyAudio (if available)"""

    @unittest.skipUnless(
        AudioCapture.get_input_device_index(None) is not None,
        "No suitable audio device found"
    )
    def test_real_device_detection(self):
        """Test detection works with real audio devices"""
        device_index = AudioCapture.get_input_device_index(None)
        self.assertIsNotNone(device_index)
        self.assertIsInstance(device_index, int)
        self.assertGreaterEqual(device_index, 0)


if __name__ == '__main__':
    unittest.main()
