/**
 * UI Operations and Event Handlers
 *
 * Manages user interface interactions, buttons, settings panel, and toast notifications.
 */

import { ws, isConnected, isRunning, serverConfig, toastTimeout, setServerConfig, setToastTimeout, textPairs, DOM } from './state.js';
import { updatePairDisplay, clearTextPairs } from './text-display.js';
import { setupModeDependentUI } from './settings.js';

/**
 * Show toast notification
 */
export function showToast(message, type = 'info', duration = 4000) {
    // Clear any existing timeout
    if (toastTimeout) {
        clearTimeout(toastTimeout);
    }

    // Set message and type
    DOM.toast.textContent = message;
    DOM.toast.className = `toast ${type}`;

    // Show toast
    setTimeout(() => {
        DOM.toast.classList.add('show');
    }, 10);

    // Hide after duration
    const timeout = setTimeout(() => {
        DOM.toast.classList.remove('show');
    }, duration);
    setToastTimeout(timeout);
}

/**
 * Update status indicator
 */
export function updateStatus(status, text) {
    DOM.statusDot.className = `status-dot ${status}`;
    DOM.statusText.textContent = text;
}

/**
 * Open settings panel
 */
function openSettings() {
    DOM.settingsPanel.classList.add('open');
    DOM.overlay.classList.add('active');
}

/**
 * Close settings panel
 */
function closeSettings() {
    DOM.settingsPanel.classList.remove('open');
    DOM.overlay.classList.remove('active');
}

/**
 * Update UI based on mode (Translation vs Transcript)
 */
export function updateUIForMode(mode) {
    const outputControls = document.getElementById('outputControls');

    if (mode === 'transcript') {
        // Transcript mode: Hide translation settings and output controls
        DOM.translationSettings.classList.add('hidden');
        if (outputControls) {
            outputControls.style.display = 'none';
        }
    } else {
        // Translation mode: Show translation settings and output controls
        DOM.translationSettings.classList.remove('hidden');
        if (outputControls) {
            outputControls.style.display = 'flex';
        }
    }

    // Update advanced settings UI based on mode
    if (typeof setupModeDependentUI === 'function') {
        setupModeDependentUI();
    }

    // Redraw existing pairs (display changes based on mode)
    textPairs.forEach(pair => {
        updatePairDisplay(pair);
    });
}

/**
 * Send settings to server
 */
function sendSettingsToServer(settings) {
    if (isConnected && ws) {
        ws.send(JSON.stringify({
            type: 'settings',
            settings: settings
        }));
    }
}

/**
 * Setup all UI event listeners
 */
export function setupUIEventListeners() {
    // Settings panel open/close
    DOM.settingsBtn.addEventListener('click', openSettings);
    DOM.closeSettingsBtn.addEventListener('click', closeSettings);
    DOM.overlay.addEventListener('click', closeSettings);

    // Language swap button
    DOM.langSwapBtn.addEventListener('click', () => {
        // Swap languages
        const tempSource = DOM.headerSourceLang.value;
        DOM.headerSourceLang.value = DOM.headerTargetLang.value;
        DOM.headerTargetLang.value = tempSource;

        // Sync settings panel languages
        DOM.sourceLang.value = DOM.headerSourceLang.value;
        DOM.targetLang.value = DOM.headerTargetLang.value;

        // Notify server if running
        if (isConnected && ws && isRunning) {
            sendSettingsToServer({
                source_lang: DOM.headerSourceLang.value,
                target_lang: DOM.headerTargetLang.value,
                tts_enabled: DOM.ttsEnabled.checked
            });

            showToast('Language settings changed. Please stop and restart recognition to apply changes.', 'warning', 5000);
        } else {
            showToast(`Languages swapped: ${DOM.headerSourceLang.value.toUpperCase()} → ${DOM.headerTargetLang.value.toUpperCase()}`, 'info', 3000);
        }

        // Update server config
        setServerConfig({
            source_lang: DOM.headerSourceLang.value,
            target_lang: DOM.headerTargetLang.value
        });
    });

    // Start button
    DOM.startBtn.addEventListener('click', () => {
        if (!isConnected || !ws) return;

        const settings = {
            mode: DOM.modeSelect.value,
            source_lang: DOM.sourceLang.value,
            target_lang: DOM.targetLang.value,
            tts_enabled: DOM.ttsEnabled.checked
        };

        ws.send(JSON.stringify({
            type: 'start',
            settings: settings
        }));

        // Update UI state immediately
        DOM.startBtn.disabled = true;
        updateStatus('connecting', 'Starting recognition...');
    });

    // Stop button
    DOM.stopBtn.addEventListener('click', () => {
        if (!isConnected || !ws) return;

        ws.send(JSON.stringify({
            type: 'stop'
        }));

        // Update UI state immediately
        DOM.stopBtn.disabled = true;
        updateStatus('connecting', 'Stopping recognition...');
    });

    // Clear button
    DOM.clearBtn.addEventListener('click', () => {
        clearTextPairs();
    });

    // Mode selection change
    DOM.modeSelect.addEventListener('change', () => {
        const mode = DOM.modeSelect.value;
        console.log('Mode changed to:', mode);
        updateUIForMode(mode);

        // Update server config
        setServerConfig({ mode });
    });

    // Source language change
    DOM.sourceLang.addEventListener('change', () => {
        // Sync header language selection
        DOM.headerSourceLang.value = DOM.sourceLang.value;

        if (!isConnected || !ws || !isRunning) return;

        sendSettingsToServer({
            source_lang: DOM.sourceLang.value,
            target_lang: DOM.targetLang.value,
            tts_enabled: DOM.ttsEnabled.checked
        });
    });

    // Target language change
    DOM.targetLang.addEventListener('change', () => {
        // Sync header language selection
        DOM.headerTargetLang.value = DOM.targetLang.value;

        if (!isConnected || !ws || !isRunning) return;

        sendSettingsToServer({
            source_lang: DOM.sourceLang.value,
            target_lang: DOM.targetLang.value,
            tts_enabled: DOM.ttsEnabled.checked
        });
    });

    // TTS enabled change
    DOM.ttsEnabled.addEventListener('change', () => {
        if (!isConnected || !ws || !isRunning) return;

        sendSettingsToServer({
            source_lang: DOM.sourceLang.value,
            target_lang: DOM.targetLang.value,
            tts_enabled: DOM.ttsEnabled.checked
        });
    });

    // Header source language change
    DOM.headerSourceLang.addEventListener('change', () => {
        const newLang = DOM.headerSourceLang.value;
        console.log('Header source language changed to:', newLang);

        // Sync settings panel language
        DOM.sourceLang.value = newLang;

        // Notify server if running
        if (isConnected && ws && isRunning) {
            sendSettingsToServer({
                source_lang: newLang,
                target_lang: DOM.targetLang.value,
                tts_enabled: DOM.ttsEnabled.checked
            });
            showToast('Source language changed. Please stop and restart recognition to apply.', 'warning', 5000);
        } else {
            showToast(`Source language set to ${newLang.toUpperCase()}`, 'info', 2000);
        }

        // Update server config
        setServerConfig({ source_lang: newLang });
    });

    // Header target language change
    DOM.headerTargetLang.addEventListener('change', () => {
        const newLang = DOM.headerTargetLang.value;
        console.log('Header target language changed to:', newLang);

        // Sync settings panel language
        DOM.targetLang.value = newLang;

        // Notify server if running
        if (isConnected && ws && isRunning) {
            sendSettingsToServer({
                source_lang: DOM.sourceLang.value,
                target_lang: newLang,
                tts_enabled: DOM.ttsEnabled.checked
            });
            showToast('Target language changed. Please stop and restart recognition to apply.', 'warning', 5000);
        } else {
            showToast(`Target language set to ${newLang.toUpperCase()}`, 'info', 2000);
        }

        // Update server config
        setServerConfig({ target_lang: newLang });
    });

    // Header mode toggle buttons
    const transcriptModeBtn = document.getElementById('transcriptModeBtn');
    const translationModeBtn = document.getElementById('translationModeBtn');
    const modeField = document.getElementById('mode');
    const transcriptLangSelector = document.getElementById('transcriptLangSelector');
    const translationLangSelector = document.getElementById('translationLangSelector');
    const headerTranscriptLang = document.getElementById('headerTranscriptLang');

    if (transcriptModeBtn && translationModeBtn) {
        transcriptModeBtn.addEventListener('click', async () => {
            // Already in transcript mode
            if (modeField.value === 'transcript') return;

            // Switch to transcript mode
            modeField.value = 'transcript';
            transcriptModeBtn.classList.add('active');
            translationModeBtn.classList.remove('active');

            // Show/hide language selectors
            transcriptLangSelector.style.display = 'flex';
            translationLangSelector.style.display = 'none';

            // Sync transcript language with source language
            headerTranscriptLang.value = DOM.headerSourceLang.value;

            // Update UI
            updateUIForMode('transcript');
            setServerConfig({ mode: 'transcript' });

            // Notify server
            try {
                const response = await fetch('/api/config/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ updates: { 'mode': 'transcript' } })
                });

                if (response.ok) {
                    showToast('🎤 Switched to Transcript mode', 'info', 2000);
                } else {
                    showToast('⚠️ Mode changed locally. Restart recognition to apply.', 'warning', 3000);
                }
            } catch (error) {
                console.error('Failed to update mode:', error);
            }
        });

        translationModeBtn.addEventListener('click', async () => {
            // Already in translation mode
            if (modeField.value === 'translation') return;

            // Switch to translation mode
            modeField.value = 'translation';
            translationModeBtn.classList.add('active');
            transcriptModeBtn.classList.remove('active');

            // Show/hide language selectors
            transcriptLangSelector.style.display = 'none';
            translationLangSelector.style.display = 'flex';

            // Sync source language with transcript language
            DOM.headerSourceLang.value = headerTranscriptLang.value;
            DOM.sourceLang.value = headerTranscriptLang.value;

            // Update UI
            updateUIForMode('translation');
            setServerConfig({ mode: 'translation' });

            // Notify server
            try {
                const response = await fetch('/api/config/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ updates: { 'mode': 'translation' } })
                });

                if (response.ok) {
                    showToast('🌐 Switched to Translation mode', 'info', 2000);
                } else {
                    showToast('⚠️ Mode changed locally. Restart recognition to apply.', 'warning', 3000);
                }
            } catch (error) {
                console.error('Failed to update mode:', error);
            }
        });
    }

    // Header transcript language change (Transcript mode only)
    if (headerTranscriptLang) {
        headerTranscriptLang.addEventListener('change', () => {
            const newLang = headerTranscriptLang.value;
            console.log('Header transcript language changed to:', newLang);

            // Sync settings panel language
            DOM.sourceLang.value = newLang;

            // Notify server if running
            if (isConnected && ws && isRunning) {
                sendSettingsToServer({
                    source_lang: newLang,
                    target_lang: DOM.targetLang.value,
                    tts_enabled: DOM.ttsEnabled.checked
                });
                showToast('Language changed. Please stop and restart recognition to apply.', 'warning', 5000);
            } else {
                showToast(`Language set to ${newLang.toUpperCase()}`, 'info', 2000);
            }

            // Update server config
            setServerConfig({ source_lang: newLang });
        });
    }

    // Header toggle source button (Translation mode only)
    const headerToggleSourceBtn = document.getElementById('headerToggleSourceBtn');
    const headerToggleSourceIcon = document.getElementById('headerToggleSourceIcon');
    const showSourceLangCheckbox = document.getElementById('showSourceLang');

    if (headerToggleSourceBtn && showSourceLangCheckbox) {
        headerToggleSourceBtn.addEventListener('click', () => {
            // Toggle the checkbox
            showSourceLangCheckbox.checked = !showSourceLangCheckbox.checked;

            // Update icon
            if (showSourceLangCheckbox.checked) {
                headerToggleSourceIcon.textContent = '👁️';
            } else {
                headerToggleSourceIcon.textContent = '👁️‍🗨️';
            }

            // Re-render all existing text pairs
            textPairs.forEach(pair => {
                updatePairDisplay(pair);
            });
        });
    }

    // Toggle source language button in output controls (Translation mode only - legacy)
    const toggleSourceBtn = document.getElementById('toggleSourceBtn');
    const toggleSourceIcon = document.getElementById('toggleSourceIcon');
    const toggleSourceText = document.getElementById('toggleSourceText');

    if (toggleSourceBtn && showSourceLangCheckbox) {
        toggleSourceBtn.addEventListener('click', () => {
            // Toggle the checkbox
            showSourceLangCheckbox.checked = !showSourceLangCheckbox.checked;

            // Update button text and icon
            if (showSourceLangCheckbox.checked) {
                toggleSourceIcon.textContent = '👁️';
                toggleSourceText.textContent = 'Hide Source';
                if (headerToggleSourceIcon) headerToggleSourceIcon.textContent = '👁️';
            } else {
                toggleSourceIcon.textContent = '👁️‍🗨️';
                toggleSourceText.textContent = 'Show Source';
                if (headerToggleSourceIcon) headerToggleSourceIcon.textContent = '👁️‍🗨️';
            }

            // Re-render all existing text pairs
            textPairs.forEach(pair => {
                updatePairDisplay(pair);
            });
        });
    }
}
