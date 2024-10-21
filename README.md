# Audio Recognition System

An audio recognition and real-time translation system built to efficiently transcribe and translate audio input. This repository provides scripts for seamless audio processing with minimal setup, making it ideal for both researchers and developers.

## Table of Contents

- [Audio Recognition System](#audio-recognition-system)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Installation](#installation)
    - [1. Prerequisites](#1-prerequisites)
    - [2. Clone the Repository](#2-clone-the-repository)
    - [3. Install Dependencies](#3-install-dependencies)
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

### Step 1: List Available Audio Devices

Before starting audio recognition, list the available audio devices and select the one you want to use:

```bash
python list_audio_devices.py
```

This command will output a list of audio devices with their respective IDs. Note down the device ID that you want to use for audio recognition.

### Step 2: Run the Audio Recognition Script

Depending on your needs, you can run the following scripts:

1. **For Transcription Only**  
   Transcribes live audio and outputs it to the console.
   ```bash
   python main_transcription_only.py --input-device <device_number>
   ```

2. **For Transcription and Translation**  
   Transcribes and translates audio in real-time, displaying both the original and translated text.
   ```bash
   python main_with_translation.py --input-device <device_number>
   ```

Again, replace `<device_number>` with the appropriate ID.

## File Descriptions

- **`list_audio_devices.py`**: Lists available audio devices along with their device IDs.
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

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

