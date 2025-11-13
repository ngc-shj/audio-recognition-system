# Audio Recognition System - Comprehensive Code Quality Analysis

**Codebase Size:** ~4,356 lines of Python code

---

## 1. CODE QUALITY ISSUES

### Issue 1.1: Bare Exception Handlers (Critical Security/Maintainability Risk)

**Files:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/tts/text_to_speech.py`
**Lines:** 281, 285, 329
**Severity:** HIGH

**Problem:**
Bare `except:` clauses catch all exceptions including SystemExit, KeyboardInterrupt, and GeneratorExit.

**Current Code:**
```python
# Line 281-286
try:
    os.unlink(mp3_path)
except:
    pass
try:
    os.unlink(wav_path)
except:
    pass
```

**Issues:**
- Masks actual errors
- Makes debugging impossible
- Can hide serious issues like out-of-memory conditions
- Violates PEP 8 guidelines

**Suggested Fix:**
```python
# Line 281-286
try:
    os.unlink(mp3_path)
except (OSError, FileNotFoundError):
    logger.warning(f"Failed to delete temporary file: {mp3_path}")
except Exception as e:
    logger.debug(f"Unexpected error deleting file: {e}")

try:
    os.unlink(wav_path)
except (OSError, FileNotFoundError):
    logger.warning(f"Failed to delete temporary file: {wav_path}")
except Exception as e:
    logger.debug(f"Unexpected error deleting file: {e}")
```

---

### Issue 1.2: Inconsistent Exception Handling Pattern

**Files:** Multiple files (`main_with_translation.py`, `main_transcription_only.py`, `config_manager.py`)
**Severity:** MEDIUM

**Problem:**
Exception handling is inconsistent across the codebase:
- Some places use `logger.info()` for errors
- Some use `logger.error()`
- Some use `print()`

**Examples:**
```python
# main_transcription_only.py, Line 276
except FileNotFoundError as e:
    logger.info("")
    logger.info(f"エラー: {e}")  # Should be logger.error()
    
# main_with_translation.py, Line 366-367
except FileNotFoundError as e:
    logger.error("")  # Correct
    logger.error(f"エラー: {e}")
```

**Suggested Fix:**
Create a standardized error handling pattern:
```python
# utils/error_handler.py (NEW FILE)
from utils.logger import setup_logger
logger = setup_logger(__name__)

class AudioSystemException(Exception):
    """Base exception for audio recognition system"""
    pass

class ConfigurationError(AudioSystemException):
    """Raised when configuration is invalid"""
    pass

def handle_error(error: Exception, context: str = "", exit_code: int = 1):
    """Standardized error handling"""
    logger.error("")
    logger.error(f"Error in {context}: {type(error).__name__}")
    logger.error(f"Message: {str(error)}")
    if isinstance(error, ConfigurationError):
        logger.error("Hint: Check your configuration file")
    sys.exit(exit_code)
```

---

### Issue 1.3: Missing Type Hints in Function Signatures

**Files:** Most files lack comprehensive type hints
**Lines:** Various function definitions
**Severity:** MEDIUM

**Examples:**
```python
# audio/capture.py, Line 24
def __init__(self, audio_config, audio_queue, config_manager=None):
    # Missing type hints

# audio/processing.py, Line 33
def __init__(self, audio_config, audio_queue, processing_queue):
    # Missing type hints

# recognition/speech_recognition.py, Line 159
def has_voice_activity(self, audio_data):
    # Missing type hints
```

**Suggested Fix:**
```python
# audio/capture.py, Line 24
from typing import Optional, Queue
from config_manager import AudioConfig

def __init__(
    self, 
    audio_config: AudioConfig, 
    audio_queue: Queue, 
    config_manager: Optional['ConfigManager'] = None
) -> None:
    """Initialize audio capture with type hints."""
    
# audio/processing.py, Line 33
def __init__(
    self, 
    audio_config: AudioConfig, 
    audio_queue: Queue, 
    processing_queue: Queue
) -> None:
    """Initialize audio processing."""

# recognition/speech_recognition.py, Line 159
def has_voice_activity(self, audio_data: np.ndarray) -> bool:
    """Detect voice activity in audio data."""
```

---

### Issue 1.4: Code Duplication - Configuration Setup

**Files:** `main_with_translation.py`, `main_transcription_only.py`
**Lines:** 160-209 in both files
**Severity:** MEDIUM

**Problem:**
Identical configuration loading and argument override logic in both main files.

**Current Duplication:**
```python
# Both files repeat this pattern (20+ lines):
config = ConfigManager(
    config_path=str(config_path),
    profile=args.profile
)

if args.output_dir:
    config.set_output_dir(args.output_dir)
    logger.info(f"   出力ディレクトリを上書き: {args.output_dir}")

if args.batch_size:
    config.set_batch_size(args.batch_size)
    # ... etc
```

**Suggested Fix:**
```python
# utils/config_setup.py (NEW FILE)
def apply_cli_overrides(
    config: ConfigManager, 
    args: argparse.Namespace
) -> ConfigManager:
    """Apply command-line argument overrides to configuration."""
    if args.output_dir:
        config.set_output_dir(args.output_dir)
        logger.info(f"   出力ディレクトリを上書き: {args.output_dir}")
    
    if hasattr(args, 'batch_size') and args.batch_size:
        config.set_batch_size(args.batch_size)
        logger.info(f"   バッチサイズを上書き: {args.batch_size}")
    
    if args.model_size:
        # ASR model size override
        if 'models' not in config._config:
            config._config['models'] = {}
        # ... rest of logic
    
    if args.debug:
        config.set_debug(True)
        logger.info(f"   デバッグモードを上書き: 有効")
    
    if args.source_lang:
        target = args.target_lang if hasattr(args, 'target_lang') else config.language.target
        config.set_language(args.source_lang, target)
        logger.info(f"   入力言語を上書き: {args.source_lang}")
    
    return config
```

Then in both main files:
```python
# main_with_translation.py, Line 186-223
from utils.config_setup import apply_cli_overrides

config = ConfigManager(
    config_path=str(config_path),
    profile=args.profile
)
config = apply_cli_overrides(config, args)
```

---

### Issue 1.5: Missing Input Validation

**Files:** `config_manager.py`, `web_ui_bridge.py`, `translation/translator.py`
**Severity:** MEDIUM

**Problem:**
No validation of critical parameters:
- Empty file paths
- Invalid language codes
- Invalid batch sizes
- Invalid URLs

**Examples:**
```python
# config_manager.py, Line 579
def set_output_dir(self, directory: str) -> None:
    if 'output' not in self._config:
        self._config['output'] = {}
    self._config['output']['directory'] = directory
    # No validation that directory is valid or writable

# web_ui_bridge.py, Line 28
def __init__(self, server_url: str = "http://localhost:8000", enabled: bool = True):
    self.server_url = server_url
    self.enabled = enabled
    # No validation of URL format or reachability
```

**Suggested Fix:**
```python
# config_manager.py, Line 579
def set_output_dir(self, directory: str) -> None:
    """Set output directory with validation."""
    if not directory:
        raise ValueError("Output directory cannot be empty")
    
    from pathlib import Path
    output_path = Path(directory)
    
    # Validate path is writable
    try:
        output_path.mkdir(parents=True, exist_ok=True)
        # Test write permission
        test_file = output_path / ".write_test"
        test_file.touch()
        test_file.unlink()
    except (OSError, PermissionError) as e:
        raise ValueError(f"Output directory is not writable: {e}")
    
    if 'output' not in self._config:
        self._config['output'] = {}
    self._config['output']['directory'] = directory
    self._output = None  # Invalidate cache

# web_ui_bridge.py, Line 28
from urllib.parse import urlparse

def __init__(self, server_url: str = "http://localhost:8000", enabled: bool = True):
    """Initialize Web UI Bridge with URL validation."""
    # Validate URL format
    try:
        result = urlparse(server_url)
        if not all([result.scheme, result.netloc]):
            raise ValueError(f"Invalid URL format: {server_url}")
    except Exception as e:
        raise ValueError(f"Invalid server URL: {e}")
    
    self.server_url = server_url
    self.enabled = enabled
    self.broadcast_url = f"{server_url}/api/broadcast"
```

---

## 2. PERFORMANCE OPTIMIZATIONS

### Issue 2.1: Inefficient Queue Handling in Translation Thread

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/translation/translator.py`
**Lines:** 344-355
**Severity:** HIGH

**Problem:**
The translation thread uses busy-waiting with `queue.Queue.get_nowait()` in a loop without throttling.

**Current Code:**
```python
# translation/translator.py, Lines 343-355
while len(texts_to_translate) < self.batch_size:
    try:
        item = self.translation_queue.get_nowait()
        # ... process
    except queue.Empty:
        if self.debug:
            logger.info("翻訳キューが空です")
        break
```

**Issues:**
- Causes CPU spinning when queue is empty
- get_nowait() doesn't provide backpressure
- No exponential backoff

**Suggested Fix:**
```python
# translation/translator.py, Lines 343-365
def _get_batch_from_queue(self, batch_size: int, timeout: float = 0.1) -> List[dict]:
    """Get a batch of texts from queue with smart timeout."""
    texts_to_translate = []
    
    # Try to get at least one item with timeout
    try:
        item = self.translation_queue.get(timeout=timeout)
        texts_to_translate.append(item)
    except queue.Empty:
        return texts_to_translate
    
    # Collect remaining items without blocking (non-greedy)
    while len(texts_to_translate) < batch_size:
        try:
            item = self.translation_queue.get_nowait()
            texts_to_translate.append(item)
        except queue.Empty:
            break
    
    return texts_to_translate

# In translation_thread:
texts_to_translate = []

# Retry failed translations first
while self.failed_translations and len(texts_to_translate) < self.batch_size:
    texts_to_translate.append(self.failed_translations.pop(0))

# Get new items from queue
remaining_needed = self.batch_size - len(texts_to_translate)
if remaining_needed > 0:
    new_items = self._get_batch_from_queue(remaining_needed, timeout=0.2)
    texts_to_translate.extend(new_items)

if not texts_to_translate:
    if not is_running.is_set():
        break
    time.sleep(0.5)  # Back off when no work available
    continue
```

---

### Issue 2.2: Memory Leak in Model Loading

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/translation/translator.py`
**Lines:** 220-230
**Severity:** HIGH

**Problem:**
Models are loaded but previous references are not properly cleaned up before reassignment.

**Current Code:**
```python
# translation/translator.py, Lines 223-226
def load_model(self):
    try:
        # 既存モデルのクリーンアップ
        del self.llm_model
        del self.llm_tokenizer
        del self.api_client
        # ... load new model
```

**Issues:**
- `del` statement doesn't guarantee garbage collection
- No explicit cleanup of GPU/MPS cache
- Can cause memory accumulation on repeated reloads
- Race condition if model is used while being loaded

**Suggested Fix:**
```python
# translation/translator.py, Lines 220-240
def load_model(self):
    """Load translation model with proper memory cleanup."""
    try:
        # Cleanup existing model with explicit garbage collection
        self._cleanup_model()
        
        # APIサーバーを使用する場合
        if self.use_api:
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    "openai package is required for API mode. "
                    "Install it with: pip install openai"
                )

            logger.info(f"APIサーバーに接続中: {self.api_base_url}")
            logger.info(f"使用モデル: {self.api_model}")

            # OpenAI互換APIクライアントの初期化
            self.api_client = OpenAI(
                base_url=self.api_base_url,
                api_key=self.api_key or "dummy-key",
                timeout=self.api_timeout,
                max_retries=self.api_max_retries
            )
            self.llm_model = None
            self.llm_tokenizer = None
            self.model_type = 'api'
            self.is_gpt_oss = False

            logger.info("APIクライアントの初期化完了")
            return
        
        # ... rest of model loading

    except Exception as e:
        logger.error(f"モデルの再ロード中にエラーが発生しました: {e}")
        self._cleanup_model()  # Cleanup on error too
        raise

def _cleanup_model(self) -> None:
    """Clean up model resources properly."""
    try:
        if hasattr(self, 'llm_model') and self.llm_model is not None:
            del self.llm_model
            self.llm_model = None
        
        if hasattr(self, 'llm_tokenizer') and self.llm_tokenizer is not None:
            del self.llm_tokenizer
            self.llm_tokenizer = None
        
        if hasattr(self, 'api_client') and self.api_client is not None:
            del self.api_client
            self.api_client = None
        
        # Explicit GPU/MPS cache cleanup
        if sys.platform == 'darwin':
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        else:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        # Force garbage collection
        gc.collect()
        
    except Exception as e:
        logger.warning(f"Error during model cleanup: {e}")
```

---

### Issue 2.3: Inefficient Deque Usage in Audio Processing

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/audio/processing.py`
**Lines:** 73, 127-131
**Severity:** MEDIUM

**Problem:**
Converting deque to list repeatedly causes unnecessary memory allocation and performance overhead.

**Current Code:**
```python
# audio/processing.py, Line 127-131
if silence_start is not None:
    silence_samples = int((current_time - silence_start) * self.config.sample_rate)
    valid_samples = len(buffer) - silence_samples
    if valid_samples > 0:
        audio_data = np.array(list(buffer)[:valid_samples])  # ← Inefficient conversion
    else:
        audio_data = np.array(buffer)  # ← Also conversion here
```

**Suggested Fix:**
```python
# audio/processing.py, Lines 127-131
if silence_start is not None:
    silence_samples = int((current_time - silence_start) * self.config.sample_rate)
    valid_samples = len(buffer) - silence_samples
    if valid_samples > 0:
        # Efficient extraction from deque
        audio_data = np.array(list(itertools.islice(buffer, 0, valid_samples)), dtype=self.config.numpy_dtype)
    else:
        audio_data = np.array(buffer, dtype=self.config.numpy_dtype)
else:
    audio_data = np.array(buffer, dtype=self.config.numpy_dtype)
```

Or better, use numpy array directly:
```python
# audio/processing.py, Line 73 - Initialize differently
self.buffer_samples = []  # Use list instead of deque for easier numpy conversion

# audio/processing.py, Line 83
self.buffer_samples.extend(data)
if len(self.buffer_samples) > self.max_buffer_size:
    self.buffer_samples = self.buffer_samples[-self.max_buffer_size:]

# audio/processing.py, Line 127-131
audio_data = np.array(
    self.buffer_samples[:valid_samples] if silence_start else self.buffer_samples,
    dtype=self.config.numpy_dtype
)
```

---

### Issue 2.4: Unnecessary Object Recreation in Tight Loop

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/audio/capture.py`
**Lines:** 48-52
**Severity:** MEDIUM

**Problem:**
Audio callback creates numpy array from buffer every frame, which is called frequently.

**Current Code:**
```python
# audio/capture.py, Line 48-52
def audio_callback(self, in_data, frame_count, time_info, status):
    """PyAudioストリームのコールバック関数"""
    audio_data = np.frombuffer(in_data, dtype=self.audio_config.numpy_dtype)
    self.audio_queue.put(audio_data)  # ← Puts reference, queue handling can be optimized
    return (in_data, pyaudio.paContinue)
```

**Suggested Fix:**
```python
# audio/capture.py, Line 48-52
def audio_callback(self, in_data, frame_count, time_info, status):
    """PyAudioストリームのコールバック関数 with improved efficiency"""
    try:
        # Convert to numpy directly (already efficient)
        audio_data = np.frombuffer(in_data, dtype=self.audio_config.numpy_dtype)
        
        # Check queue size to avoid unbounded growth
        if self.audio_queue.qsize() > 100:  # Backpressure threshold
            logger.warning("Audio queue overflow - dropping frames")
            return (in_data, pyaudio.paContinue)
        
        self.audio_queue.put(audio_data)
    except Exception as e:
        logger.error(f"Error in audio callback: {e}")
    
    return (in_data, pyaudio.paContinue)
```

---

## 3. ARCHITECTURE IMPROVEMENTS

### Issue 3.1: Tight Coupling Between Modules

**Files:** `main_with_translation.py`, `recognition/speech_recognition.py`, `translation/translator.py`
**Severity:** HIGH

**Problem:**
Components have direct dependencies on concrete implementations rather than using abstraction.

**Current Code:**
```python
# main_with_translation.py, Lines 251-259
speech_recognition = SpeechRecognition(
    config.audio,
    processing_queue,
    translation_queue,
    config,  # ConfigManager directly passed
    config.language,
    debug=debug_mode,
    web_ui=web_ui
)
```

**Issues:**
- Hard to test components in isolation
- Web UI Bridge is optional but tightly coupled
- Config is directly accessed instead of through interface
- Can't swap implementations

**Suggested Fix:**
```python
# utils/interfaces.py (NEW FILE)
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class ConfigProvider(ABC):
    """Abstract interface for configuration"""
    @property
    @abstractmethod
    def audio(self): pass
    
    @property
    @abstractmethod
    def language(self): pass
    
    @abstractmethod
    def get_model_config(self, model_type: str): pass

class MessageBroker(ABC):
    """Abstract interface for message handling"""
    @abstractmethod
    def send_recognized_text(self, text: str, language: str, pair_id: Optional[str] = None): pass
    
    @abstractmethod
    def send_translated_text(self, text: str, source: Optional[str] = None, pair_id: Optional[str] = None): pass

class NullMessageBroker(MessageBroker):
    """No-op implementation for testing"""
    def send_recognized_text(self, text: str, language: str, pair_id: Optional[str] = None): pass
    def send_translated_text(self, text: str, source: Optional[str] = None, pair_id: Optional[str] = None): pass

# Updated main_with_translation.py
from utils.interfaces import ConfigProvider, MessageBroker

speech_recognition = SpeechRecognition(
    config.audio,
    processing_queue,
    translation_queue,
    config_provider=config,  # Use abstraction
    lang_config=config.language,
    debug=debug_mode,
    message_broker=web_ui or NullMessageBroker()  # Always have a broker
)
```

---

### Issue 3.2: Missing Strategy Pattern for Model Loading

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/translation/translator.py`
**Lines:** 220-327
**Severity:** MEDIUM

**Problem:**
Model loading has multiple if/elif branches for different model types (API, GGUF, MLX, Transformers), violating SOLID principles.

**Current Code:**
```python
# translation/translator.py, Lines 254-323
if self.use_api and OPENAI_AVAILABLE:
    # ... 20 lines of API setup
elif self.use_gguf and LLAMA_CPP_AVAILABLE:
    # ... 25 lines of GGUF setup
elif sys.platform == 'darwin':
    # ... 15 lines of MLX setup
else:
    # ... 20 lines of Transformers setup
```

**Suggested Fix:**
```python
# utils/model_loaders.py (NEW FILE)
from abc import ABC, abstractmethod
from typing import Tuple, Optional

class ModelLoader(ABC):
    """Abstract model loader strategy"""
    @abstractmethod
    def load(self) -> Tuple[Any, Optional[Any]]:
        """Load model and tokenizer (if applicable)"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources"""
        pass

class APIModelLoader(ModelLoader):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int, max_retries: int):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.api_client = None
    
    def load(self) -> Tuple[Any, None]:
        from openai import OpenAI
        self.api_client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "dummy-key",
            timeout=self.api_timeout,
            max_retries=self.api_max_retries
        )
        logger.info(f"APIサーバーに接続: {self.base_url}")
        return self.api_client, None
    
    def cleanup(self) -> None:
        if self.api_client:
            del self.api_client
            self.api_client = None

class GGUFModelLoader(ModelLoader):
    def __init__(self, model_path: str, model_file: str, n_ctx: int, n_gpu_layers: int, n_threads: int):
        self.model_path = model_path
        self.model_file = model_file
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.model = None
    
    def load(self) -> Tuple[Any, None]:
        from llama_cpp import Llama
        # ... GGUF loading logic
        return self.model, None
    
    def cleanup(self) -> None:
        if self.model:
            del self.model
            self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

# Usage in Translation class
class Translation:
    def load_model(self):
        self._cleanup_model()
        
        if self.use_api:
            loader = APIModelLoader(
                self.api_base_url,
                self.api_key,
                self.api_model,
                self.api_timeout,
                self.api_max_retries
            )
        elif self.use_gguf:
            loader = GGUFModelLoader(...)
        elif sys.platform == 'darwin':
            loader = MLXModelLoader(...)
        else:
            loader = TransformersModelLoader(...)
        
        self.llm_model, self.llm_tokenizer = loader.load()
        self.model_loader = loader
```

---

### Issue 3.3: Missing Dependency Injection

**Files:** Multiple main files
**Severity:** MEDIUM

**Problem:**
Hard-coded component creation makes testing and configuration difficult.

**Suggested Fix:**
```python
# utils/container.py (NEW FILE)
from typing import Optional
from dataclasses import dataclass

@dataclass
class ComponentContainer:
    """Dependency injection container for audio system components"""
    config: ConfigManager
    audio_capture: AudioCapture
    audio_processing: AudioProcessing
    speech_recognition: SpeechRecognition
    translation: Optional[Translation] = None
    resource_manager: Optional[ResourceManager] = None
    web_ui: Optional[MessageBroker] = None
    
    @staticmethod
    def create_transcription_system(
        config_path: str,
        profile: str = "production",
        enable_web_ui: bool = False,
        web_ui_url: str = "http://localhost:8000"
    ) -> 'ComponentContainer':
        """Factory method to create all components"""
        config = ConfigManager(config_path, profile)
        
        # Create queues
        audio_queue = queue.Queue()
        processing_queue = queue.Queue()
        
        # Create components
        audio_capture = AudioCapture(config.audio, audio_queue, config.audio)
        audio_processing = AudioProcessing(config.audio, audio_queue, processing_queue)
        
        web_ui = None
        if enable_web_ui:
            try:
                web_ui = WebUIBridge(server_url=web_ui_url, enabled=True)
            except Exception as e:
                logger.warning(f"Failed to initialize Web UI: {e}")
        
        speech_recognition = SpeechRecognition(
            config.audio,
            processing_queue,
            None,  # No translation
            config,
            config.language,
            web_ui=web_ui
        )
        
        resource_manager = ResourceManager(config)
        
        return ComponentContainer(
            config=config,
            audio_capture=audio_capture,
            audio_processing=audio_processing,
            speech_recognition=speech_recognition,
            resource_manager=resource_manager,
            web_ui=web_ui
        )

# Usage in main files
from utils.container import ComponentContainer

container = ComponentContainer.create_transcription_system(
    config_path=args.config,
    profile=args.profile,
    enable_web_ui=args.web_ui,
    web_ui_url=args.web_ui_url
)

system = AudioTranscriptionSystem(
    audio_capture=container.audio_capture,
    audio_processing=container.audio_processing,
    speech_recognition=container.speech_recognition,
    resource_manager=container.resource_manager,
    debug=container.config.is_debug_enabled()
)
```

---

## 4. CONFIGURATION & USABILITY

### Issue 4.1: Missing Validation for Critical Configuration

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/config_manager.py`
**Severity:** MEDIUM

**Problem:**
Config values are loaded but never validated for correctness.

**Examples of Missing Validation:**
- Sample rate must be > 0
- Channels must be 1 or 2
- Batch size must be > 0
- Language codes must be valid ISO 639-1
- Timeouts must be positive

**Suggested Fix:**
```python
# config_manager.py - Add validation methods
class ConfigValidator:
    """Validate configuration values"""
    
    VALID_LANGUAGES = {
        'ja', 'en', 'zh', 'ko', 'fr', 'de', 'es', 'it', 'ru', 'ar', 'pt', 'hi'
    }
    
    VALID_SAMPLE_RATES = {8000, 16000, 44100, 48000}
    VALID_CHANNELS = {1, 2}
    VALID_FORMATS = {'int8', 'int16', 'int32', 'float32'}
    
    @staticmethod
    def validate_audio_config(audio_config: AudioConfig) -> None:
        """Validate audio configuration"""
        if audio_config.sample_rate not in ConfigValidator.VALID_SAMPLE_RATES:
            raise ValueError(
                f"Invalid sample_rate {audio_config.sample_rate}. "
                f"Must be one of: {ConfigValidator.VALID_SAMPLE_RATES}"
            )
        
        if audio_config.channels not in ConfigValidator.VALID_CHANNELS:
            raise ValueError(
                f"Invalid channels {audio_config.channels}. "
                f"Must be 1 or 2"
            )
        
        if audio_config.buffer_duration <= 0:
            raise ValueError("buffer_duration must be positive")
        
        if audio_config.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
    
    @staticmethod
    def validate_language_config(lang_config: LanguageConfig) -> None:
        """Validate language configuration"""
        if lang_config.source not in ConfigValidator.VALID_LANGUAGES:
            raise ValueError(
                f"Invalid source language: {lang_config.source}. "
                f"Must be one of: {ConfigValidator.VALID_LANGUAGES}"
            )
        
        if lang_config.target not in ConfigValidator.VALID_LANGUAGES:
            raise ValueError(
                f"Invalid target language: {lang_config.target}. "
                f"Must be one of: {ConfigValidator.VALID_LANGUAGES}"
            )
    
    @staticmethod
    def validate_translation_config(trans_config: TranslationConfig) -> None:
        """Validate translation configuration"""
        if trans_config.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        
        if trans_config.context_window_size < 0:
            raise ValueError("context_window_size cannot be negative")
        
        if trans_config.max_consecutive_errors <= 0:
            raise ValueError("max_consecutive_errors must be positive")

# Use in ConfigManager.__init__:
def __init__(self, config_path: Optional[str] = None, profile: str = "production"):
    # ... existing code ...
    
    # Validate configuration
    try:
        ConfigValidator.validate_audio_config(self.audio)
        ConfigValidator.validate_language_config(self.language)
        ConfigValidator.validate_translation_config(self.translation)
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise ConfigurationError(str(e))
```

---

### Issue 4.2: Unclear Configuration Defaults

**File:** `config_manager.py`
**Severity:** MEDIUM

**Problem:**
Many hardcoded defaults are scattered and not documented.

**Current:**
```python
# Line 392-401
dynamic_buffer_config = DynamicBufferConfig(
    min_duration=db_data.get('min_duration', 2.0),
    max_duration=db_data.get('max_duration', 30.0),
    short_pause=db_data.get('short_pause', 0.3),
    medium_pause=db_data.get('medium_pause', 0.8),
    long_pause=db_data.get('long_pause', 1.5)
)
```

**Suggested Fix:**
```python
# Create a defaults file
# config_defaults.py
"""Default configuration values for audio recognition system"""

AUDIO_DEFAULTS = {
    'sample_rate': 16000,
    'channels': 1,
    'format': 'int16',
    'chunk_size': 1024,
    'buffer_duration': 2.0,
}

DYNAMIC_BUFFER_DEFAULTS = {
    'min_duration': 2.0,     # Minimum audio segment duration
    'max_duration': 30.0,    # Maximum audio segment duration before force-splitting
    'short_pause': 0.3,      # Short pause threshold (not used for segmentation)
    'medium_pause': 0.8,     # Medium pause threshold for segmentation
    'long_pause': 1.5,       # Long pause threshold for segmentation
}

VOICE_DETECTION_DEFAULTS = {
    'silence_threshold': 0.02,
    'voice_activity_threshold': 0.05,
    'silence_duration': 0.5,
    'zero_crossing_rate_threshold': 0.1,
}

TRANSLATION_DEFAULTS = {
    'batch_size': 5,
    'context_window_size': 8,
    'context_separator': '\n',
    'reload_interval': 3600,
    'max_consecutive_errors': 5,
    'error_cooldown': 10,
}

MODEL_DEFAULTS = {
    'asr_model_size': 'large-v3-turbo',
    'trust_remote_code': False,
}

# Then use in config_manager.py
from config_defaults import DYNAMIC_BUFFER_DEFAULTS

dynamic_buffer_config = DynamicBufferConfig(
    **{k: db_data.get(k, v) for k, v in DYNAMIC_BUFFER_DEFAULTS.items()}
)
```

---

## 5. TESTING & RELIABILITY

### Issue 5.1: No Unit Tests

**Severity:** CRITICAL

**Problem:**
Zero test files in the codebase. No test coverage for:
- Configuration loading and validation
- Audio processing pipelines
- Translation logic
- Error handling paths

**Suggested Fix:**
```python
# tests/test_config_manager.py
import pytest
from config_manager import ConfigManager, ConfigurationError

class TestConfigManager:
    @pytest.fixture
    def valid_config(self, tmp_path):
        """Create a valid test config"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
language:
  source: en
  target: ja
audio:
  sample_rate: 16000
  channels: 1
  format: int16
        """)
        return ConfigManager(config_path=str(config_file))
    
    def test_load_valid_config(self, valid_config):
        assert valid_config.language.source == 'en'
        assert valid_config.audio.sample_rate == 16000
    
    def test_invalid_sample_rate(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
audio:
  sample_rate: 99999
        """)
        with pytest.raises(ConfigurationError):
            ConfigManager(config_path=str(config_file))
    
    def test_set_output_dir_creates_directory(self, valid_config, tmp_path):
        output_dir = tmp_path / "output"
        valid_config.set_output_dir(str(output_dir))
        assert output_dir.exists()
    
    def test_set_output_dir_invalid_path(self, valid_config):
        with pytest.raises(ValueError):
            valid_config.set_output_dir("/root/cannot_write_here")

# tests/test_audio_processing.py
import pytest
import numpy as np
from audio.processing import AudioProcessing
from config_manager import AudioConfig

class TestAudioProcessing:
    @pytest.fixture
    def config(self):
        return AudioConfig(
            format_str='int16',
            format=2,  # pyaudio.paInt16
            sample_rate=16000,
            channels=1,
            chunk_size=1024,
            buffer_duration=2.0,
            numpy_dtype=np.int16,
            buffer_size=32000,
            silence_threshold=0.02,
            voice_activity_threshold=0.05,
            silence_duration=0.5,
        )
    
    def test_voice_activity_detection(self, config):
        processor = AudioProcessing(config, None, None)
        
        # Test with silent audio (zeros)
        silent_audio = np.zeros(1024, dtype=np.int16)
        assert not processor.has_voice_activity(silent_audio)
        
        # Test with speech-like audio (with energy and zero crossings)
        speech_audio = np.array([100, -50, 80, -60] * 256, dtype=np.int16)
        assert processor.has_voice_activity(speech_audio)
```

---

### Issue 5.2: Race Conditions in Threading

**Files:** `main_with_translation.py`, `audio/capture.py`
**Severity:** HIGH

**Problem:**
Global variable `_system_instance` is accessed without synchronization.

**Current Code:**
```python
# main_with_translation.py, Lines 41-42, 355-363
_system_instance = None

# ... later in main()
_system_instance = AudioRecognitionSystem(...)
_system_instance.run()
```

**Issues:**
- No lock protecting access to `_system_instance`
- Web UI or other threads could access while being written
- Can cause AttributeError or undefined behavior

**Suggested Fix:**
```python
# main_with_translation.py
import threading

# Global instance with lock
_system_instance_lock = threading.RLock()
_system_instance: Optional[AudioRecognitionSystem] = None

def get_system_instance() -> Optional[AudioRecognitionSystem]:
    """Thread-safe getter for system instance"""
    with _system_instance_lock:
        return _system_instance

def set_system_instance(instance: Optional[AudioRecognitionSystem]) -> None:
    """Thread-safe setter for system instance"""
    global _system_instance
    with _system_instance_lock:
        _system_instance = instance

# In main()
system = AudioRecognitionSystem(...)
set_system_instance(system)
system.run()
set_system_instance(None)  # Clear on shutdown

# For web_ui_bridge or other external access
if system := get_system_instance():
    system.stop()  # Use walrus operator for Python 3.8+
```

---

### Issue 5.3: Missing Resource Cleanup

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/audio/capture.py`
**Lines:** 54-100
**Severity:** HIGH

**Problem:**
PyAudio resources might not be cleaned up properly on exception.

**Current Code:**
```python
# audio/capture.py, Lines 54-100
def capture_thread(self, is_running):
    audio = None
    stream = None

    try:
        audio = pyaudio.PyAudio()
        stream = audio.open(...)
        # ... processing loop
    except Exception as e:
        logger.error(f"音声キャプチャエラー: {e}")
    finally:
        if stream is not None:
            try:
                if stream.is_active():
                    stream.stop_stream()
                time.sleep(0.2)
                stream.close()
            except Exception as e:
                logger.error(f"ストリームクローズエラー: {e}")
        
        if audio is not None:
            try:
                audio.terminate()
            except Exception as e:
                logger.error(f"PyAudio終了エラー: {e}")
```

**Issues:**
- Good finally block, but can be improved with context managers
- No protection against double cleanup
- No timeout on cleanup

**Suggested Fix:**
```python
# utils/context_managers.py (NEW FILE)
from contextlib import contextmanager
import pyaudio
import time

@contextmanager
def pyaudio_stream(format, channels, rate, input=True, input_device_index=None,
                   frames_per_buffer=1024, stream_callback=None):
    """Context manager for PyAudio stream with automatic cleanup"""
    audio = None
    stream = None
    
    try:
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=format,
            channels=channels,
            rate=rate,
            input=input,
            input_device_index=input_device_index,
            frames_per_buffer=frames_per_buffer,
            stream_callback=stream_callback
        )
        yield stream
    finally:
        # Cleanup with proper error handling
        cleanup_timeout = 5.0  # seconds
        cleanup_start = time.time()
        
        if stream is not None:
            try:
                if stream.is_active():
                    stream.stop_stream()
                time.sleep(0.2)
                stream.close()
            except Exception as e:
                logger.error(f"Stream close error: {e}")
        
        if audio is not None:
            try:
                audio.terminate()
            except Exception as e:
                logger.error(f"PyAudio terminate error: {e}")
        
        elapsed = time.time() - cleanup_start
        if elapsed > cleanup_timeout:
            logger.warning(f"Cleanup took {elapsed:.1f}s (timeout: {cleanup_timeout}s)")

# Updated audio/capture.py
from utils.context_managers import pyaudio_stream

def capture_thread(self, is_running):
    try:
        with pyaudio_stream(
            format=self.audio_config.format,
            channels=self.audio_config.channels,
            rate=self.audio_config.sample_rate,
            input=True,
            input_device_index=self.input_device_index,
            frames_per_buffer=self.audio_config.chunk_size,
            stream_callback=self.audio_callback
        ) as stream:
            logger.info(f"音声キャプチャスレッド開始 (デバイスインデックス: {self.input_device_index})")
            
            stream.start_stream()
            
            while is_running.is_set():
                time.sleep(0.1)
    
    except Exception as e:
        logger.error(f"音声キャプチャエラー: {e}")
    finally:
        logger.info("音声キャプチャスレッド終了")
```

---

### Issue 5.4: Edge Cases Not Handled

**File:** `audio/processing.py`
**Lines:** 159-182
**Severity:** MEDIUM

**Problem:**
Voice activity detection has edge cases that aren't handled.

**Current Code:**
```python
# audio/processing.py, Lines 159-182
def has_voice_activity(self, audio_data):
    normalized_data = self.normalize_audio(audio_data)
    
    rms = np.sqrt(np.mean(normalized_data**2))
    has_energy = rms > self.config.voice_activity_threshold
    
    zero_crossings = np.sum(np.abs(np.diff(np.sign(normalized_data)))) / (2 * len(normalized_data))
    has_speech_characteristics = zero_crossings > self.zero_crossing_rate_threshold
    
    return has_energy and has_speech_characteristics
```

**Edge Cases Not Handled:**
- Empty audio_data (len=0)
- All zeros in audio
- NaN or inf values from normalization
- Division by zero if len=1

**Suggested Fix:**
```python
# audio/processing.py, Lines 159-182
def has_voice_activity(self, audio_data: np.ndarray) -> bool:
    """
    Detect voice activity with edge case handling.
    
    Args:
        audio_data: Audio samples
    
    Returns:
        True if voice activity detected, False otherwise
    
    Raises:
        ValueError: If audio_data is invalid
    """
    # Edge case: empty audio
    if len(audio_data) == 0:
        return False
    
    # Edge case: single sample
    if len(audio_data) == 1:
        return abs(audio_data[0]) > self.config.voice_activity_threshold
    
    try:
        normalized_data = self.normalize_audio(audio_data)
        
        # Handle NaN or inf values
        if not np.all(np.isfinite(normalized_data)):
            logger.warning("Invalid values in audio data (NaN or inf)")
            return False
        
        # Energy-based detection with bounds check
        rms = np.sqrt(np.mean(normalized_data**2))
        if not np.isfinite(rms):
            return False
        
        has_energy = rms > self.config.voice_activity_threshold
        
        # Zero crossing detection with division by zero protection
        diff = np.diff(np.sign(normalized_data))
        zero_crossings = np.sum(np.abs(diff)) / (2.0 * len(normalized_data))
        
        has_speech_characteristics = zero_crossings > self.zero_crossing_rate_threshold
        
        # Both conditions must be met
        return has_energy and has_speech_characteristics
    
    except Exception as e:
        logger.warning(f"Error in voice activity detection: {e}")
        return False
```

---

## 6. SECURITY CONCERNS

### Issue 6.1: Unsafe Model Loading with trust_remote_code

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/translation/translator.py`
**Lines:** 308-311, 312-318
**Severity:** HIGH

**Problem:**
`trust_remote_code=True` allows arbitrary code execution from untrusted models.

**Current Code:**
```python
# translation/translator.py, Lines 308-318
self.llm_tokenizer = AutoTokenizer.from_pretrained(
    self.model_path,
    trust_remote_code=self.trust_remote_code  # Could be True!
)
self.llm_model = AutoModelForCausalLM.from_pretrained(
    self.model_path,
    torch_dtype="auto",
    device_map="auto",
    low_cpu_mem_usage=True,
    trust_remote_code=self.trust_remote_code,  # Could be True!
)
```

**Issues:**
- Default is False (good), but if enabled, allows arbitrary code execution
- No documentation warning about risks
- No validation of model source

**Suggested Fix:**
```python
# translation/translator.py, Line ~220

def load_model(self):
    """Load translation model with security checks"""
    try:
        # Check model source before enabling trust_remote_code
        if self.trust_remote_code:
            logger.warning(
                "⚠️  trust_remote_code is enabled. This allows arbitrary code execution "
                "from untrusted model files. Only use with models from trusted sources."
            )
            # Optional: Add confirmation for interactive use
            if os.isatty(sys.stdin.fileno()):  # Only if running interactively
                response = input(
                    "Continue loading model with trust_remote_code=True? (yes/no): "
                )
                if response.lower() != 'yes':
                    raise ValueError("Model loading cancelled by user")
        
        # Rest of model loading...
        self.llm_model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype="auto",
            device_map="auto",
            low_cpu_mem_usage=True,
            trust_remote_code=self.trust_remote_code,
        )
```

Also add documentation:
```python
# config_manager.py

@dataclass
class ModelConfig:
    """モデル設定データクラス"""
    model_path: str
    model_size: Optional[str] = None
    gguf: GGUFConfig = None
    api: APIConfig = None
    trust_remote_code: bool = False  # SECURITY: Only enable for trusted models!
    # New field for model verification
    model_source: Optional[str] = None  # 'huggingface', 'local', etc.
```

---

### Issue 6.2: Missing API Key Validation

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/translation/translator.py`
**Lines:** 240-245
**Severity:** MEDIUM

**Problem:**
API keys are passed without validation or sanitization.

**Current Code:**
```python
# translation/translator.py, Lines 240-245
self.api_client = OpenAI(
    base_url=self.api_base_url,
    api_key=self.api_key or "dummy-key",  # ← Defaults to dummy!
    timeout=self.api_timeout,
    max_retries=self.api_max_retries
)
```

**Issues:**
- "dummy-key" placeholder is used
- No validation that key is valid format
- No warning if key is not provided
- Key could be logged in error messages

**Suggested Fix:**
```python
# utils/security.py (NEW FILE)
import re
from typing import Optional

class APIKeyValidator:
    """Validate and sanitize API keys"""
    
    # Patterns for common API key formats
    OPENAI_KEY_PATTERN = re.compile(r'^sk-[A-Za-z0-9]{20,}$')
    OLLAMA_KEY_PATTERN = re.compile(r'^[A-Za-z0-9-]{20,}$')
    
    @staticmethod
    def validate_openai_key(api_key: Optional[str]) -> bool:
        """Validate OpenAI API key format"""
        if not api_key:
            return False
        return APIKeyValidator.OPENAI_KEY_PATTERN.match(api_key) is not None
    
    @staticmethod
    def mask_key(api_key: Optional[str], show_chars: int = 4) -> str:
        """Mask API key for logging"""
        if not api_key or len(api_key) < show_chars:
            return "***"
        return api_key[:show_chars] + "***" + api_key[-show_chars:]

# translation/translator.py, Updated
def load_model(self):
    try:
        # ... cleanup ...
        
        if self.use_api:
            if not OPENAI_AVAILABLE:
                raise ImportError(...)
            
            logger.info(f"APIサーバーに接続中: {self.api_base_url}")
            logger.info(f"使用モデル: {self.api_model}")
            
            # Validate API configuration
            if not self.api_key:
                logger.warning(
                    "API key not provided. LM Studio and similar servers may work "
                    "without authentication, but some servers require it."
                )
            elif not APIKeyValidator.validate_openai_key(self.api_key):
                logger.warning(
                    f"API key format looks incorrect: {APIKeyValidator.mask_key(self.api_key)}"
                )
            
            # Initialize with masking for logs
            masked_key = APIKeyValidator.mask_key(self.api_key)
            logger.debug(f"API key (masked): {masked_key}")
            
            self.api_client = OpenAI(
                base_url=self.api_base_url,
                api_key=self.api_key or None,  # Pass None instead of "dummy-key"
                timeout=self.api_timeout,
                max_retries=self.api_max_retries
            )
            
            logger.info("APIクライアント初期化完了")
            return
```

---

### Issue 6.3: No Input Sanitization for File Operations

**File:** `/Users/noguchi/ghq/github.com/ngc-shj/audio-recognition-system/recognition/speech_recognition.py`
**Lines:** 53-56
**Severity:** MEDIUM

**Problem:**
File paths from config are used without sanitization, could allow path traversal.

**Current Code:**
```python
# recognition/speech_recognition.py, Lines 53-56
self.log_file_path = os.path.join(
    self.output_dir,
    f"recognized_audio_log_{lang_config.source}_{current_time}.txt"
)
```

**Issues:**
- `lang_config.source` is not validated
- Could contain path traversal sequences like `../`
- Output directory not fully validated

**Suggested Fix:**
```python
# utils/path_security.py (NEW FILE)
from pathlib import Path
import re

class PathValidator:
    """Validate file paths for security"""
    
    SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
    
    @staticmethod
    def validate_safe_filename(filename: str) -> bool:
        """Check if filename is safe (no special chars)"""
        return PathValidator.SAFE_FILENAME_PATTERN.match(filename) is not None
    
    @staticmethod
    def resolve_safe_path(base_dir: str, filename: str) -> Path:
        """Resolve a path safely, preventing path traversal"""
        base = Path(base_dir).resolve()
        
        # Validate filename
        if not filename:
            raise ValueError("Filename cannot be empty")
        
        if ".." in filename or filename.startswith("/"):
            raise ValueError(f"Invalid filename (contains path traversal): {filename}")
        
        resolved = (base / filename).resolve()
        
        # Ensure resolved path is within base directory
        try:
            resolved.relative_to(base)
        except ValueError:
            raise ValueError(f"Path {filename} is outside base directory {base}")
        
        return resolved

# recognition/speech_recognition.py, Lines 53-56
from utils.path_security import PathValidator

# Validate language code first
if not re.match(r'^[a-z]{2}(-[a-z]{2})?$', lang_config.source):
    raise ValueError(f"Invalid language code: {lang_config.source}")

# Create safe filename
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
safe_filename = f"recognized_audio_log_{lang_config.source}_{timestamp}.txt"

# Use safe path resolution
self.log_file_path = str(
    PathValidator.resolve_safe_path(self.output_dir, safe_filename)
)
```

---

## 7. DEVELOPER EXPERIENCE

### Issue 7.1: Complex Setup Process

**Files:** README, dependency management
**Severity:** MEDIUM

**Problem:**
No clear setup documentation or automated setup script.

**Suggested Fix:**
```bash
# setup.sh (NEW FILE)
#!/bin/bash
set -e

echo "Audio Recognition System - Setup Script"
echo "========================================"

# Check Python version
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Detected Python: $PYTHON_VERSION"

if [[ ! "$PYTHON_VERSION" =~ ^3\.[8-9] ]] && [[ ! "$PYTHON_VERSION" =~ ^3\.1[0-9] ]]; then
    echo "Error: Python 3.8+ required"
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Download models (optional)
read -p "Download speech recognition model? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 -c "import whisper; whisper.load_model('large-v3-turbo')"
fi

# Test configuration
echo "Creating default configuration..."
if [ ! -f "config.yaml" ]; then
    if [ -f "config.yaml.example" ]; then
        cp config.yaml.example config.yaml
        echo "Created config.yaml from example"
    fi
fi

echo ""
echo "Setup complete!"
echo "To start: python main_with_translation.py --config config.yaml"
```

---

### Issue 7.2: No Debug Mode Documentation

**Severity:** MEDIUM

**Problem:**
Debug mode exists but behavior is not documented.

**Suggested Fix:**
```markdown
# DEBUG MODE GUIDE

## Enabling Debug Mode

```bash
python main_with_translation.py --debug
```

## What Debug Mode Enables

1. **Audio Debugging**
   - Saves recognized audio to `logs/debug_audio/` folder
   - Saves as WAV files with timestamps

2. **Verbose Logging**
   - Shows queue status (full/empty)
   - Prints extracted chunks before recognition
   - Shows translation prompt and raw output

3. **Performance Metrics**
   - VAD (Voice Activity Detection) decisions
   - Processing timings
   - Model loading times

## Example Debug Session

```bash
python main_with_translation.py --debug --config config.yaml 2>&1 | tee debug.log
```

## Performance Analysis with Debug Info

Looking for performance bottlenecks?
- Check "音声処理スレッド開始" to "終了" timing
- Monitor CPU usage with: `top -p $(pgrep -f main_with_translation)`
- Check memory with: `ps aux | grep main_with_translation`
```

---

### Issue 7.3: No Integration Tests

**Severity:** MEDIUM

**Suggested Fix:**
```python
# tests/integration_test.py
"""Integration tests for audio recognition system"""
import pytest
import tempfile
import numpy as np
from pathlib import Path
from config_manager import ConfigManager
from audio.processing import AudioProcessing
from recognition.speech_recognition import SpeechRecognition

class TestIntegration:
    @pytest.fixture
    def temp_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def config_with_temp_dir(self, temp_output_dir):
        """Create config pointing to temp directory"""
        config = ConfigManager()
        config.set_output_dir(temp_output_dir)
        return config
    
    def test_end_to_end_transcription(self, config_with_temp_dir):
        """Test full pipeline from audio to transcription"""
        # Generate test audio
        sample_rate = config_with_temp_dir.audio.sample_rate
        duration = 1  # 1 second
        t = np.linspace(0, duration, int(sample_rate * duration))
        # Generate silence (should be ignored)
        audio = np.zeros_like(t, dtype=np.int16)
        
        # Run through processing
        processor = AudioProcessing(
            config_with_temp_dir.audio,
            audio_queue=...,  # mock
            processing_queue=...  # mock
        )
        
        # Verify output directory was created
        assert Path(config_with_temp_dir.output.directory).exists()
```

---

## SUMMARY TABLE

| Priority | Category | Issue | File | Severity | Impact |
|----------|----------|-------|------|----------|--------|
| 1 | Code Quality | Bare exception handlers | tts/text_to_speech.py | HIGH | Masks errors, debugging impossible |
| 2 | Performance | Inefficient queue handling | translation/translator.py | HIGH | CPU spinning, reduced responsiveness |
| 3 | Performance | Memory leak in model loading | translation/translator.py | HIGH | Memory accumulation over time |
| 4 | Architecture | Tight coupling | main_*.py, *.py | HIGH | Hard to test, extend |
| 5 | Testing | No unit tests | All | CRITICAL | No regression protection |
| 6 | Threading | Race conditions | main files | HIGH | Undefined behavior |
| 7 | Security | trust_remote_code | translation/translator.py | HIGH | Arbitrary code execution risk |
| 8 | Code Quality | Missing type hints | Most files | MEDIUM | Harder maintenance, type errors |
| 9 | Configuration | No validation | config_manager.py | MEDIUM | Invalid configs accepted |
| 10 | Code Quality | Code duplication | main_*.py | MEDIUM | Maintenance burden |

---

## QUICK WINS (Easy, High-Impact)

1. Add type hints to function signatures (30 min)
2. Fix bare exception handlers (15 min)
3. Add input validation to config manager (45 min)
4. Create standardized error handling (30 min)
5. Add async/await for Web UI communication (60 min)
6. Create unit tests for config manager (90 min)

Total estimated effort: 4.5 hours for immediate improvements with high impact.
