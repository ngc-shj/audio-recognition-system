/**
 * Audio Devices Management
 *
 * Handles loading and managing audio input/output devices.
 */

import { showToast } from './ui.js';

/**
 * Load audio devices and populate dropdowns
 */
export async function loadAudioDevices() {
    try {
        const response = await fetch('/api/audio/devices');
        if (response.ok) {
            const data = await response.json();

            if (data.status === 'unavailable') {
                console.warn('PyAudio not available:', data.message);
                return;
            }

            // Get current config for selected devices
            const configResponse = await fetch('/api/config/full');
            let currentInputDevice = null;
            let currentOutputDevice = null;

            if (configResponse.ok) {
                const configData = await configResponse.json();
                if (configData.status === 'success') {
                    currentInputDevice = configData.config.audio?.input_device;
                    currentOutputDevice = configData.config.tts?.output_device;
                }
            }

            // Populate input devices
            const inputSelect = document.getElementById('inputDevice');
            inputSelect.innerHTML = '<option value="">Default (Auto-detect)</option>';

            data.input_devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.name;
                option.textContent = `${device.name} (${device.channels}ch, ${device.sample_rate}Hz)`;
                if (device.name === currentInputDevice) {
                    option.selected = true;
                }
                inputSelect.appendChild(option);
            });

            // Populate output devices
            const outputSelect = document.getElementById('outputDevice');
            outputSelect.innerHTML = '<option value="">Default (System Speaker)</option>';

            data.output_devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.name;
                option.textContent = `${device.name} (${device.channels}ch, ${device.sample_rate}Hz)`;
                if (device.name === currentOutputDevice) {
                    option.selected = true;
                }
                outputSelect.appendChild(option);
            });

            // Setup feedback loop prevention
            setupDeviceSelectionValidation();
        }
    } catch (error) {
        console.error('Failed to load audio devices:', error);
    }
}

/**
 * Device selection validation (prevent feedback loop)
 */
function setupDeviceSelectionValidation() {
    const inputSelect = document.getElementById('inputDevice');
    const outputSelect = document.getElementById('outputDevice');

    if (!inputSelect || !outputSelect) return;

    // Input device change
    inputSelect.addEventListener('change', () => {
        const inputDevice = inputSelect.value;
        const outputDevice = outputSelect.value;

        // If both are selected and same device
        if (inputDevice && outputDevice && inputDevice === outputDevice) {
            showToast('⚠️ Warning: Input and Output devices are the same. This may cause audio feedback loop!', 'warning', 5000);

            // Automatically reset output device to Default
            outputSelect.value = '';
            showToast('Output device reset to Default to prevent feedback loop.', 'info', 3000);
        }
    });

    // Output device change
    outputSelect.addEventListener('change', () => {
        const inputDevice = inputSelect.value;
        const outputDevice = outputSelect.value;

        // If both are selected and same device
        if (inputDevice && outputDevice && inputDevice === outputDevice) {
            showToast('⚠️ Warning: Input and Output devices are the same. This may cause audio feedback loop!', 'warning', 5000);

            // Automatically reset input device to Default
            inputSelect.value = '';
            showToast('Input device reset to Default to prevent feedback loop.', 'info', 3000);
        }
    });
}
