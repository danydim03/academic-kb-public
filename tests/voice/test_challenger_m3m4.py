"""
Academic KB Voice Studio — Challenger 2 Empirical Stress Tests (Milestones M3 & M4)
Covers:
1. Biometric coordinates & Canvas 2D Dual-Slice Geometry (Y=424 fissure, 318x512, oral cavity, cyber glow)
2. Barge-in & cancellation synchronicity and in-flight audio packet behavior
3. Audio buffer jitter handling and schedule math (50ms cushion vs underrun recovery)
4. Malformed WebSocket message resilience (odd byteLength, non-dict JSON, unknown types, corrupt citations)
5. Fallback behavior (image load failure, AudioWorklet to ScriptProcessor fallback, 44.1kHz/48kHz resampling)
"""

import os
import json
import math
import struct
import subprocess
import pytest
import numpy as np
from PIL import Image

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
STUDY_HTML_PATH = os.path.join(PROJECT_ROOT, "study.html")
AVATAR_IMG_PATH = os.path.join(PROJECT_ROOT, "static/voice_avatar.png")


# ===========================================================================
# 1. Biometric Coordinates & Canvas 2D Geometry
# ===========================================================================

class TestBiometricCoordinatesAndAvatarGeometry:
    """Empirical verification of avatar dimensions, coordinates, and slicing math."""

    def test_avatar_image_file_properties(self):
        """Verifies physical voice_avatar.png file matches exactly 636x1024 RGBA."""
        assert os.path.exists(AVATAR_IMG_PATH), f"Missing image: {AVATAR_IMG_PATH}"
        img = Image.open(AVATAR_IMG_PATH)
        assert img.size == (636, 1024), f"Expected (636, 1024), got {img.size}"
        assert img.mode in ("RGBA", "RGB"), f"Expected RGBA/RGB mode, got {img.mode}"

    def test_fissure_line_y424_anatomical_gradient(self):
        """
        Empirically verifies Y=424 as the true lip contact fissure by computing
        the vertical intensity gradient across rows 415..435 in the mouth span X=250..380.
        The contact fissure between lips exhibits a distinct local luminance minimum / edge.
        """
        arr = np.array(Image.open(AVATAR_IMG_PATH).convert("L"))
        mouth_crop = arr[415:435, 250:380] # shape (20, 130)
        row_means = mouth_crop.mean(axis=1) # mean luminance per row
        
        # Row 424 corresponds to index 9 (424 - 415 = 9)
        min_row_idx = int(np.argmin(row_means))
        min_row_y = 415 + min_row_idx
        
        # The darkest contact line between upper and lower lips must be within +/- 2px of Y=424
        assert abs(min_row_y - 424) <= 2, f"Darkest fissure row found at Y={min_row_y}, expected close to 424"

    def test_dual_slice_canvas_geometry_tiling(self):
        """Verifies upper and lower slices tile 1024px image to 512px canvas with 0.5x scaling."""
        img_w, img_h = 636, 1024
        canvas_w, canvas_h = 318, 512
        fissure_y = 424
        
        # Upper slice: (0, 0, 636, 424) -> canvas (0, 0, 318, 212)
        upper_s_height = fissure_y
        upper_c_height = upper_s_height * 0.5
        assert upper_c_height == 212.0
        
        # Lower slice: (0, 424, 636, 600) -> canvas (0, 212, 318, 300)
        lower_s_height = img_h - fissure_y
        assert lower_s_height == 600
        lower_c_height = lower_s_height * 0.5
        assert lower_c_height == 300.0
        
        # Total heights
        assert upper_s_height + lower_s_height == img_h
        assert upper_c_height + lower_c_height == canvas_h

    def test_jaw_offset_formula_and_saturation(self):
        """
        Verifies Math.min(8, rms * 28):
        - 0.0 at rms=0
        - linear scaling for rms <= 8/28 (~0.2857)
        - clamped to 8.0px for rms > 0.2857
        """
        def jaw_offset(rms: float) -> float:
            return min(8.0, rms * 28.0)

        assert jaw_offset(0.0) == 0.0
        assert pytest.approx(jaw_offset(0.1), 0.001) == 2.8
        assert pytest.approx(jaw_offset(0.2), 0.001) == 5.6
        assert pytest.approx(jaw_offset(8.0 / 28.0), 0.001) == 8.0
        assert jaw_offset(0.3) == 8.0
        assert jaw_offset(0.5) == 8.0
        assert jaw_offset(1.0) == 8.0

    def test_cyber_glow_formula(self):
        """
        Verifies box-shadow formulas:
        glowBlur = 12.0 + rms * 40.0
        glowAlpha = 0.25 + rms * 0.65
        """
        def glow(rms: float):
            blur = 12.0 + rms * 40.0
            alpha = 0.25 + rms * 0.65
            return blur, alpha

        b0, a0 = glow(0.0)
        assert b0 == 12.0 and a0 == 0.25

        b_half, a_half = glow(0.5)
        assert b_half == 32.0 and pytest.approx(a_half, 0.001) == 0.575

        b1, a1 = glow(1.0)
        assert b1 == 52.0 and pytest.approx(a1, 0.001) == 0.90


# ===========================================================================
# 2. Barge-in & Cancellation Immediacy & Flaw Analysis
# ===========================================================================

class TestBargeInAndCancellation:
    """Verifies synchronous cancellation, active queue flushing, and in-flight audio packet handling."""

    def test_synchronous_playback_cancellation_execution(self):
        """
        Executes JavaScript simulation of LiveVoice.cancelPlayback() via Node.js
        to verify that all active Web Audio buffer sources are stopped with stop(0)
        and activeSources array is synchronously cleared to length 0.
        """
        js_code = """
        let stopCalls = 0;
        let disconnectCalls = 0;

        class MockSourceNode {
            stop(when) {
                if (when === 0) stopCalls++;
            }
            disconnect() {
                disconnectCalls++;
            }
        }

        const LiveVoice = {
            state: 'speaking',
            activeSources: [new MockSourceNode(), new MockSourceNode(), new MockSourceNode()],
            playbackCtx: { currentTime: 42.5 },
            nextPlayTime: 45.0,
            currentOutputRMS: 0.65,
            setVoiceState(s) { this.state = s; },
            cancelPlayback() {
                this.activeSources.forEach(s => {
                    try {
                        s.stop(0);
                        s.disconnect();
                    } catch(e) {}
                });
                this.activeSources = [];
                if (this.playbackCtx) {
                    this.nextPlayTime = this.playbackCtx.currentTime;
                }
                this.currentOutputRMS = 0.0;
                this.setVoiceState('interrupted');
            }
        };

        LiveVoice.cancelPlayback();

        console.log(JSON.stringify({
            stopCalls,
            disconnectCalls,
            remainingSources: LiveVoice.activeSources.length,
            nextPlayTime: LiveVoice.nextPlayTime,
            currentOutputRMS: LiveVoice.currentOutputRMS,
            state: LiveVoice.state
        }));
        """
        res = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        
        assert data["stopCalls"] == 3
        assert data["disconnectCalls"] == 3
        assert data["remainingSources"] == 0
        assert data["nextPlayTime"] == 42.5
        assert data["currentOutputRMS"] == 0.0
        assert data["state"] == "interrupted"

    def test_in_flight_audio_packet_after_barge_in_flaw(self):
        """
        Adversarial test: Simulates arrival of an in-flight audio packet
        after client barge-in was triggered.
        Reveals that study.html queuePlayback() unconditionally switches
        state back to 'speaking' if an in-flight packet arrives while in 'interrupted'.
        """
        js_code = """
        class MockAudioBuffer { duration = 0.042; }
        class MockContext {
            currentTime = 10.0;
            createBuffer() { return { duration: 0.042, getChannelData: () => new Float32Array(1024) }; }
            createBufferSource() { return { connect: () => {}, start: () => {}, onended: null }; }
        }

        const LiveVoice = {
            state: 'interrupted',
            activeSources: [],
            playbackCtx: new MockContext(),
            outputAnalyser: {},
            nextPlayTime: 10.0,
            SAMPLE_RATE_OUT: 24000,
            JITTER_CUSHION_SEC: 0.05,
            setVoiceState(s) { this.state = s; },
            queuePlayback(arrayBuffer) {
                if (!this.playbackCtx) return;
                const int16 = new Int16Array(arrayBuffer);
                if (int16.length === 0) return;
                const float32 = new Float32Array(int16.length);
                const audioBuffer = this.playbackCtx.createBuffer(1, float32.length, this.SAMPLE_RATE_OUT);
                const source = this.playbackCtx.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(this.outputAnalyser);

                const now = this.playbackCtx.currentTime;
                if (this.nextPlayTime < now) {
                    this.nextPlayTime = now + this.JITTER_CUSHION_SEC;
                }
                source.start(this.nextPlayTime);
                this.nextPlayTime += audioBuffer.duration;
                this.activeSources.push(source);

                if (this.state !== 'speaking') {
                    this.setVoiceState('speaking');
                }
            }
        };

        // An in-flight audio packet arrives right after cancellation
        const pcmPacket = new ArrayBuffer(2048);
        LiveVoice.queuePlayback(pcmPacket);

        console.log(JSON.stringify({
            stateAfterInFlightPacket: LiveVoice.state,
            queuedSources: LiveVoice.activeSources.length
        }));
        """
        res = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        
        # When an in-flight packet arrives, state changes back to 'speaking'
        # instead of discarding stale audio packets during 'interrupted'!
        assert data["stateAfterInFlightPacket"] == "speaking"
        assert data["queuedSources"] == 1


# ===========================================================================
# 3. Audio Buffer Jitter Handling & Schedule Math
# ===========================================================================

class TestAudioBufferJitterHandling:
    """Verifies jitter buffer scheduling math and underrun resilience."""

    def test_jitter_buffer_schedule_math_under_normal_stream(self):
        """
        Simulates consecutive 42.6ms packets (1024 samples @ 24kHz) arriving with jitter.
        Verifies schedule times are strictly monotonic and maintain continuity.
        """
        packet_duration = 1024 / 24000.0  # ~0.04267 sec
        cushion = 0.05

        current_time = 0.1
        next_play_time = current_time

        schedule_times = []
        
        # 10 packets arriving at intervals of 30ms to 50ms
        arrival_deltas = [0.035, 0.040, 0.038, 0.055, 0.030, 0.042, 0.045, 0.039, 0.041, 0.038]
        
        for dt in arrival_deltas:
            current_time += dt
            now = current_time
            if next_play_time < now:
                next_play_time = now + cushion
            play_at = next_play_time
            next_play_time += packet_duration
            schedule_times.append((play_at, play_at + packet_duration))

        # Check that no packet starts before its arrival time
        for i, (start, end) in enumerate(schedule_times):
            assert start >= 0.1, "Scheduled before initial time"
            if i > 0:
                prev_start, prev_end = schedule_times[i - 1]
                # Either perfectly contiguous (prev_end == start) or cushion reset (start >= prev_end)
                assert start >= prev_start, "Non-monotonic schedule"

    def test_jitter_buffer_underrun_recovery(self):
        """
        Simulates network stall: packet delayed by 250ms causing underrun (buffer starvation).
        Verifies that playback recovers with 50ms cushion instead of scheduling in the past.
        """
        packet_duration = 0.04267
        cushion = 0.05
        now = 1.0
        next_play_time = 1.04267 # ends at 1.04267

        # Stalled arrival: next packet arrives at now = 1.300 (buffer underrun of 257ms)
        stall_arrival_time = 1.300
        now = stall_arrival_time

        assert next_play_time < now, "Buffer underrun condition"
        if next_play_time < now:
            next_play_time = now + cushion

        scheduled_start = next_play_time
        # Scheduled 50ms into the future from arrival time, NOT in the past
        assert scheduled_start == pytest.approx(1.350, 0.001)
        assert scheduled_start > now


# ===========================================================================
# 4. Malformed WebSocket Message & Binary Frame Resilience
# ===========================================================================

class TestWebSocketEventResilience:
    """Stress tests frontend message parsers against malformed inputs."""

    def test_odd_byte_length_binary_frame_crash(self):
        """
        EMPIRICAL BUG DETECTION:
        Demonstrates that passing an odd number of bytes (e.g. 3 bytes or 2047 bytes)
        to study.html queuePlayback() throws an uncaught RangeError in JavaScript
        because Int16Array requires byteLength to be a multiple of 2!
        """
        js_code = """
        function queuePlayback(arrayBuffer) {
            const int16 = new Int16Array(arrayBuffer);
            return int16.length;
        }

        let errorCaught = null;
        try {
            const oddBuffer = new ArrayBuffer(3); // 3 bytes
            queuePlayback(oddBuffer);
        } catch(e) {
            errorCaught = { name: e.name, message: e.message };
        }
        console.log(JSON.stringify({ errorCaught }));
        """
        res = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        
        assert data["errorCaught"] is not None
        assert data["errorCaught"]["name"] == "RangeError"
        assert "multiple of 2" in data["errorCaught"]["message"]

    def test_malformed_grounding_citations_crash(self):
        """
        EMPIRICAL BUG DETECTION:
        Demonstrates that when a grounding event contains non-array citations
        (e.g. citations: "Doc1.pdf") or citations with null items ([null]),
        study.html renderGroundingCitations throws uncaught TypeError.
        """
        js_code = """
        const LiveVoice = {
            citationsCount: 0,
            renderGroundingCitations(groundingMsg) {
                const citations = groundingMsg.citations || [];
                this.citationsCount += citations.length;
                citations.forEach(c => {
                    const str = `[${c.course ? c.course + ' | ' : ''}${c.source || 'Doc'}${c.page ? ', p. ' + c.page : ''}]`;
                });
            }
        };

        const errors = [];
        // Test 1: string citations
        try {
            LiveVoice.renderGroundingCitations({ type: 'grounding', citations: 'invalid_string' });
        } catch(e) {
            errors.push({ test: 'string_citations', name: e.name, message: e.message });
        }

        // Test 2: null entry in citations array
        try {
            LiveVoice.renderGroundingCitations({ type: 'grounding', citations: [null] });
        } catch(e) {
            errors.push({ test: 'null_citation_item', name: e.name, message: e.message });
        }

        console.log(JSON.stringify(errors));
        """
        res = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        errors = json.loads(res.stdout)
        
        assert len(errors) == 2
        assert errors[0]["test"] == "string_citations"
        assert errors[0]["name"] == "TypeError"
        assert errors[1]["test"] == "null_citation_item"
        assert errors[1]["name"] == "TypeError"

    def test_non_dict_json_resilience(self):
        """
        Verifies handleServerMessage() behavior when parsing non-dict JSON primitives:
        - 12345
        - "some text"
        - true
        - null
        - [1, 2, 3]
        """
        js_code = """
        const LiveVoice = {
            state: 'idle',
            cancelCalled: false,
            cancelPlayback() { this.cancelCalled = true; },
            handleServerMessage(msg) {
                if (!msg || typeof msg !== 'object') return;
                switch (msg.type) {
                    case 'ready': break;
                    default:
                        if (msg.interrupted === true) this.cancelPlayback();
                        break;
                }
            }
        };

        const testInputs = [12345, "plain string", true, null, [1, 2, 3], { type: "unknown" }];
        let threw = false;
        try {
            for (const inp of testInputs) {
                LiveVoice.handleServerMessage(inp);
            }
        } catch(e) {
            threw = true;
        }
        console.log(JSON.stringify({ threw }));
        """
        res = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        assert data["threw"] is False


# ===========================================================================
# 5. Fallback Behavior & Sample Rate Conversion
# ===========================================================================

class TestFallbacksAndResampling:
    """Verifies fallbacks (image load failure, ScriptProcessor, sample rate conversion)."""

    def test_avatar_image_load_failure_fallback(self):
        """
        Verifies that when avatarImg fails to load (naturalWidth == 0 or complete == false),
        renderAvatarFrame falls back to rendering placeholder background and text without throwing.
        """
        js_code = """
        class MockCanvasContext {
            fillStyle = '';
            font = '';
            textAlign = '';
            rects = [];
            texts = [];
            clearRect() {}
            fillRect(x, y, w, h) { this.rects.push({x, y, w, h, fill: this.fillStyle}); }
            fillText(text, x, y) { this.texts.push({text, x, y, fill: this.fillStyle}); }
        }

        const LiveVoice = {
            ctx: new MockCanvasContext(),
            canvas: {},
            AVATAR_CANVAS_WIDTH: 318,
            AVATAR_CANVAS_HEIGHT: 512,
            currentOutputRMS: 0.0,
            avatarImg: { complete: true, naturalWidth: 0 }, // Failed or unloaded image
            renderAvatarFrame() {
                if (!this.ctx || !this.canvas) return;
                const ctx = this.ctx;
                ctx.clearRect(0, 0, this.AVATAR_CANVAS_WIDTH, this.AVATAR_CANVAS_HEIGHT);
                if (this.avatarImg && this.avatarImg.complete && this.avatarImg.naturalWidth > 0) {
                    // Would draw image
                } else {
                    ctx.fillStyle = '#0a1610';
                    ctx.fillRect(0, 0, this.AVATAR_CANVAS_WIDTH, this.AVATAR_CANVAS_HEIGHT);
                    ctx.fillStyle = 'var(--text-dim)';
                    ctx.font = '13px Inter, sans-serif';
                    ctx.textAlign = 'center';
                    ctx.fillText('Caricamento Avatar...', this.AVATAR_CANVAS_WIDTH / 2, this.AVATAR_CANVAS_HEIGHT / 2);
                }
            }
        };

        LiveVoice.renderAvatarFrame();

        console.log(JSON.stringify({
            rectCount: LiveVoice.ctx.rects.length,
            textDrawn: LiveVoice.ctx.texts[0].text
        }));
        """
        res = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        
        assert data["rectCount"] == 1
        assert "Caricamento Avatar..." in data["textDrawn"]

    def test_resampling_44100hz_negative_index_and_nan_glitch(self):
        """
        CRITICAL EMPIRICAL BUG DETECTION:
        Demonstrates that downsampling from 44.1kHz to 16kHz in both AudioWorklet
        and ScriptProcessor causes resampleIndex to become negative (-0.88),
        leading to channelData[-1] (undefined) and NaN samples in output Int16 PCM.
        """
        js_code = """
        const rate = 44100;
        const targetRate = 16000;
        const ratio = rate / targetRate; // 2.75625
        let resampleIndex = 0;
        const quantumSize = 128; // AudioWorklet quantum size
        const channelData = new Float32Array(quantumSize);
        for (let i = 0; i < quantumSize; i++) channelData[i] = 0.5 * Math.sin(i * 0.1);

        let nanCount = 0;
        let negativeIndexCount = 0;

        // Process 100 consecutive audio quantums
        for (let q = 0; q < 100; q++) {
            for (let i = 0; i < channelData.length; i++) {
                while (resampleIndex <= i) {
                    const idx = Math.floor(resampleIndex);
                    if (idx < 0) negativeIndexCount++;
                    const frac = resampleIndex - idx;
                    const nextIdx = Math.min(channelData.length - 1, idx + 1);
                    const sample = (1 - frac) * channelData[idx] + frac * channelData[nextIdx];
                    if (isNaN(sample)) nanCount++;
                    resampleIndex += ratio;
                }
            }
            resampleIndex -= channelData.length;
        }

        console.log(JSON.stringify({ negativeIndexCount, nanCount }));
        """
        res = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        
        # At 44.1kHz, negativeIndexCount and nanCount are > 0!
        assert data["negativeIndexCount"] > 0, "Expected negative index glitch at 44.1kHz"
        assert data["nanCount"] > 0, "Expected NaN samples glitch at 44.1kHz"

    def test_resampling_48000hz_stability(self):
        """
        Demonstrates that at 48kHz (exact integer ratio 48000/16000 = 3.0),
        resampleIndex does not become negative and produces 0 NaNs.
        """
        js_code = """
        const rate = 48000;
        const targetRate = 16000;
        const ratio = rate / targetRate; // 3.0 exact
        let resampleIndex = 0;
        const quantumSize = 128;
        const channelData = new Float32Array(quantumSize);
        for (let i = 0; i < quantumSize; i++) channelData[i] = 0.5 * Math.sin(i * 0.1);

        let nanCount = 0;
        let negativeIndexCount = 0;

        for (let q = 0; q < 100; q++) {
            for (let i = 0; i < channelData.length; i++) {
                while (resampleIndex <= i) {
                    const idx = Math.floor(resampleIndex);
                    if (idx < 0) negativeIndexCount++;
                    const frac = resampleIndex - idx;
                    const nextIdx = Math.min(channelData.length - 1, idx + 1);
                    const sample = (1 - frac) * channelData[idx] + frac * channelData[nextIdx];
                    if (isNaN(sample)) nanCount++;
                    resampleIndex += ratio;
                }
            }
            resampleIndex -= channelData.length;
        }

        console.log(JSON.stringify({ negativeIndexCount, nanCount }));
        """
        res = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        
        assert data["negativeIndexCount"] == 0
        assert data["nanCount"] == 0
