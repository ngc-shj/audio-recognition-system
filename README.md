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
  - [File Structure](#file-structure)
  - [Troubleshooting](#troubleshooting)
  - [Contributions](#contributions)
  - [License](#license)

## Overview

The Audio Recognition System enables audio transcription and, optionally, translation of real-time audio data. Built with a modern configuration system using YAML files, this project supports multiple platforms (macOS, Linux, Windows) and offers flexible customization through profiles and command-line options.

## Features

- **Real-time Audio Transcription**: Uses Whisper models for accurate speech recognition
- **Multi-language Translation**: Supports translation between multiple languages using LLM models
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
    darwin:
      model_path: "mlx-community/llm-jp-3-3.7b-instruct"
    default:
      model_path: "llm-jp/llm-jp-3-3.7b-instruct"

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
      max_tokens: 256
      temperature: 0.8
      top_p: 0.95
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

## File Structure

```
audio-recognition-system/
├── config.yaml                      # Main configuration file
├── config_manager.py                # Configuration management
├── main_transcription_only.py       # Transcription-only script
├── main_with_translation.py         # Transcription + translation script
├── list_audio_devices.py            # Device listing utility
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

## Changelog

### v2.0.0 (Current)
- ✨ Added YAML-based configuration system
- ✨ Added profile support (development, production, testing)
- ✨ Platform-specific optimizations (MLX for macOS)
- 🐛 Fixed MLX translation parameter handling
- 📝 Comprehensive configuration documentation
- 🎨 Cleaner architecture with data classes

### v1.0.0
- Initial release with basic transcription and translation
