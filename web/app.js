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
const liveOutput = document.getElementById('liveOutput');
const modeSelect = document.getElementById('mode');
const sourceLang = document.getElementById('sourceLang');
const targetLang = document.getElementById('targetLang');
const ttsEnabled = document.getElementById('ttsEnabled');
const translationSettings = document.getElementById('translationSettings');

// ペアリング用のマップ（タイムスタンプでペアを管理）
let textPairs = new Map();

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
    const { text, timestamp, language, pair_id } = data;
    const pairId = pair_id || timestamp || Date.now().toString();

    // ペアを作成または更新
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

    // 表示を更新
    updatePairDisplay(pair);
}

// 翻訳テキストの処理
function handleTranslatedText(data) {
    const { text, timestamp, source_text, pair_id } = data;
    const pairId = pair_id || timestamp || Date.now().toString();

    // ペアを作成または更新
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

    // 表示を更新
    updatePairDisplay(pair);
}

// エラーハンドラ
function handleError(data) {
    const { message } = data;
    console.error('Server error:', message);
    alert(`Error: ${message}`);
}

// ペア表示を更新
function updatePairDisplay(pair) {
    // "Waiting..." メッセージを削除
    if (liveOutput.querySelector('p[style*="color: #999"]')) {
        liveOutput.innerHTML = '';
    }

    // 既存のエントリを探す
    let entryElement = document.getElementById(`pair-${pair.id}`);

    if (!entryElement) {
        // 新しいエントリを作成
        entryElement = document.createElement('div');
        entryElement.id = `pair-${pair.id}`;
        entryElement.className = 'text-entry';
        liveOutput.insertBefore(entryElement, liveOutput.firstChild);
    }

    // タイムスタンプを表示
    const time = new Date(pair.timestamp || Date.now());
    const timeStr = time.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    // モードを確認
    const mode = serverConfig.mode || 'translation';
    const isTranslationMode = mode === 'translation';

    // コンテンツを構築
    let html = `<div class="timestamp">${timeStr}${pair.language ? ` [${pair.language}]` : ''}</div><div class="text-pair">`;

    // 認識テキスト
    if (pair.recognized) {
        html += `
            <div class="text-item">
                <button class="play-btn" onclick="playText('${escapeHtml(pair.recognized)}', '${pair.language || 'en'}')">▶</button>
                <div class="text-content original-text">
                    <div class="text-label">${isTranslationMode ? 'Original' : 'Recognized'}</div>
                    <div class="text-value">${escapeHtml(pair.recognized)}</div>
                </div>
            </div>
        `;
    }

    // 翻訳テキスト（翻訳モードのみ）
    if (pair.translated && isTranslationMode) {
        html += `
            <div class="text-item">
                <button class="play-btn" onclick="playText('${escapeHtml(pair.translated)}', '${serverConfig.target_lang || 'ja'}')">▶</button>
                <div class="text-content translated-text">
                    <div class="text-label">Translation</div>
                    <div class="text-value">${escapeHtml(pair.translated)}</div>
                </div>
            </div>
        `;
    }

    html += '</div>';
    entryElement.innerHTML = html;

    // 最大50エントリまで保持
    while (liveOutput.children.length > 50) {
        const lastChild = liveOutput.lastChild;
        const pairId = lastChild.id.replace('pair-', '');
        textPairs.delete(pairId);
        liveOutput.removeChild(lastChild);
    }
}

// HTML エスケープ
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/'/g, '&apos;');
}

// テキスト再生（将来的に実装）
function playText(text, language) {
    console.log(`Playing text: "${text}" in language: ${language}`);
    // TODO: Web Speech API または TTS API を使用して音声再生
    alert(`Text: ${text}\nLanguage: ${language}\n\n(Audio playback not yet implemented)`);
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
        mode: modeSelect.value,
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

    console.log('Stopping recognition');

    ws.send(JSON.stringify({
        type: 'stop'
    }));

    // UI状態を即座に更新
    stopBtn.disabled = true;
    updateStatus('connecting', 'Stopping recognition...');
});

// クリアボタン
clearBtn.addEventListener('click', () => {
    liveOutput.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">Cleared</p>';
    textPairs.clear();
});

// モード変更時の処理
function updateUIForMode(mode) {
    if (mode === 'transcript') {
        // Transcript mode: Hide translation settings
        translationSettings.classList.add('hidden');
    } else {
        // Translation mode: Show translation settings
        translationSettings.classList.remove('hidden');
    }

    // 既存のペアを再描画（モードによって表示が変わるため）
    textPairs.forEach(pair => {
        updatePairDisplay(pair);
    });
}

// モード選択の変更
modeSelect.addEventListener('change', () => {
    const mode = modeSelect.value;
    console.log('Mode changed to:', mode);
    updateUIForMode(mode);

    // Update server config
    serverConfig.mode = mode;
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
            if (modeSelect && serverConfig.mode) {
                modeSelect.value = serverConfig.mode;
            }
            if (sourceLang && serverConfig.source_lang) {
                sourceLang.value = serverConfig.source_lang;
            }
            if (targetLang && serverConfig.target_lang) {
                targetLang.value = serverConfig.target_lang;
            }

            // モードに応じてUIを更新
            updateUIForMode(serverConfig.mode);
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
