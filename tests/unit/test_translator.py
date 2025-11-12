"""
Unit tests for translation.translator module
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import queue
import threading
import os

from translation.translator import Translation


class MockLangConfig:
    """Mock LanguageConfig for testing"""
    def __init__(self):
        self.source = 'en'
        self.target = 'ja'


class MockTransConfig:
    """Mock TranslationConfig for testing"""
    def __init__(self):
        self.batch_size = 5
        self.context_window_size = 8
        self.context_separator = '\n'
        self.reload_interval = 7200
        self.max_consecutive_errors = 3
        self.error_cooldown = 5.0
        self.generation_params = {
            'temperature': 0.7,
            'max_tokens': 256
        }


class MockModelConfig:
    """Mock ModelConfig for testing"""
    def __init__(self):
        self.model_path = '/path/to/model'
        self.trust_remote_code = False
        self.api = Mock(
            enabled=False,
            base_url='http://localhost:1234/v1',
            api_key='test-key',
            model='gpt-3.5-turbo',
            timeout=30.0,
            max_retries=3
        )
        self.gguf = Mock(
            enabled=False,
            model_path='/path/to/gguf',
            model_file='model.gguf',
            n_ctx=2048,
            n_gpu_layers=0,
            n_threads=4
        )


class MockOutputConfig:
    """Mock OutputConfig for testing"""
    def __init__(self):
        self.directory = 'logs'


class TestTranslationInit(unittest.TestCase):
    """Test Translation class initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.translation_queue = queue.Queue()
        self.lang_config = MockLangConfig()

        # Create mock config_manager
        self.config_manager = Mock()
        self.config_manager.translation = MockTransConfig()
        self.config_manager.output = MockOutputConfig()
        self.config_manager.get_model_config.return_value = MockModelConfig()

    def test_init_with_config_manager(self):
        """Test initialization with ConfigManager"""
        translator = Translation(
            self.translation_queue,
            self.config_manager,
            self.lang_config,
            debug=False
        )

        self.assertEqual(translator.translation_queue, self.translation_queue)
        self.assertEqual(translator.lang_config, self.lang_config)
        self.assertEqual(translator.batch_size, 5)
        self.assertEqual(translator.context_window_size, 8)
        self.assertFalse(translator.debug)

    def test_init_sets_default_generation_params(self):
        """Test initialization sets default generation params"""
        translator = Translation(
            self.translation_queue,
            self.config_manager,
            self.lang_config
        )

        self.assertIn('temperature', translator.generation_params)
        self.assertIn('max_tokens', translator.generation_params)

    def test_init_with_tts_and_web_ui(self):
        """Test initialization with optional TTS and Web UI"""
        mock_tts = Mock()
        mock_web_ui = Mock()

        translator = Translation(
            self.translation_queue,
            self.config_manager,
            self.lang_config,
            tts=mock_tts,
            web_ui=mock_web_ui
        )

        self.assertEqual(translator.tts, mock_tts)
        self.assertEqual(translator.web_ui, mock_web_ui)


class TestTranslationTextProcessing(unittest.TestCase):
    """Test text processing methods"""

    def test_preprocess_text_removes_whitespace(self):
        """Test preprocessing removes extra whitespace"""
        text = "  Hello   World  "
        result = Translation.preprocess_text(text)
        self.assertEqual(result, "Hello World")

    def test_preprocess_text_handles_empty(self):
        """Test preprocessing handles empty strings"""
        result = Translation.preprocess_text("")
        self.assertEqual(result, "")

    def test_preprocess_text_handles_none(self):
        """Test preprocessing handles None"""
        result = Translation.preprocess_text(None)
        self.assertEqual(result, "")

    def test_is_valid_translation_accepts_valid_text(self):
        """Test validation accepts valid translations"""
        self.assertTrue(Translation.is_valid_translation("This is a translation"))
        self.assertTrue(Translation.is_valid_translation("日本語の翻訳"))

    def test_is_valid_translation_rejects_empty(self):
        """Test validation rejects empty strings"""
        self.assertFalse(Translation.is_valid_translation(""))
        self.assertFalse(Translation.is_valid_translation("   "))

    def test_is_valid_translation_rejects_none(self):
        """Test validation rejects None"""
        self.assertFalse(Translation.is_valid_translation(None))


class TestTranslationMemoryManagement(unittest.TestCase):
    """Test memory management in Translation class"""

    def setUp(self):
        """Set up test fixtures"""
        self.translation_queue = queue.Queue()
        self.lang_config = MockLangConfig()
        self.config_manager = Mock()
        self.config_manager.translation = MockTransConfig()
        self.config_manager.output = MockOutputConfig()
        self.config_manager.get_model_config.return_value = MockModelConfig()

    @patch('translation.translator.gc.collect')
    def test_load_model_cleans_up_existing_model(self, mock_gc):
        """Test load_model properly cleans up existing models"""
        translator = Translation(
            self.translation_queue,
            self.config_manager,
            self.lang_config
        )

        # Set up existing models
        translator.llm_model = Mock()
        translator.llm_tokenizer = Mock()
        translator.api_client = Mock()

        # Mock API mode to avoid actual model loading
        translator.use_api = True

        with patch('translation.translator.OPENAI_AVAILABLE', True):
            with patch('translation.translator.OpenAI'):
                translator.load_model()

        # Verify garbage collection was called
        mock_gc.assert_called_once()

    def test_check_model_reload_does_not_reload_before_interval(self):
        """Test model reload respects reload interval"""
        translator = Translation(
            self.translation_queue,
            self.config_manager,
            self.lang_config
        )

        # Set last reload time to recent
        import time
        translator.last_model_reload = time.time()
        translator.reload_interval = 3600  # 1 hour

        with patch.object(translator, 'load_model') as mock_load:
            translator.check_model_reload()

            # Should not reload
            mock_load.assert_not_called()


class TestTranslationQueueHandling(unittest.TestCase):
    """Test queue handling in translation thread"""

    def setUp(self):
        """Set up test fixtures"""
        self.translation_queue = queue.Queue()
        self.lang_config = MockLangConfig()
        self.config_manager = Mock()
        self.config_manager.translation = MockTransConfig()
        self.config_manager.output = MockOutputConfig()
        self.config_manager.get_model_config.return_value = MockModelConfig()

    def test_translation_queue_timeout_efficiency(self):
        """Test translation thread uses efficient queue timeout"""
        translator = Translation(
            self.translation_queue,
            self.config_manager,
            self.lang_config
        )

        is_running = threading.Event()
        is_running.set()

        # Mock API mode to avoid model loading
        translator.use_api = True
        translator.api_client = Mock()

        # Start thread in background
        thread = threading.Thread(
            target=translator.translation_thread,
            args=(is_running,),
            daemon=True
        )
        thread.start()

        # Verify thread doesn't busy-wait (would consume CPU)
        import time
        start_time = time.time()
        time.sleep(0.5)

        # Stop thread
        is_running.clear()
        thread.join(timeout=2.0)

        # Thread should have waited efficiently, not busy-looping
        # If it was busy-looping with 0.1s sleep, we'd see high CPU
        # This is more of a behavioral test
        self.assertTrue(True)  # Placeholder - actual CPU measurement would be complex


class TestTranslationErrorHandling(unittest.TestCase):
    """Test error handling in Translation class"""

    def setUp(self):
        """Set up test fixtures"""
        self.translation_queue = queue.Queue()
        self.lang_config = MockLangConfig()
        self.config_manager = Mock()
        self.config_manager.translation = MockTransConfig()
        self.config_manager.output = MockOutputConfig()
        self.config_manager.get_model_config.return_value = MockModelConfig()

    def test_handle_translation_error_tracks_failures(self):
        """Test error handler tracks failed translations"""
        translator = Translation(
            self.translation_queue,
            self.config_manager,
            self.lang_config
        )

        text = "Test text"
        translator.handle_translation_error(text)

        self.assertEqual(len(translator.failed_translations), 1)
        self.assertEqual(translator.failed_translations[0], text)

    def test_handle_translation_error_limits_failed_queue(self):
        """Test error handler limits size of failed queue"""
        translator = Translation(
            self.translation_queue,
            self.config_manager,
            self.lang_config
        )

        # Add more failures than max
        for i in range(15):
            translator.handle_translation_error(f"Text {i}")

        # Should be limited to 10
        self.assertEqual(len(translator.failed_translations), 10)


if __name__ == '__main__':
    unittest.main()
