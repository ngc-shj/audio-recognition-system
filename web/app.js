// WebSocket connection
let ws = null;
let isConnected = false;
let isRunning = false;

// Server configuration
let serverConfig = {
    mode: 'translation',
    source_lang: 'en',
    target_lang: 'ja'
};

// DOM elements
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const statsText = document.getElementById('statsText');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const clearBtn = document.getElementById('clearBtn');
const recognizedOutput = document.getElementById('recognizedOutput');
const translatedOutput = document.getElementById('translatedOutput');
const sourceLang = document.getElementById('sourceLang');
const targetLang = document.getElementById('targetLang');
const ttsEnabled = document.getElementById('ttsEnabled');

// WebSocket接続を確立
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    console.log('Connecting to WebSocket:', wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        isConnected = true;
        updateStatus('connected', 'Connected');
        startBtn.disabled = false;

        // Ping/pongで接続維持
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateStatus('disconnected', 'Connection Error');
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        isConnected = false;
        updateStatus('disconnected', 'Disconnected');
        startBtn.disabled = true;
        stopBtn.disabled = true;

        // 5秒後に再接続を試みる
        setTimeout(() => {
            console.log('Attempting to reconnect...');
            connectWebSocket();
        }, 5000);
    };
}

// メッセージハンドラ
function handleMessage(data) {
    const { type } = data;

    switch (type) {
        case 'pong':
            // Ping/pong応答
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

// ステータスメッセージの処理
function handleStatusMessage(data) {
    const { message, status } = data;
    console.log('Status:', status, message);

    if (status === 'running') {
        isRunning = true;
        updateStatus('running', 'Recognition Running');
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statsText.textContent = 'Recognition: Active';
    } else if (status === 'stopped') {
        isRunning = false;
        updateStatus('connected', 'Connected');
        startBtn.disabled = false;
        stopBtn.disabled = true;
        statsText.textContent = 'Recognition: Idle';
    }
}

// 認識テキストの処理
function handleRecognizedText(data) {
    const { text, timestamp, language } = data;
    addTextEntry(recognizedOutput, text, timestamp, language, false);
}

// 翻訳テキストの処理
function handleTranslatedText(data) {
    const { text, timestamp, source_text } = data;
    addTextEntry(translatedOutput, text, timestamp, null, true);
}

// エラーハンドラ
function handleError(data) {
    const { message } = data;
    console.error('Server error:', message);
    alert(`Error: ${message}`);
}

// テキストエントリを追加
function addTextEntry(container, text, timestamp, language, isTranslation) {
    // "Waiting..." メッセージを削除
    if (container.querySelector('p[style*="color: #999"]')) {
        container.innerHTML = '';
    }

    const entry = document.createElement('div');
    entry.className = `text-entry${isTranslation ? ' translation' : ''}`;

    const time = new Date(timestamp || Date.now());
    const timeStr = time.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    entry.innerHTML = `
        <div class="timestamp">${timeStr}${language ? ` [${language}]` : ''}</div>
        <div>${text}</div>
    `;

    container.insertBefore(entry, container.firstChild);

    // 最大50エントリまで保持
    while (container.children.length > 50) {
        container.removeChild(container.lastChild);
    }
}

// ステータス更新
function updateStatus(status, text) {
    statusDot.className = `status-dot ${status}`;
    statusText.textContent = text;
}

// 開始ボタン
startBtn.addEventListener('click', () => {
    if (!isConnected || !ws) return;

    const settings = {
        source_lang: sourceLang.value,
        target_lang: targetLang.value,
        tts_enabled: ttsEnabled.checked
    };

    console.log('Starting recognition with settings:', settings);

    ws.send(JSON.stringify({
        type: 'start',
        settings: settings
    }));

    // UI状態を即座に更新
    startBtn.disabled = true;
    updateStatus('connecting', 'Starting recognition...');
});

// 停止ボタン
stopBtn.addEventListener('click', () => {
    if (!isConnected || !ws) return;

    ws.send(JSON.stringify({
        type: 'stop'
    }));
});

// クリアボタン
clearBtn.addEventListener('click', () => {
    recognizedOutput.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">Cleared</p>';
    translatedOutput.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">Cleared</p>';
});

// 設定変更時の処理
[sourceLang, targetLang, ttsEnabled].forEach(element => {
    element.addEventListener('change', () => {
        if (!isConnected || !ws || !isRunning) return;

        const settings = {
            source_lang: sourceLang.value,
            target_lang: targetLang.value,
            tts_enabled: ttsEnabled.checked
        };

        ws.send(JSON.stringify({
            type: 'settings',
            settings: settings
        }));
    });
});

// サーバー設定を取得してUIに反映
async function loadServerConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            serverConfig = await response.json();
            console.log('Server config loaded:', serverConfig);

            // UIに反映
            if (sourceLang && serverConfig.source_lang) {
                sourceLang.value = serverConfig.source_lang;
            }
            if (targetLang && serverConfig.target_lang) {
                targetLang.value = serverConfig.target_lang;
            }

            // transcriptモードの場合は翻訳パネルを非表示
            if (serverConfig.mode === 'transcript') {
                const translatedPanel = document.querySelector('.panel:has(#translatedOutput)');
                if (translatedPanel) {
                    translatedPanel.style.display = 'none';
                }
            }
        }
    } catch (error) {
        console.error('Failed to load server config:', error);
    }
}

// 認識ステータスを取得
async function checkRecognitionStatus() {
    try {
        const response = await fetch('/api/status');
        if (response.ok) {
            const status = await response.json();
            if (status.recognition_active) {
                isRunning = true;
                updateStatus('running', 'Recognition Running');
                startBtn.disabled = true;
                stopBtn.disabled = false;
                statsText.textContent = 'Recognition: Active';
            }
        }
    } catch (error) {
        console.error('Failed to check recognition status:', error);
    }
}

// ページロード時に設定を読み込んでから接続
window.addEventListener('load', async () => {
    await loadServerConfig();
    await checkRecognitionStatus();
    connectWebSocket();
});
