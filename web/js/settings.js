/**
 * Advanced Settings Management
 *
 * Handles loading, saving, and managing advanced configuration settings.
 */

import { serverConfig, setServerConfig, setIsRunning, DOM, textPairs } from './state.js';
import { updateStatus, updateUIForMode, showToast } from './ui.js';
import { loadAudioDevices } from './audio-devices.js';
import { updatePairDisplay } from './text-display.js';

/**
 * Load server configuration
 */
export async function loadServerConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const config = await response.json();
            console.log('Server config loaded:', config);
            setServerConfig(config);

            // Reflect in UI
            if (DOM.modeSelect && config.mode) {
                DOM.modeSelect.value = config.mode;
            }
            if (DOM.sourceLang && config.source_lang) {
                DOM.sourceLang.value = config.source_lang;
                DOM.headerSourceLang.value = config.source_lang;
            }
            if (DOM.targetLang && config.target_lang) {
                DOM.targetLang.value = config.target_lang;
                DOM.headerTargetLang.value = config.target_lang;
            }

            // Update UI based on mode
            updateUIForMode(config.mode);
        }
    } catch (error) {
        console.error('Failed to load server config:', error);
    }
}

/**
 * Check recognition status
 */
export async function checkRecognitionStatus() {
    try {
        const response = await fetch('/api/status');
        if (response.ok) {
            const status = await response.json();
            if (status.recognition_active) {
                // Recognition running
                setIsRunning(true);
                updateStatus('running', 'Recognition Running');
                DOM.startBtn.disabled = true;
                DOM.stopBtn.disabled = false;
            } else {
                // Recognition stopped
                setIsRunning(false);
                updateStatus('connected', 'Connected');
                DOM.startBtn.disabled = false;
                DOM.stopBtn.disabled = true;
            }
        }
    } catch (error) {
        console.error('Failed to check recognition status:', error);
        // On error, set to disconnected state
        updateStatus('disconnected', 'Disconnected');
        DOM.startBtn.disabled = true;
        DOM.stopBtn.disabled = true;
    }
}

/**
 * Load full configuration from server
 */
export async function loadFullConfig() {
    try {
        const response = await fetch('/api/config/full');
        if (response.ok) {
            const data = await response.json();
            if (data.status === 'success') {
                populateAdvancedSettings(data.config);
            }
        }
    } catch (error) {
        console.error('Failed to load full config:', error);
    }
}

/**
 * Populate advanced settings UI with config values
 */
function populateAdvancedSettings(config) {
    // TTS Settings
    if (config.tts) {
        document.getElementById('ttsRate').value = config.tts.rate || '+30%';
        document.getElementById('ttsVolume').value = config.tts.volume || '+0%';
        document.getElementById('ttsPitch').value = config.tts.pitch || '+0Hz';
    }

    // Model Settings
    if (config.models) {
        // ASR Model
        if (config.models.asr && config.models.asr.darwin) {
            document.getElementById('asrModelPath').value = config.models.asr.darwin.model_path || 'mlx-community/whisper-large-v3-turbo';
            document.getElementById('asrModelSize').value = config.models.asr.darwin.model_size || 'large-v3-turbo';
        }

        // Translation Model
        if (config.models.translation && config.models.translation.darwin) {
            document.getElementById('translationModelPath').value = config.models.translation.darwin.model_path || 'mlx-community/gpt-oss-20b-MXFP4-Q4';
        }
    }

    // API Settings
    if (config.models && config.models.translation && config.models.translation.api) {
        const apiConfig = config.models.translation.api;
        document.getElementById('apiEnabled').checked = apiConfig.enabled || false;
        document.getElementById('apiBaseUrl').value = apiConfig.base_url || 'http://localhost:1234/v1';
        document.getElementById('apiModel').value = apiConfig.model || 'local-model';

        // Toggle between local model and API server settings
        const apiServerSettings = document.getElementById('apiServerSettings');
        const localModelSettings = document.getElementById('localModelSettings');

        if (apiConfig.enabled) {
            apiServerSettings.classList.remove('hidden');
            localModelSettings.classList.add('hidden');
        } else {
            apiServerSettings.classList.add('hidden');
            localModelSettings.classList.remove('hidden');
        }
    }

    // Audio Detection Settings
    if (config.audio && config.audio.voice_detection) {
        const silenceThreshold = config.audio.voice_detection.silence_threshold || 0.005;
        document.getElementById('silenceThreshold').value = silenceThreshold;
        document.getElementById('silenceThresholdValue').textContent = silenceThreshold;
    }

    if (config.audio && config.audio.dynamic_buffer) {
        const mediumPause = config.audio.dynamic_buffer.medium_pause || 0.8;
        const longPause = config.audio.dynamic_buffer.long_pause || 1.5;

        document.getElementById('mediumPause').value = mediumPause;
        document.getElementById('mediumPauseValue').textContent = `${mediumPause}s`;

        document.getElementById('longPause').value = longPause;
        document.getElementById('longPauseValue').textContent = `${longPause}s`;
    }

    // Translation Parameters
    if (config.translation && config.translation.generation) {
        const genConfig = config.translation.generation.darwin || config.translation.generation.default || {};
        const temperature = genConfig.temperature || 0.8;
        document.getElementById('temperature').value = temperature;
        document.getElementById('temperatureValue').textContent = temperature;
    }

    if (config.translation && config.translation.context) {
        const windowSize = config.translation.context.window_size || 8;
        document.getElementById('contextWindowSize').value = windowSize;
        document.getElementById('contextWindowSizeValue').textContent = `${windowSize} sentences`;
    }

    // Display Options
    if (config.output) {
        const showTimestampElem = document.getElementById('showTimestamp');
        const showLanguageElem = document.getElementById('showLanguage');

        if (showTimestampElem) {
            showTimestampElem.checked = config.output.show_timestamp ?? true;
        }
        if (showLanguageElem) {
            showLanguageElem.checked = config.output.show_language ?? true;
        }
    }
}

/**
 * Setup platform-dependent UI (ASR model fields)
 */
function setupPlatformDependentUI() {
    // Detect macOS using userAgent
    const isMac = navigator.userAgent.toUpperCase().indexOf('MAC') >= 0;

    const asrModelPathGroup = document.getElementById('asrModelPathGroup');
    const asrModelSizeGroup = document.getElementById('asrModelSizeGroup');

    if (isMac) {
        // Show Path field for macOS (MLX format)
        if (asrModelPathGroup) asrModelPathGroup.style.display = 'block';
        if (asrModelSizeGroup) asrModelSizeGroup.style.display = 'none';
    } else {
        // Show Size field for Linux/Windows (auto-download)
        if (asrModelPathGroup) asrModelPathGroup.style.display = 'none';
        if (asrModelSizeGroup) asrModelSizeGroup.style.display = 'block';
    }
}

/**
 * Setup mode-dependent UI (Translation vs Transcript)
 */
export function setupModeDependentUI() {
    const modeElement = document.getElementById('mode');
    if (!modeElement) return;

    const mode = modeElement.value;
    const translationSettingsSection = document.getElementById('translationSettingsSection');

    if (mode === 'translation') {
        // Translation mode: Show translation settings section
        if (translationSettingsSection) translationSettingsSection.style.display = 'block';
    } else {
        // Transcript mode: Hide translation settings section
        if (translationSettingsSection) translationSettingsSection.style.display = 'none';
    }
}

/**
 * Setup advanced settings event listeners
 */
export function setupAdvancedSettings() {
    // Setup platform-dependent UI first
    setupPlatformDependentUI();

    // Setup mode-dependent UI
    setupModeDependentUI();

    // API enabled checkbox toggle (exclusive with local model)
    const apiEnabledCheckbox = document.getElementById('apiEnabled');
    if (apiEnabledCheckbox) {
        apiEnabledCheckbox.addEventListener('change', (e) => {
            const apiServerSettings = document.getElementById('apiServerSettings');
            const localModelSettings = document.getElementById('localModelSettings');

            if (e.target.checked) {
                // Show API settings, hide local model settings
                apiServerSettings.classList.remove('hidden');
                localModelSettings.classList.add('hidden');
            } else {
                // Show local model settings, hide API settings
                apiServerSettings.classList.add('hidden');
                localModelSettings.classList.remove('hidden');
            }
        });
    }

    // Range input value display updates
    const silenceThresholdInput = document.getElementById('silenceThreshold');
    if (silenceThresholdInput) {
        silenceThresholdInput.addEventListener('input', (e) => {
            document.getElementById('silenceThresholdValue').textContent = e.target.value;
        });
    }

    const mediumPauseInput = document.getElementById('mediumPause');
    if (mediumPauseInput) {
        mediumPauseInput.addEventListener('input', (e) => {
            document.getElementById('mediumPauseValue').textContent = `${e.target.value}s`;
        });
    }

    const longPauseInput = document.getElementById('longPause');
    if (longPauseInput) {
        longPauseInput.addEventListener('input', (e) => {
            document.getElementById('longPauseValue').textContent = `${e.target.value}s`;
        });
    }

    const temperatureInput = document.getElementById('temperature');
    if (temperatureInput) {
        temperatureInput.addEventListener('input', (e) => {
            document.getElementById('temperatureValue').textContent = e.target.value;
        });
    }

    const contextWindowSizeInput = document.getElementById('contextWindowSize');
    if (contextWindowSizeInput) {
        contextWindowSizeInput.addEventListener('input', (e) => {
            document.getElementById('contextWindowSizeValue').textContent = `${e.target.value} sentences`;
        });
    }

    // Display Options - update display immediately when changed
    const showTimestampCheckbox = document.getElementById('showTimestamp');
    const showLanguageCheckbox = document.getElementById('showLanguage');

    console.log('Display Options setup:');
    console.log('- showTimestamp element:', showTimestampCheckbox);
    console.log('- showLanguage element:', showLanguageCheckbox);

    if (showTimestampCheckbox) {
        console.log('Setting up showTimestamp event listener');
        showTimestampCheckbox.addEventListener('change', () => {
            console.log('showTimestamp changed, re-rendering pairs...');
            // Re-render all existing text pairs
            textPairs.forEach(pair => {
                updatePairDisplay(pair);
            });
        });
    } else {
        console.warn('showTimestamp checkbox not found!');
    }

    if (showLanguageCheckbox) {
        console.log('Setting up showLanguage event listener');
        showLanguageCheckbox.addEventListener('change', (e) => {
            console.log('showLanguage changed:', e.target.checked);
            console.log('textPairs size:', textPairs.size);
            // Re-render all existing text pairs
            textPairs.forEach((pair, pairId) => {
                console.log('Updating pair:', pairId);
                updatePairDisplay(pair);
            });
            console.log('Done updating all pairs');
        });
    } else {
        console.warn('showLanguage checkbox not found!');
    }

    // Refresh devices button
    const refreshInputDevicesBtn = document.getElementById('refreshInputDevices');
    if (refreshInputDevicesBtn) {
        refreshInputDevicesBtn.addEventListener('click', async () => {
            await loadAudioDevices();
            showToast('🔄 Audio devices refreshed', 'info', 2000);
        });
    }

    // Save Advanced Settings button
    const saveAdvancedSettingsBtn = document.getElementById('saveAdvancedSettings');
    if (saveAdvancedSettingsBtn) {
        saveAdvancedSettingsBtn.addEventListener('click', async () => {
            await saveAdvancedSettings();
        });
    }
}

/**
 * Save advanced settings to server
 */
async function saveAdvancedSettings() {
    // Detect platform to save only the appropriate ASR model field
    const isMac = navigator.userAgent.toUpperCase().indexOf('MAC') >= 0;

    const updates = {
        // TTS Settings
        'tts.rate': document.getElementById('ttsRate').value,
        'tts.volume': document.getElementById('ttsVolume').value,
        'tts.pitch': document.getElementById('ttsPitch').value,

        // Model Settings - only save the visible ASR field based on platform
        'models.translation.darwin.model_path': document.getElementById('translationModelPath').value,

        // API Settings
        'models.translation.api.enabled': document.getElementById('apiEnabled').checked,
        'models.translation.api.base_url': document.getElementById('apiBaseUrl').value,
        'models.translation.api.model': document.getElementById('apiModel').value,

        // Audio Device Settings
        'audio.input_device': document.getElementById('inputDevice').value || null,
        'tts.output_device': document.getElementById('outputDevice').value || null,

        // Audio Detection
        'audio.voice_detection.silence_threshold': parseFloat(document.getElementById('silenceThreshold').value),
        'audio.dynamic_buffer.medium_pause': parseFloat(document.getElementById('mediumPause').value),
        'audio.dynamic_buffer.long_pause': parseFloat(document.getElementById('longPause').value),

        // Translation Parameters
        'translation.generation.darwin.temperature': parseFloat(document.getElementById('temperature').value),
        'translation.generation.default.temperature': parseFloat(document.getElementById('temperature').value),
        'translation.context.window_size': parseInt(document.getElementById('contextWindowSize').value),

        // Display Options (no restart required)
        'output.show_timestamp': document.getElementById('showTimestamp')?.checked ?? true,
        'output.show_language': document.getElementById('showLanguage')?.checked ?? true
    };

    // Add platform-specific ASR model field
    if (isMac) {
        updates['models.asr.darwin.model_path'] = document.getElementById('asrModelPath').value;
    } else {
        updates['models.asr.darwin.model_size'] = document.getElementById('asrModelSize').value;
    }

    // Determine if any settings that require restart were changed
    const restartRequiredKeys = [
        'tts.rate', 'tts.volume', 'tts.pitch',
        'models.translation.darwin.model_path',
        'models.asr.darwin.model_path', 'models.asr.darwin.model_size',
        'models.translation.api.enabled', 'models.translation.api.base_url', 'models.translation.api.model',
        'audio.input_device', 'tts.output_device',
        'audio.voice_detection.silence_threshold',
        'audio.dynamic_buffer.medium_pause', 'audio.dynamic_buffer.long_pause',
        'translation.generation.darwin.temperature', 'translation.generation.default.temperature',
        'translation.context.window_size'
    ];

    const changedRestartRequired = Object.keys(updates).some(key => restartRequiredKeys.includes(key));

    try {
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ updates })
        });

        if (response.ok) {
            await response.json();  // Parse response but result not needed

            // Show appropriate message based on what was changed
            if (changedRestartRequired) {
                showToast('✅ Settings saved successfully! Restart recognition for changes to take effect.', 'info', 5000);
            } else {
                showToast('✅ Display settings saved!', 'info', 2000);
            }

            // Reload full config to reflect changes
            await loadFullConfig();
        } else {
            const error = await response.json();
            showToast(`❌ Failed to save settings: ${error.detail}`, 'warning', 5000);
        }
    } catch (error) {
        console.error('Error saving advanced settings:', error);
        showToast('❌ Error saving settings. Please try again.', 'warning', 5000);
    }
}
