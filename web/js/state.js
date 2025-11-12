/**
 * Global State Management
 *
 * Manages application state and DOM element references.
 */

// ========================================
// Global State Variables
// ========================================

// WebSocket connection
export let ws = null;
export let isConnected = false;
export let isRunning = false;

// Server configuration
export let serverConfig = {
    mode: 'translation',
    source_lang: 'en',
    target_lang: 'ja'
};

// Pairing map (managing pairs by timestamp)
export let textPairs = new Map();

// Toast notification timeout
export let toastTimeout = null;

// ========================================
// State Setters (to allow updates from other modules)
// ========================================

export function setWs(websocket) {
    ws = websocket;
}

export function setIsConnected(connected) {
    isConnected = connected;
}

export function setIsRunning(running) {
    isRunning = running;
}

export function setServerConfig(config) {
    serverConfig = { ...serverConfig, ...config };
}

export function setToastTimeout(timeout) {
    toastTimeout = timeout;
}

// ========================================
// DOM Elements
// ========================================

export const DOM = {
    // Status
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),

    // Control buttons
    startBtn: document.getElementById('startBtn'),
    stopBtn: document.getElementById('stopBtn'),
    clearBtn: document.getElementById('clearBtn'),

    // Output
    liveOutput: document.getElementById('liveOutput'),

    // Settings panel elements
    modeSelect: document.getElementById('mode'),
    sourceLang: document.getElementById('sourceLang'),
    targetLang: document.getElementById('targetLang'),
    ttsEnabled: document.getElementById('ttsEnabled'),
    translationSettings: document.getElementById('translationSettings'),

    // Display options
    showTimestamp: document.getElementById('showTimestamp'),
    showLanguage: document.getElementById('showLanguage'),

    // Settings panel
    settingsBtn: document.getElementById('settingsBtn'),
    settingsPanel: document.getElementById('settingsPanel'),
    closeSettingsBtn: document.getElementById('closeSettingsBtn'),
    overlay: document.getElementById('overlay'),

    // Header language controls
    headerSourceLang: document.getElementById('headerSourceLang'),
    headerTargetLang: document.getElementById('headerTargetLang'),
    langSwapBtn: document.getElementById('langSwapBtn'),

    // Toast notification
    toast: document.getElementById('toast')
};
