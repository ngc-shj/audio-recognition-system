# Audio Recognition System

An audio recognition and real-time translation system built to efficiently transcribe and translate audio input. This repository provides scripts for seamless audio processing with minimal setup, making it ideal for both researchers and developers.

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
- [File Descriptions](#file-descriptions)
- [Troubleshooting](#troubleshooting)
- [Contributions](#contributions)
- [License](#license)

## Overview

The Audio Recognition System enables audio transcription and, optionally, translation of real-time audio data. Built for simplicity, this project can be quickly set up on macOS with Blackhole for audio routing, and supports extensions for other operating systems with equivalent software.

## Installation

### 1. Prerequisites
   - **macOS**: Install Blackhole for audio routing.
     ```bash
     brew install blackhole-2ch
     ```
   - **Python**: Ensure Python 3.7 or later is installed.
   - **Virtual Environment** (recommended): To keep dependencies organized.

### 2. Clone the Repository
   ```bash
   git clone https://github.com/ngc-shj/audio-recognition-system
   cd audio-recognition-system
   ```

### 3. Install Dependencies
   - Inside the project directory, run:
     ```bash
     pip install -r requirements.txt
     ```

## Usage

This repository offers two main scripts depending on your needs:

1. **For Transcription Only**  
   Transcribes live audio and outputs it to the console.
   ```bash
   python main_transcription_only.py
   ```

2. **For Transcription and Translation**  
   Transcribes and translates audio in real-time, displaying both the original and translated text.
   ```bash
   python main_with_translation.py
   ```

## File Descriptions

- **`main_transcription_only.py`**: Handles real-time audio transcription.
- **`main_with_translation.py`**: Manages both transcription and translation of live audio.
- **`requirements.txt`**: Lists all necessary Python packages.

## Troubleshooting

If you encounter issues:
1. Verify that Blackhole is correctly installed and configured.
2. Ensure that your Python version is compatible.
3. Check the `Issues` tab for similar problems or report a new one with details.

## Contributions

Contributions to enhance this project are welcome! Please:
1. Fork the repository.
2. Create a new branch for your feature.
3. Submit a pull request with a clear description of your additions.

## License

This project is licensed under the Apache License 2.0 - see the `LICENSE` file for details.
