"""
Pytest configuration and fixtures
"""

import pytest
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_audio_config():
    """Fixture for mock AudioConfig"""
    from unittest.mock import Mock
    import pyaudio
    import numpy as np

    config = Mock()
    config.format = pyaudio.paInt16
    config.channels = 1
    config.sample_rate = 16000
    config.chunk_size = 1024
    config.numpy_dtype = np.int16
    return config


@pytest.fixture
def mock_lang_config():
    """Fixture for mock LanguageConfig"""
    from unittest.mock import Mock

    config = Mock()
    config.source = 'en'
    config.target = 'ja'
    return config


@pytest.fixture
def mock_translation_config():
    """Fixture for mock TranslationConfig"""
    from unittest.mock import Mock

    config = Mock()
    config.batch_size = 5
    config.context_window_size = 8
    config.context_separator = '\n'
    config.reload_interval = 7200
    config.max_consecutive_errors = 3
    config.error_cooldown = 5.0
    config.generation_params = {
        'temperature': 0.7,
        'max_tokens': 256
    }
    return config


@pytest.fixture
def temp_log_dir(tmp_path):
    """Fixture for temporary log directory"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture(autouse=True)
def cleanup_logs():
    """Auto-cleanup fixture for test logs"""
    yield
    # Cleanup after test
    # Can add cleanup logic here if needed


def pytest_configure(config):
    """Pytest configuration hook"""
    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
    config.addinivalue_line("markers", "requires_audio: Tests requiring audio hardware")
    config.addinivalue_line("markers", "requires_model: Tests requiring ML models")
