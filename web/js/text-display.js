/**
 * Text Display and Pairing Management
 *
 * Handles recognized and translated text display with pairing logic.
 */

import { textPairs, serverConfig, DOM } from './state.js';

/**
 * Handle recognized text message
 */
export function handleRecognizedText(data) {
    const { text, timestamp, language, pair_id } = data;
    const pairId = pair_id || timestamp || Date.now().toString();

    // Create or update pair
    let pair = textPairs.get(pairId) || {
        id: pairId,
        recognized: null,
        translated: null,
        language: language,
        timestamp: timestamp
    };

    pair.recognized = text;
    pair.language = language;
    pair.timestamp = timestamp;
    textPairs.set(pairId, pair);

    // Update display
    updatePairDisplay(pair);
}

/**
 * Handle translated text message
 */
export function handleTranslatedText(data) {
    const { text, timestamp, source_text, pair_id } = data;
    const pairId = pair_id || timestamp || Date.now().toString();

    // Create or update pair
    let pair = textPairs.get(pairId) || {
        id: pairId,
        recognized: source_text || null,
        translated: null,
        timestamp: timestamp
    };

    pair.translated = text;
    if (source_text && !pair.recognized) {
        pair.recognized = source_text;
    }
    if (timestamp && !pair.timestamp) {
        pair.timestamp = timestamp;
    }
    textPairs.set(pairId, pair);

    // Update display
    updatePairDisplay(pair);
}

/**
 * Update pair display in the UI
 */
export function updatePairDisplay(pair) {
    // Remove "Waiting..." message
    if (DOM.liveOutput.querySelector('p[style*="color: #999"]')) {
        DOM.liveOutput.innerHTML = '';
    }

    // Find existing entry
    let entryElement = document.getElementById(`pair-${pair.id}`);

    // Check mode
    const mode = serverConfig.mode || 'translation';
    const isTranslationMode = mode === 'translation';

    if (!entryElement) {
        // Create new entry
        entryElement = document.createElement('div');
        entryElement.id = `pair-${pair.id}`;
        entryElement.className = isTranslationMode ? 'text-entry' : 'text-entry transcript-only';
        DOM.liveOutput.insertBefore(entryElement, DOM.liveOutput.firstChild);
    } else {
        // Update class for mode change
        entryElement.className = isTranslationMode ? 'text-entry' : 'text-entry transcript-only';
    }

    // Play button (translated text in translation mode, recognized text otherwise)
    const playButtonText = isTranslationMode && pair.translated ? pair.translated : pair.recognized;
    const playButtonLang = isTranslationMode && pair.translated ? serverConfig.target_lang || 'ja' : pair.language || 'en';

    // Build content (simple vertical layout)
    let html = `
        <button class="play-btn" onclick="window.audioApp.playText('${escapeHtml(playButtonText || '')}', '${playButtonLang}')">▶</button>
        <div class="text-pair">
    `;

    // Check if we should show source language (for toggle button)
    const showSourceLangCheckbox = document.getElementById('showSourceLang');
    const displaySource = showSourceLangCheckbox ? showSourceLangCheckbox.checked : true;

    // Translation mode: source (small, light) → translation (large, main)
    if (isTranslationMode) {
        // Show original text only if toggle is enabled
        if (pair.recognized && displaySource) {
            html += `<div class="original-text">${escapeHtml(pair.recognized)}</div>`;
        }
        // Always show translated text
        if (pair.translated) {
            html += `<div class="translated-text">${escapeHtml(pair.translated)}</div>`;
        }
    } else {
        // Transcript mode: just recognized text (large)
        if (pair.recognized) {
            html += `<div class="original-text">${escapeHtml(pair.recognized)}</div>`;
        }
    }

    html += '</div>';
    entryElement.innerHTML = html;

    // Keep max 50 entries
    while (DOM.liveOutput.children.length > 50) {
        const lastChild = DOM.liveOutput.lastChild;
        const pairId = lastChild.id.replace('pair-', '');
        textPairs.delete(pairId);
        DOM.liveOutput.removeChild(lastChild);
    }
}

/**
 * HTML escape utility
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/'/g, '&apos;');
}

/**
 * Text playback (to be implemented)
 */
export function playText(text, language) {
    console.log(`Playing text: "${text}" in language: ${language}`);
    // TODO: Implement Web Speech API or TTS API for audio playback
    alert(`Text: ${text}\nLanguage: ${language}\n\n(Audio playback not yet implemented)`);
}

/**
 * Clear all text pairs
 */
export function clearTextPairs() {
    DOM.liveOutput.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">Cleared</p>';
    textPairs.clear();
}
