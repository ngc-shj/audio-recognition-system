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
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const clearBtn = document.getElementById('clearBtn');
const liveOutput = document.getElementById('liveOutput');
const modeSelect = document.getElementById('mode');
const sourceLang = document.getElementById('sourceLang');
const targetLang = document.getElementById('targetLang');
const ttsEnabled = document.getElementById('ttsEnabled');
const translationSettings = document.getElementById('translationSettings');
const showTimestamp = document.getElementById('showTimestamp');
const showLanguage = document.getElementById('showLanguage');
const settingsBtn = document.getElementById('settingsBtn');
const settingsPanel = document.getElementById('settingsPanel');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const overlay = document.getElementById('overlay');
const headerSourceLang = document.getElementById('headerSourceLang');
const headerTargetLang = document.getElementById('headerTargetLang');
const langSwapBtn = document.getElementById('langSwapBtn');

// ペアリング用のマップ（タイムスタンプでペアを管理）
let textPairs = new Map();

// Toast notification
const toast = document.getElementById('toast');
let toastTimeout = null;

function showToast(message, type = 'info', duration = 4000) {
    // Clear any existing timeout
    if (toastTimeout) {
        clearTimeout(toastTimeout);
    }

    // Set message and type
    toast.textContent = message;
    toast.className = `toast ${type}`;

    // Show toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    // Hide after duration
    toastTimeout = setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

// 設定パネルの開閉
function openSettings() {
    settingsPanel.classList.add('open');
    overlay.classList.add('active');
}

function closeSettings() {
    settingsPanel.classList.remove('open');
    overlay.classList.remove('active');
}

settingsBtn.addEventListener('click', openSettings);
closeSettingsBtn.addEventListener('click', closeSettings);
overlay.addEventListener('click', closeSettings);

// 言語入れ替えボタン
langSwapBtn.addEventListener('click', () => {
    // 言語を入れ替え
    const tempSource = headerSourceLang.value;
    headerSourceLang.value = headerTargetLang.value;
    headerTargetLang.value = tempSource;

    // 設定パネルの言語も同期
    sourceLang.value = headerSourceLang.value;
    targetLang.value = headerTargetLang.value;

    // 実行中の場合はサーバーに通知し、再起動を促す
    if (isConnected && ws && isRunning) {
        ws.send(JSON.stringify({
            type: 'settings',
            settings: {
                source_lang: headerSourceLang.value,
                target_lang: headerTargetLang.value,
                tts_enabled: ttsEnabled.checked
            }
        }));

        // ユーザーに視覚的な通知
        showToast('Language settings changed. Please stop and restart recognition to apply changes.', 'warning', 5000);
    } else {
        // 停止中の場合は次回起動時に適用されることを通知
        showToast(`Languages swapped: ${headerSourceLang.value.toUpperCase()} → ${headerTargetLang.value.toUpperCase()}`, 'info', 3000);
    }

    // サーバー設定を更新
    serverConfig.source_lang = headerSourceLang.value;
    serverConfig.target_lang = headerTargetLang.value;
});

// WebSocket接続を確立
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    console.log('Connecting to WebSocket:', wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = async () => {
        console.log('WebSocket connected');
        isConnected = true;

        // WebSocket接続後に認識ステータスを再確認してボタン状態を適切に設定
        await checkRecognitionStatus();

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
    const { status } = data;

    if (status === 'running') {
        isRunning = true;
        updateStatus('running', 'Recognition Running');
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else if (status === 'stopped') {
        isRunning = false;
        updateStatus('connected', 'Connected');
        startBtn.disabled = false;
        stopBtn.disabled = true;
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

    // モードを確認
    const mode = serverConfig.mode || 'translation';
    const isTranslationMode = mode === 'translation';

    if (!entryElement) {
        // 新しいエントリを作成
        entryElement = document.createElement('div');
        entryElement.id = `pair-${pair.id}`;
        entryElement.className = isTranslationMode ? 'text-entry' : 'text-entry transcript-only';
        liveOutput.insertBefore(entryElement, liveOutput.firstChild);
    } else {
        // モード変更に対応してクラスを更新
        entryElement.className = isTranslationMode ? 'text-entry' : 'text-entry transcript-only';
    }

    // タイムスタンプを表示
    const time = new Date(pair.timestamp || Date.now());
    const timeStr = time.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    // 再生ボタン（翻訳モードでは翻訳テキスト用、それ以外は認識テキスト用）
    const playButtonText = isTranslationMode && pair.translated ? pair.translated : pair.recognized;
    const playButtonLang = isTranslationMode && pair.translated ? serverConfig.target_lang || 'ja' : pair.language || 'en';

    // コンテンツを構築（シンプルな縦並びレイアウト）
    let html = `
        <button class="play-btn" onclick="playText('${escapeHtml(playButtonText || '')}', '${playButtonLang}')">▶</button>
        <div class="text-pair">
    `;

    // タイムスタンプと言語コードの表示制御
    const displayTimestamp = showTimestamp.checked;
    const displayLanguage = showLanguage.checked;

    let prefix = '';
    if (displayTimestamp) {
        prefix += timeStr;
    }
    if (displayLanguage && pair.language) {
        prefix += ` [${pair.language}]`;
    }
    if (prefix) {
        prefix = `<span class="timestamp">${prefix}</span> `;
    }

    // 翻訳モード：時刻+原語（小さく薄く）→ 翻訳語（大きくメイン）
    if (isTranslationMode) {
        if (pair.recognized) {
            html += `<div class="original-text">${prefix}${escapeHtml(pair.recognized)}</div>`;
        }
        if (pair.translated) {
            html += `<div class="translated-text">${escapeHtml(pair.translated)}</div>`;
        }
    } else {
        // Transcriptモード：時刻+認識テキスト（大きく）
        if (pair.recognized) {
            html += `<div class="original-text">${prefix}${escapeHtml(pair.recognized)}</div>`;
        }
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
sourceLang.addEventListener('change', () => {
    // ヘッダーの言語選択も同期
    headerSourceLang.value = sourceLang.value;

    if (!isConnected || !ws || !isRunning) return;

    ws.send(JSON.stringify({
        type: 'settings',
        settings: {
            source_lang: sourceLang.value,
            target_lang: targetLang.value,
            tts_enabled: ttsEnabled.checked
        }
    }));
});

targetLang.addEventListener('change', () => {
    // ヘッダーの言語選択も同期
    headerTargetLang.value = targetLang.value;

    if (!isConnected || !ws || !isRunning) return;

    ws.send(JSON.stringify({
        type: 'settings',
        settings: {
            source_lang: sourceLang.value,
            target_lang: targetLang.value,
            tts_enabled: ttsEnabled.checked
        }
    }));
});

ttsEnabled.addEventListener('change', () => {
    if (!isConnected || !ws || !isRunning) return;

    ws.send(JSON.stringify({
        type: 'settings',
        settings: {
            source_lang: sourceLang.value,
            target_lang: targetLang.value,
            tts_enabled: ttsEnabled.checked
        }
    }));
});

// 表示設定変更時の処理（既存のペアを再描画）
[showTimestamp, showLanguage].forEach(element => {
    element.addEventListener('change', () => {
        // 既存のペアを再描画
        textPairs.forEach(pair => {
            updatePairDisplay(pair);
        });
    });
});

// ヘッダー言語切り替え（リアルタイム変更）
headerSourceLang.addEventListener('change', () => {
    const newLang = headerSourceLang.value;
    console.log('Header source language changed to:', newLang);

    // 設定パネルの言語も同期
    sourceLang.value = newLang;

    // 実行中の場合はサーバーに通知し、再起動を促す
    if (isConnected && ws && isRunning) {
        ws.send(JSON.stringify({
            type: 'settings',
            settings: {
                source_lang: newLang,
                target_lang: targetLang.value,
                tts_enabled: ttsEnabled.checked
            }
        }));
        showToast('Source language changed. Please stop and restart recognition to apply.', 'warning', 5000);
    } else {
        showToast(`Source language set to ${newLang.toUpperCase()}`, 'info', 2000);
    }

    // サーバー設定を更新
    serverConfig.source_lang = newLang;
});

headerTargetLang.addEventListener('change', () => {
    const newLang = headerTargetLang.value;
    console.log('Header target language changed to:', newLang);

    // 設定パネルの言語も同期
    targetLang.value = newLang;

    // 実行中の場合はサーバーに通知し、再起動を促す
    if (isConnected && ws && isRunning) {
        ws.send(JSON.stringify({
            type: 'settings',
            settings: {
                source_lang: sourceLang.value,
                target_lang: newLang,
                tts_enabled: ttsEnabled.checked
            }
        }));
        showToast('Target language changed. Please stop and restart recognition to apply.', 'warning', 5000);
    } else {
        showToast(`Target language set to ${newLang.toUpperCase()}`, 'info', 2000);
    }

    // サーバー設定を更新
    serverConfig.target_lang = newLang;
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
                headerSourceLang.value = serverConfig.source_lang;
            }
            if (targetLang && serverConfig.target_lang) {
                targetLang.value = serverConfig.target_lang;
                headerTargetLang.value = serverConfig.target_lang;
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
                // 認識実行中
                isRunning = true;
                updateStatus('running', 'Recognition Running');
                startBtn.disabled = true;
                stopBtn.disabled = false;
            } else {
                // 認識停止中
                isRunning = false;
                updateStatus('connected', 'Connected');
                startBtn.disabled = false;
                stopBtn.disabled = true;
            }
        }
    } catch (error) {
        console.error('Failed to check recognition status:', error);
        // エラー時は接続されていない状態にする
        updateStatus('disconnected', 'Disconnected');
        startBtn.disabled = true;
        stopBtn.disabled = true;
    }
}

// ========================================
// Advanced Settings Management
// ========================================

// Load full config from server
async function loadFullConfig() {
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

// Populate advanced settings UI with config values
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

    // Audio Device Settings - これらは個別にロードされる
    // (loadAudioDevicesで処理)
}

// Setup platform-dependent UI (ASR model fields)
function setupPlatformDependentUI() {
    // Detect macOS using userAgent (more reliable than deprecated navigator.platform)
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

// Setup advanced settings event listeners
function setupAdvancedSettings() {
    // Setup platform-dependent UI first
    setupPlatformDependentUI();

    // API enabled checkbox toggle (exclusive with local model)
    document.getElementById('apiEnabled').addEventListener('change', (e) => {
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

    // Range input value display updates
    document.getElementById('silenceThreshold').addEventListener('input', (e) => {
        document.getElementById('silenceThresholdValue').textContent = e.target.value;
    });

    document.getElementById('mediumPause').addEventListener('input', (e) => {
        document.getElementById('mediumPauseValue').textContent = `${e.target.value}s`;
    });

    document.getElementById('longPause').addEventListener('input', (e) => {
        document.getElementById('longPauseValue').textContent = `${e.target.value}s`;
    });

    document.getElementById('temperature').addEventListener('input', (e) => {
        document.getElementById('temperatureValue').textContent = e.target.value;
    });

    document.getElementById('contextWindowSize').addEventListener('input', (e) => {
        document.getElementById('contextWindowSizeValue').textContent = `${e.target.value} sentences`;
    });

    // Refresh devices button
    document.getElementById('refreshInputDevices').addEventListener('click', async () => {
        await loadAudioDevices();
        showToast('🔄 Audio devices refreshed', 'info', 2000);
    });

    // Save Advanced Settings button
    document.getElementById('saveAdvancedSettings').addEventListener('click', async () => {
        await saveAdvancedSettings();
    });
}

// Save advanced settings to server
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
        'translation.context.window_size': parseInt(document.getElementById('contextWindowSize').value)
    };

    // Add platform-specific ASR model field
    if (isMac) {
        updates['models.asr.darwin.model_path'] = document.getElementById('asrModelPath').value;
    } else {
        updates['models.asr.darwin.model_size'] = document.getElementById('asrModelSize').value;
    }

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
            showToast('✅ Settings saved successfully! Restart recognition for changes to take effect.', 'info', 5000);

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

// Load audio devices and populate dropdowns
async function loadAudioDevices() {
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

            // ループバック防止：input/output device選択時の相互排他チェック
            setupDeviceSelectionValidation();

        }
    } catch (error) {
        console.error('Failed to load audio devices:', error);
    }
}

// デバイス選択の検証（ループバック防止）
function setupDeviceSelectionValidation() {
    const inputSelect = document.getElementById('inputDevice');
    const outputSelect = document.getElementById('outputDevice');

    if (!inputSelect || !outputSelect) return;

    // Input device変更時
    inputSelect.addEventListener('change', () => {
        const inputDevice = inputSelect.value;
        const outputDevice = outputSelect.value;

        // 両方が選択されていて、かつ同じデバイスの場合
        if (inputDevice && outputDevice && inputDevice === outputDevice) {
            showToast('⚠️ Warning: Input and Output devices are the same. This may cause audio feedback loop!', 'warning', 5000);

            // Output deviceを自動的にDefaultに戻す
            outputSelect.value = '';
            showToast('Output device reset to Default to prevent feedback loop.', 'info', 3000);
        }
    });

    // Output device変更時
    outputSelect.addEventListener('change', () => {
        const inputDevice = inputSelect.value;
        const outputDevice = outputSelect.value;

        // 両方が選択されていて、かつ同じデバイスの場合
        if (inputDevice && outputDevice && inputDevice === outputDevice) {
            showToast('⚠️ Warning: Input and Output devices are the same. This may cause audio feedback loop!', 'warning', 5000);

            // Input deviceを自動的にDefaultに戻す
            inputSelect.value = '';
            showToast('Input device reset to Default to prevent feedback loop.', 'info', 3000);
        }
    });
}

// ページロード時に設定を読み込んでから接続
window.addEventListener('load', async () => {
    await loadServerConfig();
    await loadFullConfig();  // Load advanced settings
    await loadAudioDevices();  // Load audio devices
    await checkRecognitionStatus();
    setupAdvancedSettings();  // Setup advanced settings event listeners
    connectWebSocket();
});
