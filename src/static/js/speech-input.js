/**
 * Speech-to-text for chat inputs.
 * - Chrome / Edge: browser Web Speech API (streaming)
 * - Cursor / VS Code embedded browser: MediaRecorder + server Whisper API
 */
(function () {
    const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

    const STYLE_ID = "speech-input-styles";
    const FATAL_ERRORS = new Set([
        "not-allowed",
        "service-not-allowed",
        "audio-capture",
        "network",
    ]);

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            .speech-mic-btn {
                flex-shrink: 0;
                min-width: 44px;
                padding: 8px 12px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 18px;
                line-height: 1;
                background: #e9ecef;
                color: #333;
                transition: background 0.2s, box-shadow 0.2s;
            }
            .speech-mic-btn:hover:not(:disabled) {
                background: #dee2e6;
            }
            .speech-mic-btn:disabled {
                opacity: 0.45;
                cursor: not-allowed;
            }
            .speech-mic-btn.listening {
                background: #dc3545;
                color: #fff;
                box-shadow: 0 0 0 3px rgba(220, 53, 69, 0.35);
                animation: speech-mic-pulse 1.2s ease-in-out infinite;
            }
            .speech-mic-btn.busy {
                opacity: 0.7;
                cursor: wait;
            }
            .chat-input-area .speech-mic-btn {
                background: #16213e;
                color: #fff;
                border: 1px solid #2d3436;
            }
            .chat-input-area .speech-mic-btn:hover:not(:disabled) {
                background: #0f3460;
            }
            .chat-input-area .speech-mic-btn.listening {
                background: #dc3545;
                border-color: #dc3545;
            }
            @keyframes speech-mic-pulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.06); }
            }
        `;
        document.head.appendChild(style);
    }

    function isSpeechInputSupported() {
        return !!SpeechRecognition;
    }

    function isMediaRecorderSupported() {
        return !!(
            navigator.mediaDevices &&
            navigator.mediaDevices.getUserMedia &&
            window.MediaRecorder
        );
    }

    function isEmbeddedIdeBrowser() {
        const ua = navigator.userAgent || "";
        return /Cursor/i.test(ua) || /Visual Studio Code/i.test(ua);
    }

    function isMobileDevice() {
        return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent || "");
    }

    function resolveToken(options) {
        const getter = options.getToken || window.getAuthToken || window.getToken;
        return getter ? getter() : "";
    }

    function errorMessage(code) {
        const map = {
            "not-allowed": "麦克风权限被拒绝，请在浏览器设置中允许麦克风。",
            "service-not-allowed": "当前环境不允许使用语音识别。",
            "network": "语音识别需要网络连接，请检查网络后重试。",
            "audio-capture": "未找到可用麦克风，请检查设备连接。",
        };
        return map[code] || `语音识别错误：${code}`;
    }

    function notifyError(options, msg) {
        if (!msg) return;
        if (typeof options.onError === "function") options.onError(msg);
        else alert(msg);
    }

    async function uploadAndTranscribe(blob, options) {
        const token = resolveToken(options);
        if (!token) {
            throw new Error("请先登录后再使用语音输入");
        }
        const form = new FormData();
        form.append("file", blob, "speech.webm");
        const response = await fetch(
            `/api/speech/transcribe?token=${encodeURIComponent(token)}`,
            { method: "POST", body: form }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            const detail = data.message || data.detail || "语音识别失败";
            throw new Error(typeof detail === "string" ? detail : "语音识别失败");
        }
        return (data.text || "").trim();
    }

    function bindMicButton(input, button, options, initFn) {
        injectStyles();
        if (button.dataset.speechBound === "1") return;
        button.dataset.speechBound = "1";
        button.classList.add("speech-mic-btn");
        button.type = "button";
        button.textContent = "🎤";
        initFn(input, button, options);
    }

    function initMediaRecorderSpeechInput(input, button, options) {
        if (!isMediaRecorderSupported()) {
            button.disabled = true;
            button.title =
                "当前环境不支持录音，请使用 Chrome 打开本页面";
            return;
        }

        let mediaRecorder = null;
        let mediaStream = null;
        let chunks = [];
        let recording = false;

        function setUi(state) {
            button.classList.remove("listening", "busy");
            if (state === "recording") {
                button.classList.add("listening");
                button.textContent = "⏹";
                button.title = "录音中… 再次点击结束并识别";
            } else if (state === "busy") {
                button.classList.add("busy");
                button.textContent = "…";
                button.title = "正在识别语音…";
            } else {
                button.textContent = "🎤";
                button.title = isEmbeddedIdeBrowser()
                    ? "语音输入（内置浏览器：录完后服务端识别）"
                    : "语音输入（点击录音，再点结束）";
            }
        }

        function stopStream() {
            if (mediaStream) {
                mediaStream.getTracks().forEach((track) => track.stop());
                mediaStream = null;
            }
        }

        async function stopRecording() {
            if (!mediaRecorder || mediaRecorder.state === "inactive") return;
            mediaRecorder.stop();
        }

        button.addEventListener("click", async (event) => {
            event.preventDefault();
            if (button.disabled) return;

            if (recording) {
                await stopRecording();
                return;
            }

            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: true,
                });
                const mimeType = MediaRecorder.isTypeSupported(
                    "audio/webm;codecs=opus"
                )
                    ? "audio/webm;codecs=opus"
                    : "audio/webm";
                chunks = [];
                mediaRecorder = new MediaRecorder(mediaStream, { mimeType });
                mediaRecorder.ondataavailable = (e) => {
                    if (e.data && e.data.size > 0) chunks.push(e.data);
                };
                mediaRecorder.onstop = async () => {
                    recording = false;
                    stopStream();
                    const blob = new Blob(chunks, {
                        type: mediaRecorder.mimeType || "audio/webm",
                    });
                    mediaRecorder = null;
                    chunks = [];

                    if (!blob.size) {
                        setUi("idle");
                        notifyError(options, "录音太短，请重新录制");
                        return;
                    }

                    button.disabled = true;
                    setUi("busy");
                    try {
                        const text = await uploadAndTranscribe(blob, options);
                        if (text) {
                            const prefix = input.value.trim();
                            input.value = prefix ? `${prefix} ${text}` : text;
                            input.dispatchEvent(
                                new Event("input", { bubbles: true })
                            );
                            input.focus();
                        }
                    } catch (err) {
                        notifyError(
                            options,
                            err.message || "语音识别失败"
                        );
                    } finally {
                        button.disabled = false;
                        setUi("idle");
                    }
                };
                mediaRecorder.start();
                recording = true;
                setUi("recording");
            } catch (err) {
                recording = false;
                stopStream();
                setUi("idle");
                notifyError(
                    options,
                    `无法访问麦克风：${err.message || err}`
                );
            }
        });

        setUi("idle");
    }

    function initWebSpeechInput(input, button, options) {
        const lang = options.lang || "zh-CN";
        let recognition = null;
        let userWantsListen = false;
        let restartTimer = null;
        let sessionPrefix = "";
        let sessionFinal = "";

        function setListening(active) {
            button.classList.toggle("listening", active);
            button.textContent = active ? "⏹" : "🎤";
            button.title = active
                ? "正在聆听… 说完后点击停止"
                : "语音输入（点击开始说话）";
        }

        function clearRestartTimer() {
            if (restartTimer) {
                clearTimeout(restartTimer);
                restartTimer = null;
            }
        }

        function teardownRecognition() {
            clearRestartTimer();
            if (recognition) {
                recognition.onresult = null;
                recognition.onerror = null;
                recognition.onend = null;
                recognition.onstart = null;
                recognition = null;
            }
        }

        function applyTranscript(event) {
            let interim = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    sessionFinal += transcript;
                } else {
                    interim += transcript;
                }
            }
            input.value = sessionPrefix + sessionFinal + interim;
            input.dispatchEvent(new Event("input", { bubbles: true }));
        }

        function scheduleRestart(delayMs) {
            clearRestartTimer();
            if (!userWantsListen) return;
            restartTimer = setTimeout(() => {
                restartTimer = null;
                if (userWantsListen) beginRecognition();
            }, delayMs);
        }

        function beginRecognition() {
            if (!userWantsListen) return;
            teardownRecognition();

            recognition = new SpeechRecognition();
            recognition.lang = lang;
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;
            recognition.continuous = !isMobileDevice();

            recognition.onstart = () => setListening(true);
            recognition.onresult = (event) => applyTranscript(event);
            recognition.onerror = (event) => {
                const code = event.error || "";
                if (code === "no-speech" || code === "aborted") return;
                if (FATAL_ERRORS.has(code)) {
                    userWantsListen = false;
                    teardownRecognition();
                    setListening(false);
                    notifyError(options, errorMessage(code));
                }
            };
            recognition.onend = () => {
                const shouldContinue = userWantsListen;
                recognition = null;
                if (!shouldContinue) {
                    clearRestartTimer();
                    setListening(false);
                    return;
                }
                scheduleRestart(isMobileDevice() ? 120 : 250);
            };

            try {
                recognition.start();
            } catch (_) {
                if (userWantsListen) scheduleRestart(300);
            }
        }

        function startListening() {
            userWantsListen = true;
            sessionPrefix = input.value;
            if (sessionPrefix && !/\s$/.test(sessionPrefix)) {
                sessionPrefix += " ";
            }
            sessionFinal = "";
            beginRecognition();
        }

        function stopListening() {
            userWantsListen = false;
            clearRestartTimer();
            if (recognition) {
                try {
                    recognition.stop();
                } catch (_) {
                    /* ignore */
                }
            }
            teardownRecognition();
            setListening(false);
        }

        button.addEventListener("click", (event) => {
            event.preventDefault();
            if (userWantsListen) stopListening();
            else startListening();
        });

        setListening(false);
    }

    /**
     * @param {{ inputId: string, buttonId: string, lang?: string, getToken?: () => string, onError?: (msg: string) => void, forceServerStt?: boolean }} options
     */
    function initSpeechInput(options) {
        const input = document.getElementById(options.inputId);
        const button = document.getElementById(options.buttonId);
        if (!input || !button) return;

        const useServerMode =
            options.forceServerStt ||
            isEmbeddedIdeBrowser() ||
            !isSpeechInputSupported();

        if (useServerMode) {
            bindMicButton(input, button, options, initMediaRecorderSpeechInput);
        } else {
            bindMicButton(input, button, options, initWebSpeechInput);
        }
    }

    window.isSpeechInputSupported = isSpeechInputSupported;
    window.isEmbeddedIdeBrowser = isEmbeddedIdeBrowser;
    window.initSpeechInput = initSpeechInput;
})();
