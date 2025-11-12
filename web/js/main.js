/**
 * Main Entry Point
 *
 * Initializes the application and coordinates all modules.
 */

import { connectWebSocket } from './websocket.js';
import { setupUIEventListeners } from './ui.js';
import { loadServerConfig, loadFullConfig, setupAdvancedSettings, checkRecognitionStatus } from './settings.js';
import { loadAudioDevices } from './audio-devices.js';
import { playText } from './text-display.js';

/**
 * Initialize application on page load
 */
async function initializeApp() {
    console.log('Initializing Audio Recognition System Web UI...');

    try {
        // Load configurations
        await loadServerConfig();
        await loadFullConfig();  // Load advanced settings

        // Load audio devices
        await loadAudioDevices();

        // Check initial recognition status
        await checkRecognitionStatus();

        // Setup advanced settings event listeners
        setupAdvancedSettings();

        // Setup UI event listeners
        setupUIEventListeners();

        // Connect WebSocket
        connectWebSocket();

        console.log('Application initialized successfully');
    } catch (error) {
        console.error('Error during application initialization:', error);
    }
}

// Expose playText function to global scope for inline onclick handlers
window.audioApp = {
    playText: playText
};

// Initialize application when DOM is fully loaded
window.addEventListener('load', initializeApp);
