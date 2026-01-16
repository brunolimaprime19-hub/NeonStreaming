const video = document.getElementById('remoteVideo');
const fsrCanvas = document.getElementById('fsrCanvas');
const startBtn = document.getElementById('startBtn');
const statusOverlay = document.getElementById('status-overlay');
const statusMsg = document.getElementById('status-msg');
const loader = document.getElementById('loader');

// ==========================================
// WebGL Renderer with AMD FSR 1.0 (EASU)
// ==========================================
class WebGLRenderer {
    constructor(videoElement, canvasElement) {
        this.video = videoElement;
        this.canvas = canvasElement;
        this.gl = this.canvas.getContext('webgl2', {
            antialias: false,
            alpha: false,
            depth: false,
            stencil: false,
            preserveDrawingBuffer: false
        });

        if (!this.gl) {
            console.error('WebGL2 not supported');
            return;
        }

        this.enabled = false;
        this.program = null;
        this.texture = null;
        this.vao = null;
        this.init();
    }

    init() {
        const gl = this.gl;

        // Vertex Shader (Simple Quad)
        const vsSource = `#version 300 es
            in vec2 position;
            out vec2 vTexCoord;
            void main() {
                vTexCoord = position * 0.5 + 0.5;
                vTexCoord.y = 1.0 - vTexCoord.y;
                gl_Position = vec4(position, 0.0, 1.0);
            }
        `;

        // Fragment Shader (AMD FSR 1.0 EASU Simplified)
        const fsSource = `#version 300 es
            precision highp float;
            uniform sampler2D uTexture;
            uniform vec2 uResolution;
            uniform vec2 uInputResolution;
            in vec2 vTexCoord;
            out vec4 fragColor;

            // Simplified EASU (Edge Adaptive Spatial Upsampling)
            // Implementation based on AMD FidelityFX FSR 1.0
            
            vec3 gather(vec2 pos, vec2 offset) {
                return texture(uTexture, pos + offset / uInputResolution).rgb;
            }

            void main() {
                if (uInputResolution.x >= uResolution.x) {
                    fragColor = texture(uTexture, vTexCoord);
                    return;
                }

                vec2 pos = vTexCoord;
                
                // Simplified EASU: Edge detection and kernel weighting
                vec3 c = gather(pos, vec2(0, 0));
                vec3 n = gather(pos, vec2(0, -1));
                vec3 s = gather(pos, vec2(0, 1));
                vec3 w = gather(pos, vec2(-1, 0));
                vec3 e = gather(pos, vec2(1, 0));
                
                // Detect contrast/edges
                float lumaC = dot(c, vec3(0.299, 0.587, 0.114));
                float lumaN = dot(n, vec3(0.299, 0.587, 0.114));
                float lumaS = dot(s, vec3(0.299, 0.587, 0.114));
                float lumaW = dot(w, vec3(0.299, 0.587, 0.114));
                float lumaE = dot(e, vec3(0.299, 0.587, 0.114));
                
                float maxLuma = max(max(lumaC, lumaN), max(max(lumaS, lumaW), lumaE));
                float minLuma = min(min(lumaC, lumaN), min(min(lumaS, lumaW), lumaE));
                float contrast = (maxLuma - minLuma) / (maxLuma + 0.0001);
                
                // Sharpness factor
                float sharpness = 0.5; 
                vec3 result = c;
                
                if (contrast > 0.1) {
                    // Adaptive sharpening based on edge detection
                    vec3 edge = (n + s + w + e) * 0.25;
                    result = mix(c, edge, contrast * sharpness);
                }

                fragColor = vec4(result, 1.0);
            }
        `;

        this.program = this.createProgram(vsSource, fsSource);

        // Quad Geometry
        const positions = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
        const vbo = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
        gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

        this.vao = gl.createVertexArray();
        gl.bindVertexArray(this.vao);
        const posLoc = gl.getAttribLocation(this.program, 'position');
        gl.enableVertexAttribArray(posLoc);
        gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

        this.texture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, this.texture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    }

    createProgram(vsSource, fsSource) {
        const gl = this.gl;
        const vs = gl.createShader(gl.VERTEX_SHADER);
        gl.shaderSource(vs, vsSource);
        gl.compileShader(vs);

        const fs = gl.createShader(gl.FRAGMENT_SHADER);
        gl.shaderSource(fs, fsSource);
        gl.compileShader(fs);

        const program = gl.createProgram();
        gl.attachShader(program, vs);
        gl.attachShader(program, fs);
        gl.linkProgram(program);
        return program;
    }

    render() {
        if (!this.enabled || this.video.readyState < 2) return;

        const gl = this.gl;

        // Match canvas size to display size
        if (this.canvas.width !== this.video.videoWidth || this.canvas.height !== this.video.videoHeight) {
            // We want the canvas to be the target resolution, but for now we match display container
            const container = this.video.parentElement;
            this.canvas.width = container.clientWidth;
            this.canvas.height = container.clientHeight;
        }

        gl.viewport(0, 0, this.canvas.width, this.canvas.height);
        gl.useProgram(this.program);

        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, this.texture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, this.video);

        gl.uniform1i(gl.getUniformLocation(this.program, 'uTexture'), 0);
        gl.uniform2f(gl.getUniformLocation(this.program, 'uResolution'), this.canvas.width, this.canvas.height);
        gl.uniform2f(gl.getUniformLocation(this.program, 'uInputResolution'), this.video.videoWidth, this.video.videoHeight);

        gl.bindVertexArray(this.vao);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);

        if (this.enabled) {
            requestAnimationFrame(() => this.render());
        }
    }

    enable() {
        this.enabled = true;
        this.video.classList.add('hidden');
        this.canvas.classList.remove('hidden');
        this.render();
    }

    disable() {
        this.enabled = false;
        this.video.classList.remove('hidden');
        this.canvas.classList.add('hidden');
    }
}

// Initialize FSR Renderer
const fsrRenderer = new WebGLRenderer(video, fsrCanvas);

const statVideoLatency = document.getElementById('stat-video-latency');
const statAudioLatency = document.getElementById('stat-audio-latency');
const statFPS = document.getElementById('stat-fps');
const statBitrate = document.getElementById('stat-bitrate');
const statAudioBitrate = document.createElement('div');
statAudioBitrate.id = 'stat-audio-bitrate';
statAudioBitrate.innerText = 'Audio: Waiting...';
statAudioBitrate.style.color = '#ffff00';
statBitrate.parentNode.appendChild(statAudioBitrate);

let pc = null;
let dc = null;
let startTime = 0;

const CONFIG = {
    sdpSemantics: 'unified-plan',
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
};

function updateStatus(msg, showLoader = false) {
    statusMsg.innerText = msg;
    loader.style.display = showLoader ? 'block' : 'none';
    if (showLoader) startBtn.classList.add('hidden');
    else startBtn.classList.remove('hidden');
}

async function startStream() {
    updateStatus('Iniciando WebRTC...', true);
    resetStats();

    try {
        pc = new RTCPeerConnection(CONFIG);

        // Data Channel for Input
        dc = pc.createDataChannel('input', { ordered: false });
        setupDataChannel(dc);

        // Video and Audio Receiving
        pc.addTransceiver('video', { direction: 'recvonly' });
        pc.addTransceiver('audio', { direction: 'recvonly' });

        const remoteStream = new MediaStream();
        video.srcObject = remoteStream;

        pc.ontrack = (evt) => {
            console.log('═══════════════════════════════════════════════════');
            console.log('🎵 TRACK RECEIVED:', evt.track.kind);

            if (evt.track.kind === 'audio') {
                console.log('🔊 AUDIO TRACK RECEIVED! Starting diagnostic monitor...');

                // Audio Element Setup
                video.volume = 1.0;
                video.muted = false;
            }

            remoteStream.addTrack(evt.track);

            if (evt.track.kind === 'video') {
                console.log('📹 VIDEO TRACK - Hiding status overlay');
                statusOverlay.classList.add('hidden');
                startStatsInterval();
            }

            if (video.paused) {
                video.play().catch(e => console.warn("Auto-play blocked:", e));
            }

            console.log('═══════════════════════════════════════════════════');
        };

        pc.oniceconnectionstatechange = () => {
            console.log('ICE State:', pc.iceConnectionState);
            if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
                statusOverlay.classList.remove('hidden');
                updateStatus('Conexão perdida. Tente novamente.', false);
            }
        };

        // Negotiation
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        // Wait for ICE gathering
        await new Promise((resolve) => {
            if (pc.iceGatheringState === 'complete') resolve();
            else {
                const checkIce = () => {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkIce);
                        resolve();
                    }
                };
                pc.addEventListener('icegatheringstatechange', checkIce);
                setTimeout(resolve, 3000);
            }
        });

        const response = await fetch('/offer', {
            method: 'POST',
            body: JSON.stringify({
                sdp: pc.localDescription.sdp,
                type: pc.localDescription.type
            }),
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) throw new Error('Falha na resposta do servidor');

        const answer = await response.json();
        await pc.setRemoteDescription(new RTCSessionDescription(answer));

    } catch (e) {
        console.error("WebRTC Start Error:", e);
        updateStatus('Erro: ' + e.message, false);
    }
}

function setupDataChannel(channel) {
    channel.onopen = () => console.log('Data Channel Aberto');
    channel.onclose = () => console.log('Data Channel Fechado');
}

function sendInput(type, code, value) {
    if (dc && dc.readyState === 'open') {
        dc.send(JSON.stringify({ type, code, value }));
    }
}


// Haptic Feedback Helper
let vibrationEnabled = true;
let vibrationInitialized = false;
let vibrationSupported = false;

// Check vibration support on load
function checkVibrationSupport() {
    if ('vibrate' in navigator) {
        vibrationSupported = true;
        console.log('✅ Vibration API is supported');
        return true;
    } else if ('mozVibrate' in navigator) {
        vibrationSupported = true;
        console.log('✅ Vibration API is supported (Firefox)');
        return true;
    } else if ('webkitVibrate' in navigator) {
        vibrationSupported = true;
        console.log('✅ Vibration API is supported (Webkit)');
        return true;
    } else {
        console.warn('❌ Vibration API not supported on this device/browser');
        return false;
    }
}

// Initialize vibration on first user interaction
function initializeVibration() {
    if (vibrationInitialized || !vibrationSupported) return;

    try {
        // Try a test vibration
        const success = navigator.vibrate(1);
        vibrationInitialized = true;
        console.log('✅ Vibration initialized successfully');
        return success;
    } catch (e) {
        console.error('❌ Failed to initialize vibration:', e);
        return false;
    }
}

// Force initialization on ANY user interaction to unlock vibration API
let initAttempted = false;
function attemptVibrationInit() {
    if (!initAttempted && vibrationSupported) {
        initAttempted = true;
        console.log('🎯 Attempting vibration initialization on user interaction...');

        // Try a real vibration to unlock the API
        try {
            const success = navigator.vibrate(50);
            vibrationInitialized = true;
            if (success) {
                console.log('✅ Vibration unlocked successfully!');
            } else {
                console.warn('⚠️ Vibration unlock returned false');
            }
        } catch (e) {
            console.error('❌ Failed to unlock vibration:', e);
        }
    }
}

// Add listeners to initialize vibration on first touch/click/pointer
document.addEventListener('touchstart', attemptVibrationInit, { once: true, passive: true });
document.addEventListener('click', attemptVibrationInit, { once: true, passive: true });
document.addEventListener('pointerdown', attemptVibrationInit, { once: true, passive: true });

function vibrate(duration = 50) {
    if (!vibrationEnabled) {
        console.log('🔇 Vibration is disabled by user');
        return;
    }

    if (!vibrationSupported) {
        console.warn('❌ Vibration not supported');
        return;
    }

    // Initialize on first call
    if (!vibrationInitialized) {
        initializeVibration();
    }

    try {
        // Ensure minimum duration for mobile devices (many ignore < 50ms)
        const effectiveDuration = Math.max(duration, 50);

        // Try different vendor prefixes
        let success = false;
        if (navigator.vibrate) {
            success = navigator.vibrate(effectiveDuration);
        } else if (navigator.mozVibrate) {
            success = navigator.mozVibrate(effectiveDuration);
        } else if (navigator.webkitVibrate) {
            success = navigator.webkitVibrate(effectiveDuration);
        }

        if (!success) {
            console.warn('⚠️ Vibration call returned false - may be blocked by browser policy');
        } else {
            console.log(`📳 Vibration triggered: ${effectiveDuration}ms`);
        }
    } catch (e) {
        console.error('❌ Vibration failed:', e);
    }
}

// Update vibration status indicator
function updateVibrationStatus() {
    const statusEl = document.getElementById('vibration-status');
    if (!statusEl) return;

    if (vibrationSupported) {
        statusEl.innerHTML = '✅ Vibração suportada neste dispositivo';
        statusEl.style.background = '#10b981';
        statusEl.style.color = '#ffffff';
    } else {
        statusEl.innerHTML = '❌ Vibração não suportada (iOS ou navegador incompatível)';
        statusEl.style.background = '#ef4444';
        statusEl.style.color = '#ffffff';
    }
}

// Check support on page load
checkVibrationSupport();

// Update status when page loads and when settings panel opens
document.addEventListener('DOMContentLoaded', () => {
    updateVibrationStatus();
});

// Joystick Class
class VirtualJoystick {
    constructor(containerId, axisCodeX, axisCodeY, buttonCode) {
        this.container = document.getElementById(containerId);
        this.base = this.container.querySelector('.v-joystick-base');
        this.stick = this.container.querySelector('.v-joystick-stick');
        this.axisX = axisCodeX;
        this.axisY = axisCodeY;
        this.buttonCode = buttonCode;

        this.maxRadius = 50; // Fallback
        this.active = false;
        this.touchId = null;

        this.init();
    }

    init() {
        // Listen on container for better touch area
        this.container.addEventListener('pointerdown', e => this.onStart(e));
        window.addEventListener('pointermove', e => this.onMove(e));
        window.addEventListener('pointerup', e => this.onEnd(e));
        window.addEventListener('pointercancel', e => this.onEnd(e));
    }

    onStart(e) {
        if (document.body.classList.contains('edit-mode')) return;

        this.active = true;
        this.touchId = e.pointerId;

        this.container.setPointerCapture(e.pointerId);
        this.stick.style.transition = 'none'; // Instant response

        vibrate(50); // Vibration for joystick press
        sendInput('BUTTON', this.buttonCode, 1);
        this.onMove(e); // Initial move
    }

    onMove(e) {
        if (!this.active || e.pointerId !== this.touchId) return;

        const rect = this.base.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        const dx = e.clientX - centerX;
        const dy = e.clientY - centerY;

        const distance = Math.sqrt(dx * dx + dy * dy);
        const currentMaxRadius = rect.width / 2;
        const radius = Math.min(distance, currentMaxRadius);
        const angle = Math.atan2(dy, dx);

        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;

        this.stick.style.transform = `translate(${x}px, ${y}px)`;

        // Calculate axis values relative to VISUAL radius for perfect precision
        const valX = Math.round((x / currentMaxRadius) * 32767);
        const valY = Math.round((y / currentMaxRadius) * 32767);

        sendInput('AXIS', this.axisX, valX);
        sendInput('AXIS', this.axisY, valY);
    }

    onEnd(e) {
        if (!this.active || e.pointerId !== this.touchId) return;

        this.active = false;
        this.stick.style.transition = 'transform 0.1s ease-out'; // Smooth snap back
        this.stick.style.transform = 'translate(0, 0)';

        sendInput('AXIS', this.axisX, 0);
        sendInput('AXIS', this.axisY, 0);
        sendInput('BUTTON', this.buttonCode, 0);
    }
}

// Initializing Joysticks
const leftJoystick = new VirtualJoystick('joystick-left', 'LEFT_X', 'LEFT_Y', 'L3');
const rightJoystick = new VirtualJoystick('joystick-right', 'RIGHT_X', 'RIGHT_Y', 'R3');

// Input Events
document.querySelectorAll('button[data-key]').forEach(btn => {
    const key = btn.dataset.key;

    const handlePress = (e) => {
        if (document.body.classList.contains('edit-mode')) return;

        e.preventDefault();
        btn.classList.add('active');
        vibrate(50); // Vibration for buttons - increased for better mobile feedback
        sendInput('BUTTON', key, 1);
    };

    const handleRelease = (e) => {
        if (document.body.classList.contains('edit-mode')) return;

        e.preventDefault();
        btn.classList.remove('active');
        sendInput('BUTTON', key, 0);
    };

    btn.addEventListener('pointerdown', handlePress);
    btn.addEventListener('pointerup', handleRelease);
    btn.addEventListener('pointerleave', handleRelease);
});

// Stats variables
let lastBytesReceived = 0;
let lastTimestamp = 0;
function resetStats() {
    lastBytesReceived = 0;
    lastTimestamp = 0;
    statFPS.innerText = 'FPS: --';
    statBitrate.innerText = 'Bitrate: --';
    statVideoLatency.innerText = 'Video Latency: -- ms';
    statAudioLatency.innerText = 'Audio Latency: -- ms';
}

function startStatsInterval() {
    let audioStatsCounter = 0;
    setInterval(async () => {
        if (!pc) return;
        const stats = await pc.getStats();
        let currentBitrate = 0;
        let currentFPS = 0;
        let currentLatency = 0;
        let audioDebugInfo = {};

        stats.forEach(report => {
            if (report.type === 'inbound-rtp' && report.kind === 'video') {
                if (report.framesPerSecond) {
                    currentFPS = Math.round(report.framesPerSecond);
                    statFPS.innerText = `FPS: ${currentFPS}`;
                }

                if (report.bytesReceived) {
                    const now = Date.now();
                    const bytes = report.bytesReceived;
                    if (lastTimestamp > 0) {
                        const deltaS = (now - lastTimestamp) / 1000;
                        const deltaB = bytes - lastBytesReceived;
                        currentBitrate = (deltaB * 8) / (deltaS * 1000 * 1000); // Mbps
                        statBitrate.innerText = `Bitrate: ${currentBitrate.toFixed(1)} Mbps`;
                    }
                    lastBytesReceived = bytes;
                    lastTimestamp = now;
                }
            }
            if (report.type === 'inbound-rtp' && report.kind === 'audio') {
                const bytes = report.bytesReceived || 0;
                const packets = report.packetsReceived || 0;
                const packetsLost = report.packetsLost || 0;
                const jitter = report.jitter || 0;

                // Audio Latency Calculation (Jitter Buffer Delay)
                let audioLatencyMs = 0;
                if (report.jitterBufferDelay && report.jitterBufferEmittedCount) {
                    audioLatencyMs = (report.jitterBufferDelay / report.jitterBufferEmittedCount) * 1000;
                }
                statAudioLatency.innerText = `Audio Latency: ${audioLatencyMs.toFixed(0)}ms`;

                audioDebugInfo = {
                    bytes,
                    packets,
                    packetsLost,
                    jitter,
                    timestamp: report.timestamp
                };

                const kb = (bytes / 1024).toFixed(1);
                statAudioBitrate.innerText = `Audio: ${kb} KB, ${packets} pkts`;
                statAudioBitrate.style.color = bytes > 0 ? '#00ff00' : '#ff0000';

                // Log detailed audio stats every 5 seconds
                audioStatsCounter++;
                if (audioStatsCounter % 5 === 0) {
                    console.log('🔊 AUDIO STATS UPDATE:');
                    console.log('  - Audio Latency (Buffer):', audioLatencyMs.toFixed(0) + 'ms');
                    console.log('  - Bytes Received:', bytes);
                    console.log('  - Packets Received:', packets);
                    console.log('  - Packets Lost:', packetsLost);
                    console.log('  - Jitter:', jitter);
                    console.log('  - Loss Rate:', packets > 0 ? ((packetsLost / packets) * 100).toFixed(2) + '%' : 'N/A');

                    // Check audio track state
                    const audioTracks = video.srcObject ? video.srcObject.getAudioTracks() : [];
                    if (audioTracks.length > 0) {
                        audioTracks.forEach((track, idx) => {
                            console.log(`  - Audio Track ${idx}:`, {
                                enabled: track.enabled,
                                muted: track.muted,
                                readyState: track.readyState,
                                label: track.label
                            });
                        });
                    } else {
                        console.warn('  ⚠️ NO AUDIO TRACKS in srcObject!');
                    }

                    // Check video element audio state
                    console.log('  - Video Element:', {
                        muted: video.muted,
                        volume: video.volume,
                        paused: video.paused
                    });

                    if (bytes === 0) {
                        console.error('  ❌ AUDIO BYTES = 0! No audio data being received!');
                    }
                }
            }
            if (report.type === 'candidate-pair' && report.state === 'succeeded') {
                currentLatency = Math.round(report.currentRoundTripTime * 1000);
                statVideoLatency.innerText = `Video Latency: ${currentLatency}ms`;
            }
        });

        // Send stats to server via Data Channel
        if (dc && dc.readyState === 'open' && currentFPS > 0) {
            dc.send(JSON.stringify({
                type: 'STATS',
                fps: currentFPS,
                bitrate: currentBitrate.toFixed(2),
                latency: currentLatency,
                audio: audioDebugInfo
            }));
        }
    }, 1000);
}

// ========================
// GAME LIBRARY
// ========================

const libraryOverlay = document.getElementById('library-overlay');
const gamesGrid = document.getElementById('games-grid');
const searchInput = document.getElementById('search-input');
const filterBtns = document.querySelectorAll('.filter-btn');

let allGames = [];
let currentFilter = 'all';
let currentSearch = '';

// Load games from server
async function loadGames() {
    console.log("Library: Starting loadGames...");
    const grid = document.getElementById('games-grid');

    try {
        console.log("Library: Fetching /api/games...");
        const response = await fetch('/api/games');
        console.log("Library: Response status:", response.status);

        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status}`);
        }

        const data = await response.json();
        console.log("Library: Received data:", data);

        allGames = data.games || [];
        console.log("Library: Game count:", allGames.length);

        if (allGames.length === 0) {
            console.log("Library: No games found, showing message.");
            showNoGamesMessage();
        } else {
            console.log("Library: Rendering games...");
            renderGames();
        }
    } catch (error) {
        console.error('Library: Error loading games:', error);
        if (grid) {
            grid.innerHTML = `
                <div class="no-games-message">
                    <h2>❌ Erro ao Carregar Jogos</h2>
                    <p>${error.message}</p>
                    <button onclick="loadGames()" class="filter-btn" style="margin-top:10px">Tentar Novamente</button>
                </div>
            `;
        }
    }
}

function showNoGamesMessage() {
    gamesGrid.innerHTML = `
        <div class="no-games-message">
            <h2>🎮 Nenhum Jogo Encontrado</h2>
            <p>Certifique-se de ter jogos instalados via Steam ou Epic Games</p>
        </div>
    `;
}

function renderGames() {
    // Filter games
    let filteredGames = allGames;

    // Platform filter
    if (currentFilter !== 'all') {
        filteredGames = filteredGames.filter(game => game.platform === currentFilter);
    }

    // Search filter
    if (currentSearch) {
        filteredGames = filteredGames.filter(game =>
            game.name.toLowerCase().includes(currentSearch.toLowerCase())
        );
    }

    if (filteredGames.length === 0) {
        gamesGrid.innerHTML = `
            <div class="no-games-message">
                <h2>🔍 Nenhum Jogo Encontrado</h2>
                <p>Tente ajustar sua busca ou filtro</p>
            </div>
        `;
        return;
    }

    // Render game cards
    gamesGrid.innerHTML = filteredGames.map(game => {
        const icon = getGameIcon(game);
        const platformClass = game.platform === 'Epic Games' ? 'epic' : '';

        return `
            <div class="game-card" data-game-id="${game.id}">
                <div class="game-card-image">
                    <div class="game-icon">${icon}</div>
                </div>
                <div class="game-card-content">
                    <h3 class="game-card-title">${escapeHtml(game.name)}</h3>
                    <span class="game-card-platform ${platformClass}">${game.platform}</span>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers
    document.querySelectorAll('.game-card').forEach(card => {
        card.addEventListener('click', () => {
            const gameId = card.dataset.gameId;
            launchGameAndStream(gameId);
        });
    });
}

function getGameIcon(game) {
    // Steam Big Picture special icon
    if (game.id === 'steam_bigpicture') {
        return '🎮';
    }

    // Platform icons
    if (game.platform === 'Steam') {
        return '🎮';
    } else if (game.platform === 'Epic Games') {
        return '🎯';
    }

    return '🎮';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function launchGameAndStream(gameId) {
    try {
        // Hide library and show stream status
        libraryOverlay.classList.add('hidden');
        statusOverlay.classList.remove('hidden');
        updateStatus('Iniciando jogo...', true);

        // Launch game
        const launchResponse = await fetch('/api/launch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: gameId })
        });

        if (!launchResponse.ok) {
            throw new Error('Falha ao lançar o jogo');
        }

        // Wait a moment for game to start
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Start streaming
        await startStream();
        statusOverlay.classList.add('hidden');

    } catch (error) {
        console.error('Error launching game:', error);
        updateStatus('Erro ao iniciar jogo: ' + error.message, false);

        // Show library again after 3 seconds
        setTimeout(() => {
            statusOverlay.classList.add('hidden');
            libraryOverlay.classList.remove('hidden');
        }, 3000);
    }
}

// Search functionality
searchInput.addEventListener('input', (e) => {
    currentSearch = e.target.value;
    renderGames();
});

// Filter functionality
filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.platform;
        renderGames();
    });
});

// Load games on page load
loadGames();

// Keep the manual start button for testing
startBtn.addEventListener('click', startStream);

// ========================
// CONTROL CUSTOMIZATION
// ========================

class ControlCustomizer {
    constructor() {
        this.editMode = false;
        this.systemButtonsMode = false;
        this.scale = 1.0;
        this.positions = {};

        this.settingsBtn = document.getElementById('settings-btn');
        this.customizeOverlay = document.getElementById('customize-overlay');
        this.closeCustomizeBtn = document.getElementById('close-customize');
        this.editModeToggle = document.getElementById('edit-mode-toggle');
        this.moveSystemToggle = document.getElementById('move-system-toggle');
        this.vibrationToggle = document.getElementById('vibration-toggle');
        this.sizeButtons = document.querySelectorAll('.size-btn');
        this.fsrToggle = document.getElementById('fsr-toggle');
        this.resetBtn = document.getElementById('reset-controls');
        this.gamepadContainer = document.querySelector('.gamepad-overlay');

        this.draggables = [
            // Left Side - Individual
            { id: 'joy-l', element: document.getElementById('joystick-left') },
            { id: 'dpad-up', element: document.querySelector('.d-btn.up') },
            { id: 'dpad-down', element: document.querySelector('.d-btn.down') },
            { id: 'dpad-left', element: document.querySelector('.d-btn.left') },
            { id: 'dpad-right', element: document.querySelector('.d-btn.right') },

            // Right Side - Individual
            { id: 'joy-r', element: document.getElementById('joystick-right') },
            { id: 'btn-a', element: document.querySelector('.a-btn.a') },
            { id: 'btn-b', element: document.querySelector('.a-btn.b') },
            { id: 'btn-x', element: document.querySelector('.a-btn.x') },
            { id: 'btn-y', element: document.querySelector('.a-btn.y') },

            // Top - Shoulders & Menu
            { id: 'sh-lt', element: document.querySelector('.control-btn[data-key="LT"]') },
            { id: 'sh-lb', element: document.querySelector('.control-btn[data-key="LB"]') },
            { id: 'sh-rt', element: document.querySelector('.control-btn[data-key="RT"]') },
            { id: 'sh-rb', element: document.querySelector('.control-btn[data-key="RB"]') },
            { id: 'menu-sel', element: document.querySelector('.control-btn[data-key="SELECT"]') },
            { id: 'menu-sta', element: document.querySelector('.control-btn[data-key="START"]') },
            { id: 'menu-hom', element: document.querySelector('.home-btn') },

            // System Buttons
            { id: 'btn-fullscreen', element: document.getElementById('fullscreen-btn') },
            { id: 'btn-quality', element: document.getElementById('quality-btn') },
            { id: 'btn-settings', element: document.getElementById('settings-btn') }
        ];

        this.init();
    }

    init() {
        // Load saved settings
        this.loadSettings();

        // Event listeners
        this.settingsBtn.addEventListener('click', () => this.openPanel());
        this.closeCustomizeBtn.addEventListener('click', () => this.closePanel());
        this.editModeToggle.addEventListener('change', (e) => this.toggleEditMode(e.target.checked));
        this.moveSystemToggle.addEventListener('change', (e) => this.toggleSystemButtonsMode(e.target.checked));
        this.vibrationToggle.addEventListener('change', (e) => {
            vibrationEnabled = e.target.checked;
            this.saveSettings();
        });

        this.fsrToggle.addEventListener('change', (e) => {
            if (e.target.checked) fsrRenderer.enable();
            else fsrRenderer.disable();
            this.saveSettings();
        });

        document.getElementById('test-vibration-btn').addEventListener('click', () => {
            console.log('🧪 Testing vibration...');

            // Update status indicator
            updateVibrationStatus();

            if (!vibrationSupported) {
                alert('❌ Vibração não é suportada neste dispositivo/navegador.\n\n' +
                    'Dispositivos iOS (iPhone/iPad) não suportam a Vibration API.\n' +
                    'Use um dispositivo Android com Chrome, Firefox ou Edge.');
                return;
            }

            // Try a longer, more noticeable vibration pattern
            // Pattern: vibrate 200ms, pause 100ms, vibrate 200ms
            if (navigator.vibrate) {
                const success = navigator.vibrate([200, 100, 200]);
                if (success) {
                    console.log('✅ Test vibration triggered successfully');
                } else {
                    console.warn('⚠️ Test vibration failed - may be blocked');
                    alert('⚠️ Vibração bloqueada pelo navegador.\n\n' +
                        'Certifique-se de que:\n' +
                        '1. Você está usando HTTPS ou localhost\n' +
                        '2. Permissões do navegador estão habilitadas\n' +
                        '3. Modo silencioso está desligado');
                }
            }
        });

        this.resetBtn.addEventListener('click', () => this.resetControls());

        this.sizeButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const size = parseFloat(e.target.dataset.size);
                this.setScale(size);
            });
        });

        // Apply saved settings
        this.applyScale();
        this.applyPositions();
    }

    openPanel() {
        this.customizeOverlay.classList.remove('hidden');
    }

    closePanel() {
        // Save settings before closing
        this.saveSettings();
        this.customizeOverlay.classList.add('hidden');
    }

    toggleEditMode(enabled) {
        this.editMode = enabled;
        this.updateDragging();
    }

    toggleSystemButtonsMode(enabled) {
        this.systemButtonsMode = enabled;
        this.updateDragging();
    }

    updateDragging() {
        const isEditMode = this.editMode || this.systemButtonsMode;

        if (isEditMode) {
            document.body.classList.add('edit-mode');
            this.enableDragging();
            this.showEditIndicator();
        } else {
            document.body.classList.remove('edit-mode');
            this.disableDragging();
            this.hideEditIndicator();
            this.saveSettings();
        }
    }

    enableDragging() {
        this.draggables.forEach(({ id, element }) => {
            if (!element) return;

            // Determine if this element should be draggable based on mode
            const isSystemButton = ['btn-fullscreen', 'btn-quality', 'btn-settings'].includes(id);
            const canDrag = (isSystemButton && this.systemButtonsMode) || (!isSystemButton && this.editMode);

            if (!canDrag) {
                element.classList.remove('draggable', 'dragging');
                if (element._dragHandlers) {
                    const { onPointerDown } = element._dragHandlers;
                    element.removeEventListener('pointerdown', onPointerDown);
                    delete element._dragHandlers;
                }
                return;
            }

            if (element._dragHandlers) return; // Already setup for this element

            // Convert to absolute position ONLY if we have a saved position for this element
            // This prevents elements from disappearing when mode is disabled
            const style = window.getComputedStyle(element);
            if (this.positions[id] && style.position !== 'absolute') {
                // Element has a saved position, apply it
                element.style.position = 'absolute';
                element.style.left = this.positions[id].left || '0px';
                element.style.top = this.positions[id].top || '0px';
                element.style.margin = '0';
                element.style.transform = `scale(${this.scale})`;
                element.style.right = 'auto';
                element.style.bottom = 'auto';
            } else if (!this.positions[id] && style.position !== 'absolute') {
                // No saved position - convert to absolute at current visual position
                // This will be saved when user drags it
                const rect = element.getBoundingClientRect();
                const containerRect = this.gamepadContainer.getBoundingClientRect();
                const left = rect.left - containerRect.left;
                const top = rect.top - containerRect.top;

                element.style.position = 'absolute';
                element.style.left = `${left}px`;
                element.style.top = `${top}px`;
                element.style.margin = '0';
                element.style.transform = `scale(${this.scale})`;
                element.style.right = 'auto';
                element.style.bottom = 'auto';
            }

            element.classList.add('draggable');

            let isDragging = false;
            let startX, startY, initialLeft, initialTop;

            // Offset from the top-left corner of the element to the pointer
            let pointerOffsetX, pointerOffsetY;

            const onPointerDown = (e) => {
                // Only left click or touch
                if (e.button !== 0 && e.pointerType === 'mouse') return;

                isDragging = true;
                element.classList.add('dragging');
                element.setPointerCapture(e.pointerId); // Crucial for reliable tracking

                const rect = element.getBoundingClientRect();
                const parentRect = this.gamepadContainer.getBoundingClientRect();

                // Calculate where we clicked relative to the element's top-left
                pointerOffsetX = e.clientX - rect.left;
                pointerOffsetY = e.clientY - rect.top;

                e.preventDefault();
                e.stopPropagation();
            };

            const onPointerMove = (e) => {
                if (!isDragging) return;

                const parentRect = this.gamepadContainer.getBoundingClientRect();

                // Calculate new top-left position based on pointer position and initial offset
                // This makes the element stick exactly to the finger/cursor
                let newLeft = e.clientX - parentRect.left - pointerOffsetX;
                let newTop = e.clientY - parentRect.top - pointerOffsetY;

                // Simple bounds checking to keep inside viewport or allow free movement
                // Letting it be free feels better usually, but lets ensure it's not totally lost.

                element.style.left = `${newLeft}px`;
                element.style.top = `${newTop}px`;
            };

            const onPointerUp = (e) => {
                if (isDragging) {
                    isDragging = false;
                    element.classList.remove('dragging');
                    element.releasePointerCapture(e.pointerId);

                    // Save position
                    this.positions[id] = {
                        left: element.style.left,
                        top: element.style.top,
                        position: 'absolute'
                    };
                    this.saveSettings();
                }
            };

            element.addEventListener('pointerdown', onPointerDown);
            element.addEventListener('pointermove', onPointerMove);
            element.addEventListener('pointerup', onPointerUp);
            element.addEventListener('pointercancel', onPointerUp);

            element._dragHandlers = { onPointerDown, onPointerMove, onPointerUp };
        });
    }

    disableDragging() {
        this.draggables.forEach(({ id, element }) => {
            if (!element || !element._dragHandlers) return;

            element.classList.remove('draggable', 'dragging');

            const { onPointerDown, onPointerMove, onPointerUp } = element._dragHandlers;
            element.removeEventListener('pointerdown', onPointerDown);
            window.removeEventListener('pointermove', onPointerMove);
            window.removeEventListener('pointerup', onPointerUp);

            delete element._dragHandlers;

            // CRITICAL FIX: If element doesn't have a saved position, restore its CSS layout
            // This prevents elements from disappearing when mode is disabled
            if (!this.positions[id]) {
                element.style.position = '';
                element.style.left = '';
                element.style.top = '';
                element.style.margin = '';
                element.style.right = '';
                element.style.bottom = '';
                // Keep the scale transform
                element.style.transform = `scale(${this.scale})`;
            }
        });
    }

    setScale(scale) {
        this.scale = scale;

        // Update active button
        this.sizeButtons.forEach(btn => {
            if (parseFloat(btn.dataset.size) === scale) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        this.applyScale();
        this.saveSettings();
    }

    applyScale() {
        this.draggables.forEach(({ element }) => {
            if (element) {
                element.style.transform = `scale(${this.scale})`;
            }
        });
    }

    applyPositions() {
        this.draggables.forEach(({ id, element }) => {
            if (element && this.positions[id]) {
                // If we have a saved position, it means we used absolute positioning
                element.style.position = 'absolute';
                element.style.left = this.positions[id].left || '0px';
                element.style.top = this.positions[id].top || '0px';
                element.style.margin = '0'; // Clear margins to ensure accurate positioning
            }
        });
    }

    resetControls() {
        if (!confirm('Deseja realmente restaurar os controles para a posição padrão?')) {
            return;
        }

        this.scale = 1.0;
        this.positions = {};

        // Reset scale buttons
        this.sizeButtons.forEach(btn => {
            if (parseFloat(btn.dataset.size) === 1.0) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Reset all elements
        this.draggables.forEach(({ element }) => {
            if (element) {
                element.style.transform = 'scale(1.0)';
                // Reset positioning styles to let CSS take over (Flexbox layout)
                element.style.position = '';
                element.style.left = '';
                element.style.top = '';
                element.style.margin = '';
                element.style.right = '';
                element.style.bottom = '';
            }
        });

        this.saveSettings();
    }

    saveSettings() {
        const settings = {
            scale: this.scale,
            positions: this.positions,
            vibration: vibrationEnabled,
            fsr: this.fsrToggle ? this.fsrToggle.checked : false
        };

        localStorage.setItem('controlSettings', JSON.stringify(settings));
        console.log('Control settings saved:', settings);
    }

    loadSettings() {
        try {
            const saved = localStorage.getItem('controlSettings');
            if (saved) {
                const settings = JSON.parse(saved);
                this.scale = settings.scale || 1.0;
                this.positions = settings.positions || {};

                if (this.vibrationToggle) {
                    this.vibrationToggle.checked = settings.vibration !== false;
                    vibrationEnabled = this.vibrationToggle.checked;
                }

                if (this.fsrToggle) {
                    this.fsrToggle.checked = settings.fsr === true;
                    if (this.fsrToggle.checked) setTimeout(() => fsrRenderer.enable(), 1000);
                }

                // Update size buttons
                this.sizeButtons.forEach(btn => {
                    if (parseFloat(btn.dataset.size) === this.scale) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });

                console.log('Control settings loaded:', settings);
            }
        } catch (e) {
            console.error('Failed to load control settings:', e);
        }
    }

    showEditIndicator() {
        if (!this.indicator) {
            this.indicator = document.createElement('div');
            this.indicator.className = 'edit-mode-indicator';
            document.body.appendChild(this.indicator);
        }

        // Atualizar mensagem baseado no modo ativo
        let message = '';
        if (this.editMode && this.systemButtonsMode) {
            message = '✏️ Modo de Edição - Arraste todos os controles';
        } else if (this.editMode) {
            message = '✏️ Modo de Edição - Arraste os controles de jogo';
        } else if (this.systemButtonsMode) {
            message = '✏️ Modo de Edição - Arraste os botões de sistema (Tela Cheia, Qualidade)';
        }

        this.indicator.textContent = message;
    }

    hideEditIndicator() {
        if (this.indicator) {
            this.indicator.remove();
            this.indicator = null;
        }
    }
}

// Initialize control customizer
const controlCustomizer = new ControlCustomizer();

// ========================
// FULLSCREEN LOGIC
// ========================
const fullscreenBtn = document.getElementById('fullscreen-btn');

if (fullscreenBtn) {
    fullscreenBtn.addEventListener('click', toggleFullscreen);
}

// Double-tap for mobile fullscreen
let lastTap = 0;
video.addEventListener('touchstart', (e) => {
    const currentTime = new Date().getTime();
    const tapLength = currentTime - lastTap;
    if (tapLength < 300 && tapLength > 0) {
        e.preventDefault();
        toggleFullscreen();
    }
    lastTap = currentTime;
});

function toggleFullscreen() {
    if (!document.fullscreenElement &&    // alternative standard method
        !document.mozFullScreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {  // current working methods
        if (document.documentElement.requestFullscreen) {
            document.documentElement.requestFullscreen();
        } else if (document.documentElement.msRequestFullscreen) {
            document.documentElement.msRequestFullscreen();
        } else if (document.documentElement.mozRequestFullScreen) {
            document.documentElement.mozRequestFullScreen();
        } else if (document.documentElement.webkitRequestFullscreen) {
            document.documentElement.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT);
        }
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        } else if (document.mozCancelFullScreen) {
            document.mozCancelFullScreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        }
    }
}

// ========================
// STATS PANEL CUSTOMIZATION
// ========================

class StatsCustomizer {
    constructor() {
        this.panel = document.getElementById('stats-panel');
        this.toggle = document.getElementById('move-stats-toggle');
        this.isDragging = false;
        this.offset = { x: 0, y: 0 };

        this.init();
    }

    init() {
        if (!this.panel || !this.toggle) return;

        // Load saved position
        const saved = localStorage.getItem('statsPosition');
        if (saved) {
            try {
                const pos = JSON.parse(saved);
                this.applyPosition(pos.left, pos.top);
            } catch (e) {
                console.error('Error loading stats position', e);
            }
        }

        // Toggle Listener
        this.toggle.addEventListener('change', (e) => {
            this.setEditMode(e.target.checked);
        });

        // Drag Listeners
        this.panel.addEventListener('pointerdown', this.onDragStart.bind(this));
        window.addEventListener('pointermove', this.onDragMove.bind(this));
        window.addEventListener('pointerup', this.onDragEnd.bind(this));
        window.addEventListener('pointercancel', this.onDragEnd.bind(this));
    }

    applyPosition(left, top) {
        // Ensure within bounds
        const maxX = window.innerWidth - this.panel.offsetWidth;
        const maxY = window.innerHeight - this.panel.offsetHeight;

        // Simple clamp
        const safeLeft = Math.max(0, Math.min(left, window.innerWidth - 50));
        const safeTop = Math.max(0, Math.min(top, window.innerHeight - 20));

        this.panel.style.position = 'fixed';
        this.panel.style.left = `${safeLeft}px`;
        this.panel.style.top = `${safeTop}px`;
        this.panel.style.right = 'auto';
        this.panel.style.bottom = 'auto';
        this.panel.style.transform = 'none'; // reset any flex alignment if needed
    }

    setEditMode(enabled) {
        if (enabled) {
            this.panel.classList.add('movable');
            // If it wasn't fixed yet, make it fixed at current visual position
            const style = window.getComputedStyle(this.panel);
            if (this.panel.style.position !== 'fixed') {
                const rect = this.panel.getBoundingClientRect();
                this.applyPosition(rect.left, rect.top);
            }
        } else {
            this.panel.classList.remove('movable');
            this.savePosition();
        }
    }

    onDragStart(e) {
        if (!this.toggle.checked) return;

        this.isDragging = true;
        this.panel.setPointerCapture(e.pointerId);

        const rect = this.panel.getBoundingClientRect();
        this.offset = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }

    onDragMove(e) {
        if (!this.isDragging) return;
        e.preventDefault();

        const x = e.clientX - this.offset.x;
        const y = e.clientY - this.offset.y;

        this.applyPosition(x, y);
    }

    onDragEnd(e) {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.savePosition();
    }

    savePosition() {
        const rect = this.panel.getBoundingClientRect();
        const pos = { left: rect.left, top: rect.top };
        localStorage.setItem('statsPosition', JSON.stringify(pos));
    }
}

// Initialize Stats Customizer
const statsCustomizer = new StatsCustomizer();

// ========================
// AUDIO & DISPLAY SETTINGS
// ========================

const showStatsToggle = document.getElementById('show-stats-toggle');
const audioMuteToggle = document.getElementById('audio-mute-toggle');
const volumeSlider = document.getElementById('volume-slider');
const volumeValue = document.getElementById('volume-value');
const statsPanel = document.getElementById('stats-panel');

// Stats Display Toggle
if (showStatsToggle && statsPanel) {
    showStatsToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            statsPanel.classList.remove('hidden');
        } else {
            statsPanel.classList.add('hidden');
        }
    });
}

// Audio Controls
if (audioMuteToggle && video) {
    audioMuteToggle.addEventListener('change', (e) => {
        // Toggle: Checked = Audio ON (muted = false)
        //          Unchecked = Audio OFF (muted = true)
        const isAudioEnabled = e.target.checked;
        video.muted = !isAudioEnabled;
        console.log(`Audio Setting Change: Enabled=${isAudioEnabled}, Video.muted=${video.muted}`);

        // Visual feedback if needed
    });
}

if (volumeSlider && video) {
    volumeSlider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        video.volume = val;

        // Update text
        if (volumeValue) {
            volumeValue.innerText = Math.round(val * 100) + '%';
        }

        // Ensure not muted if volume is moved
        if (val > 0 && !audioMuteToggle.checked) {
            // Optional: Auto-unmute if user drags volume? 
            // Better to respect the main toggle, but common UX is volume drag unmutes.
            // Let's just update the toggle if they drag up from 0?
            // For now, simple direct control.
        }
    });
}

// ========================
// RECORDING FUNCTIONALITY
// ========================

const recordBtn = document.getElementById('record-btn');
const recIndicator = document.getElementById('recording-indicator');
const recTimerDisplay = document.getElementById('rec-timer');

let mediaRecorder;
let recordedChunks = [];
let isRecording = false;
let recStartTime;
let recInterval;

if (recordBtn) {
    recordBtn.addEventListener('click', toggleRecording);
}

function toggleRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

async function startRecording() {
    if (!video.srcObject) {
        alert('Nenhum stream ativo para gravar!');
        return;
    }

    const stream = video.srcObject;
    // Check if we have active tracks
    if (stream.getTracks().length === 0) {
        console.error('No tracks to record');
        return;
    }

    try {
        // Try precise mime types, fallback to default
        const options = { mimeType: 'video/webm;codecs=vp9,opus' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            console.warn('VP9 not supported, trying default WebM');
            delete options.mimeType; // Let browser choose
        }

        mediaRecorder = new MediaRecorder(stream, options);

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = saveRecording;

        mediaRecorder.start();
        isRecording = true;

        // UI Updates
        recordBtn.innerHTML = '<span class="btn-text">Parar Gravação</span>';
        recordBtn.style.background = '#334155'; // Darker/Neutral
        recIndicator.classList.remove('hidden');
        recIndicator.style.display = 'flex'; // Ensure flex override

        // Timer
        recStartTime = Date.now();
        recTimerDisplay.innerText = '00:00';
        recInterval = setInterval(updateRecTimer, 1000);

        console.log('Recording started');

    } catch (e) {
        console.error('Failed to start recording:', e);
        alert('Erro ao iniciar gravação: ' + e.message);
    }
}

function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') return;

    mediaRecorder.stop();
    isRecording = false;

    // UI Updates
    recordBtn.innerHTML = '<span class="btn-text">Iniciar Gravação</span>';
    recordBtn.style.background = '#ef4444'; // Red back
    recIndicator.classList.add('hidden');
    recIndicator.style.display = 'none'; // Force hide

    clearInterval(recInterval);
    console.log('Recording stopped');
}

function saveRecording() {
    const blob = new Blob(recordedChunks, {
        type: 'video/webm'
    });

    // Create download link
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    document.body.appendChild(a);
    a.style = 'display: none';
    a.href = url;

    const date = new Date();
    const timestamp = `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}_${date.getHours()}-${date.getMinutes()}-${date.getSeconds()}`;
    a.download = `neostream_recording_${timestamp}.webm`;

    a.click();

    // Cleanup
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    recordedChunks = [];
}

function updateRecTimer() {
    const diff = Math.floor((Date.now() - recStartTime) / 1000);
    const min = Math.floor(diff / 60);
    const sec = diff % 60;
    recTimerDisplay.innerText = `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
}

// Mouse and Keyboard support removed

// Quality Toggle
let currentQuality = '1080p';
const qualityBtn = document.getElementById('quality-btn');
const qualityText = document.getElementById('quality-text');

if (qualityBtn) {
    qualityBtn.addEventListener('click', async () => {
        // Cycle quality: 720p -> 1080p -> 2k -> 4k
        const sequence = ['720p', '1080p', '2k', '4k'];
        const nextIndex = (sequence.indexOf(currentQuality) + 1) % sequence.length;
        currentQuality = sequence[nextIndex];

        qualityText.textContent = currentQuality.toUpperCase();
        qualityBtn.title = `Qualidade: ${currentQuality.toUpperCase()}`;

        // Send to server
        try {
            const response = await fetch('/api/quality', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ quality: currentQuality })
            });
            const data = await response.json();
            console.log('Quality changed:', data);

            // Show notification
            const notification = document.createElement('div');
            notification.style.cssText = 'position:fixed;top:70px;right:20px;background:#00ff88;color:#000;padding:12px 20px;border-radius:8px;font-weight:600;z-index:10000;';
            const displayNames = {
                '720p': 'Performance (720p)',
                '1080p': 'Equilibrado (1080p)',
                '2k': 'Qualidade (1440p)',
                '4k': 'Ultra (4K)'
            };
            notification.textContent = `Qualidade: ${displayNames[currentQuality]}`;
            document.body.appendChild(notification);
            setTimeout(() => notification.remove(), 2000);

            // Reconnect to apply new quality
            if (pc && pc.connectionState === 'connected') {
                updateStatus('Reconectando com nova qualidade...', true);
                setTimeout(() => {
                    pc.close();
                    startStream();
                }, 500);
            }
        } catch (error) {
            console.error('Failed to change quality:', error);
        }
    });
}

// ========================
// PHYSICAL GAMEPAD SUPPORT (IPEGA/XBOX/PS)
// ========================

class GamepadManager {
    constructor() {
        this.gamepads = {};
        this.activeGamepadIndex = null;
        this.prevButtons = [];
        this.prevAxes = [];
        this.pollingInterval = null;
        this.discoveryInterval = null;

        // Standard Mapping specific for generic Bluetooth controllers (like Ipega)
        this.btnMap = {
            0: 'A', 1: 'B', 2: 'X', 3: 'Y',
            4: 'LB', 5: 'RB',
            6: 'LT', 7: 'RT',
            8: 'SELECT', 9: 'START',
            10: 'L3', 11: 'R3',
            12: 'DPAD_UP', 13: 'DPAD_DOWN', 14: 'DPAD_LEFT', 15: 'DPAD_RIGHT',
            16: 'HOME'
        };

        this.axisMap = {
            0: 'LEFT_X', 1: 'LEFT_Y',
            2: 'RIGHT_X', 3: 'RIGHT_Y'
        };

        this.init();
    }

    init() {
        console.log("🎮 Initializing Gamepad Manager v2 (Polling Mode)...");

        // Event listeners (Standard)
        window.addEventListener("gamepadconnected", (e) => this.onConnect(e.gamepad));
        window.addEventListener("gamepaddisconnected", (e) => this.onDisconnect(e.gamepad));

        // AGGRESSIVE DISCOVERY POLLING
        // Chrome Android sometimes doesn't fire events if already connected.
        this.discoveryInterval = setInterval(() => {
            const gps = navigator.getGamepads ? navigator.getGamepads() : [];
            for (let i = 0; i < gps.length; i++) {
                if (gps[i] && this.activeGamepadIndex === null) {
                    this.onConnect(gps[i]);
                }
            }
        }, 1000); // Check every second for new devices
    }

    onConnect(gp) {
        if (!gp) return;
        console.log("🎮 Gamepad DETECTED:", gp.id);

        if (this.activeGamepadIndex !== null) return; // Already have one

        this.activeGamepadIndex = gp.index;
        this.startPolling();

        // Visual Feedback to User (Toast)
        const toast = document.createElement('div');
        toast.style.cssText = "position:fixed; top:20px; left:50%; transform:translateX(-50%); background:#22c55e; color:white; padding:15px; border-radius:10px; z-index:10000; font-weight:bold; box-shadow:0 5px 15px rgba(0,0,0,0.5); text-align:center; font-size:16px;";
        toast.innerText = `🎮 Controle Conectado!\n${gp.id.substring(0, 20)}...`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000); // Remove after 4s

        const statusMsg = document.getElementById('status-msg');
        if (statusMsg) statusMsg.innerText = `Controle: ${gp.id.substring(0, 15)}`;
    }

    onDisconnect(gp) {
        if (this.activeGamepadIndex === gp.index) {
            console.log("⚠️ Gamepad Lost");
            this.activeGamepadIndex = null;
            this.stopPolling();

            // Notify user
            const toast = document.createElement('div');
            toast.style.cssText = "position:fixed; top:20px; left:50%; transform:translateX(-50%); background:#ef4444; color:white; padding:15px; border-radius:10px; z-index:10000; font-weight:bold;";
            toast.innerText = "⚠️ Controle Desconectado";
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
    }

    startPolling() {
        if (this.pollingInterval) return;
        this.pollingInterval = setInterval(() => this.pollStatus(), 16);
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    pollStatus() {
        if (this.activeGamepadIndex === null) return;

        const navigatorGamepads = navigator.getGamepads ? navigator.getGamepads() : [];
        const gp = navigatorGamepads[this.activeGamepadIndex];

        if (!gp || !gp.connected) {
            this.onDisconnect({ index: this.activeGamepadIndex });
            return;
        }

        // --- BUTTONS ---
        gp.buttons.forEach((btn, index) => {
            const val = btn.pressed ? 1 : 0;
            if (this.prevButtons[index] !== val) {
                this.prevButtons[index] = val;

                const code = this.btnMap[index];
                if (code) {
                    sendInput('BUTTON', code, val);

                    // Visual Feedback
                    const virtualBtn = document.querySelector(`button[data-key="${code}"]`) ||
                        document.querySelector(`.control-btn[data-key="${code}"]`);
                    if (virtualBtn) {
                        if (val) virtualBtn.classList.add('active');
                        else virtualBtn.classList.remove('active');
                    }
                }
            }
        });

        // --- AXES ---
        gp.axes.forEach((val, index) => {
            if (Math.abs(val) < 0.15) val = 0;
            const intVal = Math.round(val * 32767);

            if (Math.abs((this.prevAxes[index] || 0) - intVal) > 500) {
                this.prevAxes[index] = intVal;
                const code = this.axisMap[index];
                if (code) sendInput('AXIS', code, intVal);
            }
        });
    }
}

// Initialize Gamepad Support
const gamepadManager = new GamepadManager();
