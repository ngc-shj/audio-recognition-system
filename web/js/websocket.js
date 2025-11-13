/**
 * WebSocket Connection Management
 *
 * Handles WebSocket connection, message routing, and reconnection logic.
 */

import { ws, isConnected, isRunning, setWs, setIsConnected, setIsRunning, DOM } from './state.js';
import { updateStatus } from './ui.js';
import { handleRecognizedText, handleTranslatedText } from './text-display.js';
import { checkRecognitionStatus } from './settings.js';

/**
 * Establish WebSocket connection
 */
export function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    console.log('Connecting to WebSocket:', wsUrl);
    const websocket = new WebSocket(wsUrl);
    setWs(websocket);

    websocket.onopen = async () => {
        console.log('WebSocket connected');
        setIsConnected(true);

        // Check recognition status after connection
        await checkRecognitionStatus();

        // Keep-alive ping/pong
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    };

    websocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    };

    websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateStatus('disconnected', 'Connection Error');
    };

    websocket.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        updateStatus('disconnected', 'Disconnected');
        DOM.startBtn.disabled = true;
        DOM.stopBtn.disabled = true;

        // Reconnect after 5 seconds
        setTimeout(() => {
            console.log('Attempting to reconnect...');
            connectWebSocket();
        }, 5000);
    };
}

/**
 * Route incoming WebSocket messages
 */
function handleMessage(data) {
    const { type } = data;

    switch (type) {
        case 'pong':
            // Ping/pong response
            break;

        case 'status':
            handleStatusMessage(data);
            break;

        case 'recognized':
            handleRecognizedText(data);
            break;

        case 'translated':
            handleTranslatedText(data);
            break;

        case 'error':
            handleError(data);
            break;

        default:
            console.log('Unknown message type:', type, data);
    }
}

/**
 * Handle status messages
 */
function handleStatusMessage(data) {
    const { status } = data;

    // Get mode toggle buttons
    const transcriptModeBtn = document.getElementById('transcriptModeBtn');
    const translationModeBtn = document.getElementById('translationModeBtn');

    if (status === 'running') {
        setIsRunning(true);
        updateStatus('running', 'Recognition Running');
        DOM.startBtn.disabled = true;
        DOM.stopBtn.disabled = false;

        // Disable mode toggle buttons during recognition
        if (transcriptModeBtn) transcriptModeBtn.disabled = true;
        if (translationModeBtn) translationModeBtn.disabled = true;
    } else if (status === 'stopped') {
        setIsRunning(false);
        updateStatus('connected', 'Connected');
        DOM.startBtn.disabled = false;
        DOM.stopBtn.disabled = true;

        // Enable mode toggle buttons when stopped
        if (transcriptModeBtn) transcriptModeBtn.disabled = false;
        if (translationModeBtn) translationModeBtn.disabled = false;
    }
}

/**
 * Handle error messages
 */
function handleError(data) {
    const { message } = data;
    console.error('Server error:', message);
    alert(`Error: ${message}`);
}
