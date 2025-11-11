# Audio Recognition System

An audio recognition and real-time translation system built to efficiently transcribe and translate audio input. This repository provides scripts for seamless audio processing with minimal setup, making it ideal for both researchers and developers.

## Table of Contents

- [Audio Recognition System](#audio-recognition-system)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Features](#features)
  - [Installation](#installation)
    - [1. Prerequisites](#1-prerequisites)
    - [2. Clone the Repository](#2-clone-the-repository)
    - [3. Install Dependencies](#3-install-dependencies)
  - [Configuration](#configuration)
    - [config.yaml Structure](#configyaml-structure)
    - [Profiles](#profiles)
  - [Usage](#usage)
    - [Step 1: Configure Your System](#step-1-configure-your-system)
    - [Step 2: Run Audio Recognition](#step-2-run-audio-recognition)
      - [Transcription Only](#transcription-only)
      - [Transcription with Translation](#transcription-with-translation)
    - [Command-Line Options](#command-line-options)
  - [Web UI](#web-ui)
    - [Web UI Installation](#web-ui-installation)
    - [Starting the Web UI Server](#starting-the-web-ui-server)
    - [Web UI Features](#web-ui-features)
    - [Web UI Command-Line Options](#web-ui-command-line-options)
  - [Text-to-Speech (TTS)](#text-to-speech-tts)
    - [TTS Installation](#tts-installation)
    - [TTS Configuration](#tts-configuration)
    - [Available Voices](#available-voices)
    - [Using TTS](#using-tts)
  - [File Structure](#file-structure)
  - [Troubleshooting](#troubleshooting)
    - [Common Issues](#common-issues)
    - [Debug Mode](#debug-mode)
  - [Contributions](#contributions)
    - [Development Setup](#development-setup)
  - [License](#license)
  - [Additional Resources](#additional-resources)

## Overview

The Audio Recognition System enables audio transcription and, optionally, translation of real-time audio data. Built with a modern configuration system using YAML files, this project supports multiple platforms (macOS, Linux, Windows) and offers flexible customization through profiles and command-line options.

## Features

- **Real-time Audio Transcription**: Uses Whisper models for accurate speech recognition
- **Multi-language Translation**: Supports translation between multiple languages using LLM models
- **Web UI**: Modern browser-based interface with real-time display and controls
- **Text-to-Speech**: Optional TTS functionality to read translated text aloud using edge-tts
- **Flexible Configuration**: YAML-based configuration with profile support (development, production, testing)
- **Platform Support**: Optimized for macOS (with MLX), Linux, and Windows
- **Audio Processing**: Built-in noise reduction and voice activity detection
- **Logging**: Automatic logging of transcriptions and translations with timestamps

## Installation

### 1. Prerequisites

   - **macOS**: Install Blackhole for audio routing.
     ```bash
     brew install blackhole-2ch
     ```
   
   - **Python**: Ensure Python 3.8 or later is installed.
   
   - **Virtual Environment** (recommended): To keep dependencies organized.
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate  # On macOS/Linux
     # or
     .venv\Scripts\activate  # On Windows
     ```

### 2. Clone the Repository

   ```bash
   git clone https://github.com/ngc-shj/audio-recognition-system
   cd audio-recognition-system
   ```

### 3. Install Dependencies

   Inside the project directory, run:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The system uses a `config.yaml` file for all settings. A default configuration file is included in the repository.

### config.yaml Structure

```yaml
# Models (ASR and Translation)
models:
  asr:
    darwin:  # macOS
      model_path: "mlx-community/whisper-large-v3-turbo"
      model_size: "large-v3-turbo"
    default:  # Linux/Windows
      model_size: "large-v3-turbo"
  
  translation:
    darwin:  # macOS
      model_path: "mlx-community/gpt-oss-20b-MXFP4-Q4"
    default:  # Linux/Windows
      model_path: "openai/gpt-oss-20b"

    # API Server (LM Studio, Ollama, vLLM, etc.)
    # Use OpenAI-compatible API instead of loading models locally
    api:
      enabled: false
      base_url: "http://localhost:1234/v1"  # LM Studio default
      api_key: ""  # Leave empty if not required
      model: "local-model"  # Model name configured in your API server
      timeout: 60
      max_retries: 3

    # GGUF (llama-cpp-python)
    gguf:
      enabled: false
      model_path: "unsloth/gpt-oss-20b-GGUF"
      model_file: "gpt-oss-20b-Q4_K_M.gguf"
      n_ctx: 4096
      n_gpu_layers: -1
      n_threads: 8

# Audio Settings
audio:
  format: "int16"
  sample_rate: 16000
  channels: 1
  chunk_size: 1024
  buffer_duration: 5.0
  input_device: null  # null = auto-detect

# Language Settings
language:
  source: "en"  # Input language
  target: "ja"  # Output language (for translation)

# Translation Settings
translation:
  enabled: true
  batch_size: 5
  context:
    window_size: 8
    separator: "\n"
  
  generation:
    darwin:
      max_tokens: 4096
      temperature: 0.8
      top_p: 1.0
      repetition_penalty: 1.1
      repetition_context_size: 20

# Output Settings
output:
  directory: "logs"
  logging:
    recognized_audio: true
    translated_text: true
    bilingual_log: true
```

### Translation Modes

The system supports three translation modes:

1. **Local Model Loading** (default): Loads models directly into memory using transformers, MLX, or GGUF
2. **API Server Mode**: Uses OpenAI-compatible API servers (LM Studio, Ollama, vLLM, etc.)
3. **GGUF Mode**: Uses llama-cpp-python for GGUF format models

#### Using API Server Mode (Recommended for LM Studio, Ollama, etc.)

To use an external API server instead of loading models locally:

1. **Start your API server** (e.g., LM Studio):
   - Launch LM Studio
   - Load your preferred translation model
   - Start the local server (default: `http://localhost:1234`)

2. **Enable API mode in config.yaml**:
   ```yaml
   models:
     translation:
       api:
         enabled: true
         base_url: "http://localhost:1234/v1"  # Your API server URL
         api_key: ""  # Leave empty if not required
         model: "local-model"  # Model name from your server
         timeout: 60
         max_retries: 3
   ```

3. **Install the OpenAI client library**:
   ```bash
   pip install openai
   ```

**Benefits of API Mode:**
- No need to load models into memory (saves RAM/VRAM)
- Easy switching between different models
- Can use any OpenAI-compatible API server
- Supports LM Studio, Ollama, vLLM, Text Generation WebUI, and more

### Profiles

The system supports three profiles for different use cases:

- **development**: Faster models, verbose logging, smaller batch sizes
- **production**: Full-size models, optimized performance
- **testing**: Debug mode enabled, saves audio samples

Specify a profile with the `--profile` flag:
```bash
python main_with_translation.py --profile development
```

## Usage

### Step 1: Configure Your System

1. **List Available Audio Devices** (optional, if auto-detection doesn't work):
   ```bash
   python list_audio_devices.py
   ```

2. **Edit config.yaml** if needed:
   - Set `audio.input_device` to your device ID (or leave as `null` for auto-detection)
   - Configure languages in the `language` section
   - Adjust model paths if using local models

### Step 2: Run Audio Recognition

#### Transcription Only

Transcribes live audio and outputs it to the console:
```bash
python main_transcription_only.py
```

With custom settings:
```bash
python main_transcription_only.py \
  --source-lang en \
  --output-dir ./my_logs \
  --model-size base \
  --debug
```

#### Transcription with Translation

Transcribes and translates audio in real-time:
```bash
python main_with_translation.py
```

With custom settings:
```bash
python main_with_translation.py \
  --source-lang en \
  --target-lang ja \
  --batch-size 10 \
  --profile production
```

### Command-Line Options

Both scripts support the following options:

| Option | Description | Default |
|--------|-------------|---------|
| `--config` | Path to config file | `config.yaml` |
| `--profile` | Configuration profile | `production` |
| `--source-lang` | Input language code | From config |
| `--target-lang` | Output language code (translation only) | From config |
| `--output-dir` | Log output directory | From config |
| `--model-size` | Whisper model size | From config |
| `--batch-size` | Translation batch size (translation only) | From config |
| `--debug` | Enable debug mode | `false` |

**Example with all options:**
```bash
python main_with_translation.py \
  --config ./custom_config.yaml \
  --profile development \
  --source-lang en \
  --target-lang ja \
  --output-dir ./logs \
  --model-size base \
  --batch-size 3 \
  --debug
```

**Supported Languages:**
- English: `en`
- Japanese: `ja`
- Chinese: `zh`
- Korean: `ko`
- French: `fr`
- German: `de`
- Spanish: `es`
- And more (see Whisper documentation)

## Web UI

The system includes a modern web-based user interface for real-time audio recognition and translation. The Web UI provides an intuitive interface with visual feedback, paired text display, and easy control over the recognition system.

### Web UI Installation

In addition to the base requirements, the Web UI requires:

```bash
pip install fastapi uvicorn websockets
```

These dependencies allow the system to run a local web server with WebSocket support for real-time updates.

### Starting the Web UI Server

**Basic usage** (server only, start recognition from browser):
```bash
python web_server.py
```

Then open your browser and navigate to: `http://localhost:8000`

**With automatic recognition start:**
```bash
# Transcription with translation mode
python web_server.py --start-recognition --mode translation

# Transcription only mode
python web_server.py --start-recognition --mode transcript
```

**With custom settings:**
```bash
python web_server.py \
  --host 0.0.0.0 \
  --port 8000 \
  --start-recognition \
  --mode translation \
  --source-lang en \
  --target-lang ja \
  --config ./config.yaml
```

### Web UI Features

The Web UI provides:

- **Real-time Display**: Recognized and translated text appears instantly in the browser
- **Paired Text View**: Recognition and translation are paired together with visual indicators
- **Start/Stop Controls**: Easy buttons to control the recognition system
- **Mode Selection**: Choose between translation mode (recognition + translation) or transcript-only mode
- **Language Configuration**: Select source and target languages from the UI
- **Status Indicators**: Visual feedback showing connection status and system state
- **Auto-scrolling**: Automatically scrolls to show the latest results
- **WebSocket Communication**: Efficient real-time updates without page reloads

### Web UI Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--host` | Server host address | `0.0.0.0` |
| `--port` | Server port number | `8000` |
| `--start-recognition` | Start recognition system automatically | `false` |
| `--mode` | Mode: `translation` or `transcript` | `translation` |
| `--config` | Path to config file | `config.yaml` |
| `--source-lang` | Input language code | From config |
| `--target-lang` | Output language code | From config |

**Examples:**

Start server only (control from browser):
```bash
python web_server.py
```

Start with automatic recognition in translation mode:
```bash
python web_server.py --start-recognition --mode translation --source-lang en --target-lang ja
```

Start with automatic recognition in transcript-only mode:
```bash
python web_server.py --start-recognition --mode transcript --source-lang en
```

Run on a different port:
```bash
python web_server.py --host localhost --port 3000
```

**Note**: When using Web UI mode, recognized text and translations are sent only to the browser interface and are not printed to stdout. All results are still logged to files in the output directory.

## Text-to-Speech (TTS)

The system includes optional Text-to-Speech functionality to audibly read translated text in real-time. The TTS feature uses Microsoft Edge Neural TTS (edge-tts) for high-quality, natural-sounding voice output.

### TTS Installation

Install the required TTS dependency:

```bash
pip install edge-tts
```

For audio playback, ensure you have one of the following:
- **macOS**: `afplay` (built-in)
- **Linux/Windows**: `mpv` or `ffmpeg`

### TTS Configuration

Configure TTS in [config.yaml](config.yaml):

```yaml
tts:
  enabled: true  # Enable/disable TTS
  engine: "edge-tts"  # TTS engine (currently only edge-tts is supported)
  voice: "ja-JP-NanamiNeural"  # Voice ID for the target language
  rate: "+30%"  # Speech rate (-50% to +100%)
  volume: "+0%"  # Volume (-50% to +100%)
  pitch: "+0Hz"  # Pitch adjustment (-50Hz to +50Hz)
  output_device: "MacBook Proのスピーカー"  # Output device name (optional)
```

### Available Voices

The system automatically selects appropriate voices based on the target language:

| Language | Voice ID |
|----------|----------|
| Japanese (ja) | ja-JP-NanamiNeural |
| English (en) | en-US-AriaNeural |
| Spanish (es) | es-ES-ElviraNeural |
| French (fr) | fr-FR-DeniseNeural |
| German (de) | de-DE-KatjaNeural |
| Chinese (zh) | zh-CN-XiaoxiaoNeural |
| Korean (ko) | ko-KR-SunHiNeural |
| Italian (it) | it-IT-ElsaNeural |
| Portuguese (pt) | pt-BR-FranciscaNeural |
| Russian (ru) | ru-RU-SvetlanaNeural |

You can override the default voice by specifying a different `voice` in the config file. See the [Microsoft Edge TTS voice list](https://speech.microsoft.com/portal/voicegallery) for all available voices.

### Using TTS

TTS works automatically when enabled in the configuration:

1. **With Translation Mode**: Translated text will be read aloud automatically
   ```bash
   python main_with_translation.py --source-lang en --target-lang ja
   ```

2. **Enable/Disable via Config**: Edit `config.yaml` and set `tts.enabled` to `true` or `false`

3. **Web UI Integration**: The Web UI includes a "Enable Text-to-Speech" checkbox in the settings panel

**Note**: TTS only works in translation mode and reads the translated text, not the original recognized text.

## File Structure

```
audio-recognition-system/
├── config.yaml                      # Main configuration file
├── config_manager.py                # Configuration management
├── main_transcription_only.py       # Transcription-only script
├── main_with_translation.py         # Transcription + translation script
├── web_server.py                    # Web UI server (FastAPI + WebSocket)
├── web_ui_bridge.py                 # Bridge for sending updates to Web UI
├── list_audio_devices.py            # Device listing utility
│
├── web/                             # Web UI files
│   ├── index.html                   # Main Web UI page
│   ├── app.js                       # Client-side JavaScript
│   └── styles.css                   # UI styles
│
├── audio/
│   ├── capture.py                   # Audio capture module
│   └── processing.py                # Audio processing (noise reduction, etc.)
│
├── recognition/
│   └── speech_recognition.py        # Speech recognition (Whisper)
│
├── translation/
│   └── translator.py                # Translation module (LLM-based)
│
├── tts/                             # Text-to-Speech module
│   └── text_to_speech.py            # TTS using edge-tts (Microsoft Edge Neural TTS)
│
├── utils/
│   ├── resource_manager.py          # System resource management
│   └── argument_config.py           # Command-line argument parsing
│
└── logs/                            # Output directory (auto-created)
    ├── recognized_audio_log_*.txt
    ├── translated_text_log_*.txt
    └── bilingual_translation_log_*.txt
```

## Troubleshooting

### Common Issues

1. **Audio device not found**
   - Run `python list_audio_devices.py` to see available devices
   - Set `audio.input_device` in `config.yaml` to the correct device ID
   - For macOS: Ensure Blackhole is installed and configured

2. **Model download errors**
   - Check your internet connection
   - Models are downloaded automatically on first run
   - For offline use, download models manually and update paths in `config.yaml`

3. **Translation errors: `generate_step() got an unexpected keyword argument`**
   - Ensure you're using the latest version of `translator.py` (see FIXES_SUMMARY.md)
   - This was fixed to properly handle MLX generation parameters

4. **High CPU/Memory usage**
   - Use the `development` profile for lighter models
   - Reduce `translation.batch_size` in config.yaml
   - Adjust `resources.threads.max` for your system

5. **Config file not found**
   - Ensure `config.yaml` is in the same directory as the scripts
   - Use `--config` flag to specify a custom path

### Debug Mode

Enable debug mode for detailed logging:
```bash
python main_with_translation.py --debug
```

Or set in config.yaml:
```yaml
debug:
  enabled: true
  save_audio_samples: true
  verbose_logging: true
```

## Contributions

Contributions to enhance this project are welcome! Please:

1. Fork the repository
2. Create a new branch for your feature: `git checkout -b feature/my-feature`
3. Make your changes and commit: `git commit -am 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Submit a pull request with a clear description of your additions

### Development Setup

```bash
# Clone and setup
git clone https://github.com/ngc-shj/audio-recognition-system
cd audio-recognition-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Use development profile
python main_with_translation.py --profile development --debug
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

## Additional Resources

- [Whisper Documentation](https://github.com/openai/whisper)
- [MLX Framework (macOS)](https://github.com/ml-explore/mlx)
- [Blackhole Audio Driver](https://github.com/ExistentialAudio/BlackHole)
