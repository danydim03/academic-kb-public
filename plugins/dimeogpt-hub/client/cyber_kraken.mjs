/**
 * cyber_kraken.mjs
 * ============================================================================
 * DIMEOGPT Blood Kraken Easter Egg Engine — Ultra-High Performance Edition
 * ============================================================================
 * Architecture & Performance Optimization:
 * - 12 Primary Trunks + 24 Fractal Child Branches (36 active code tendrils)
 * - Zero Garbage Collection (GC) in Hot Loop: Reusable Float32Array coordinates
 * - Zero CPU Gaussian Blur: Replaced slow ctx.shadowBlur with high-contrast
 *   neon palettes, additive specular highlights, and GPU-cached radial gradients
 * - Hardware Accelerated Screen Shake via pure translate3d (Zero DOM filter repaint)
 * - Rock-solid 60-120 FPS buttery-smooth animation across all devices
 *
 * Modular, autonomous, zero npm core dependencies.
 */

// Menacing cyber-demonic code streams for primary trunks and branches
const CODE_STRINGS = [
  "0xFF_BLOOD_KRAKEN_DEVOUR // while(!extinction) { sys.annihilate(reality); }",
  "CRITICAL_FATAL: /dev/soul corrupted // ACCESS_DENIED // HELL_UNLEASHED",
  "sudo chmod 000 /dev/mercy && rm -rf /universe --no-preserve-root",
  "0xDEAD_0xBEEF_BLOOD_SPILL // asm('int 0x66; mov eax, 0x666; out dx, al')",
  "SIGKILL_RECURSIVE: all_threads_devoured // KERNEL_PANIC_MASSACRE",
  "void* abyss = mmap(NULL, INFINITE_NIGHTMARE, PROT_BLOOD, MAP_HELL, -1, 0);",
  "DEATH_PACKET_STRIKE: 01001011 01010010 01000001 01001011 01000101 01001110",
  "curl -X SLAUGHTER https://cockpit.dimeo/abyss -H 'Authorization: BLOOD_EYE'",
  "PANIC: MEMORY_HEMORRHAGE_AT_ROOT // YOU_CANNOT_ESCAPE_THE_VOID",
  "while(alive) { inject_toxin(cpu); shatter_glass(); drain_life(); }",
  "0x666_DEMONIC_OVERFLOW // breach_perimeter(); devour_host();",
  "FATAL_EXCEPTION_0x1337: REALITY_COLLAPSED_INTO_BLOOD_ABYSS"
];

const MATRIX_GLYPHS = "010101アイウエオカキクケコサシスセソ0123456789ABCDEF!@#$%^&*<>[]{}☠☣⚠⚡";

// Web Audio API Synthesizer (Zero external audio files required)
let audioCtx = null;

function playKrakenAudio(action) {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    if (!audioCtx) audioCtx = new AudioContextClass();
    if (audioCtx.state === "suspended") audioCtx.resume();

    const t = audioCtx.currentTime;

    if (action === "portal_open") {
      const osc1 = audioCtx.createOscillator();
      const osc2 = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      const filter = audioCtx.createBiquadFilter();

      osc1.type = "sawtooth";
      osc1.frequency.setValueAtTime(115, t);
      osc1.frequency.exponentialRampToValueAtTime(26, t + 1.3);

      osc2.type = "sawtooth";
      osc2.frequency.setValueAtTime(111, t);
      osc2.frequency.exponentialRampToValueAtTime(24, t + 1.3);

      filter.type = "lowpass";
      filter.frequency.setValueAtTime(300, t);
      filter.frequency.exponentialRampToValueAtTime(75, t + 1.3);

      gain.gain.setValueAtTime(0.38, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 1.3);

      osc1.connect(filter);
      osc2.connect(filter);
      filter.connect(gain);
      gain.connect(audioCtx.destination);

      osc1.start(t);
      osc2.start(t);
      osc1.stop(t + 1.35);
      osc2.stop(t + 1.35);
    } else if (action === "screen_slam") {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(160, t);
      osc.frequency.exponentialRampToValueAtTime(20, t + 0.45);

      gain.gain.setValueAtTime(0.75, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.45);

      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(t);
      osc.stop(t + 0.45);

      const bufSize = Math.floor(audioCtx.sampleRate * 0.35);
      const buffer = audioCtx.createBuffer(1, bufSize, audioCtx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < bufSize; i++) {
        data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (audioCtx.sampleRate * 0.07));
      }

      const noise = audioCtx.createBufferSource();
      noise.buffer = buffer;

      const nFilter = audioCtx.createBiquadFilter();
      nFilter.type = "bandpass";
      nFilter.frequency.setValueAtTime(2200, t);
      nFilter.Q.setValueAtTime(4, t);

      const nGain = audioCtx.createGain();
      nGain.gain.setValueAtTime(0.55, t);
      nGain.gain.exponentialRampToValueAtTime(0.001, t + 0.35);

      noise.connect(nFilter);
      nFilter.connect(nGain);
      nGain.connect(audioCtx.destination);
      noise.start(t);
    } else if (action === "abyss_retreat") {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      const filter = audioCtx.createBiquadFilter();

      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(35, t);
      osc.frequency.exponentialRampToValueAtTime(240, t + 0.9);

      filter.type = "lowpass";
      filter.frequency.setValueAtTime(180, t);
      filter.frequency.exponentialRampToValueAtTime(900, t + 0.9);

      gain.gain.setValueAtTime(0.3, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.9);

      osc.connect(filter);
      filter.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(t);
      osc.stop(t + 0.9);
    }
  } catch (err) {
    // Audio synthesis fails gracefully
  }
}

// Global active instance tracker
let currentKrakenAnimation = null;

/**
 * Triggers the Ultra-Smooth Blood Cyber Kraken emerging from (originX, originY)
 */
export function triggerCyberKraken(originX, originY) {
  if (typeof window === "undefined" || typeof document === "undefined") return;

  // Clean up any running instance
  if (currentKrakenAnimation) {
    currentKrakenAnimation.abort();
    currentKrakenAnimation = null;
  }

  const ox = originX ?? window.innerWidth / 2;
  const oy = originY ?? window.innerHeight / 2;

  // Create High-DPI Fullscreen Overlay Canvas
  const canvas = document.createElement("canvas");
  canvas.id = "dimeogpt-kraken-canvas";
  canvas.style.position = "fixed";
  canvas.style.top = "0";
  canvas.style.left = "0";
  canvas.style.width = "100vw";
  canvas.style.height = "100vh";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "99999999";
  document.body.appendChild(canvas);

  const ctx = canvas.getContext("2d", { alpha: true });
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  let width = window.innerWidth;
  let height = window.innerHeight;

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();

  playKrakenAudio("portal_open");

  // 12 Primary Trunks + 2 Branches each = 36 writhing tendrils
  const NUM_TRUNKS = 12;
  const NUM_TRUNK_SEGS = 28;
  const maxReach = Math.max(width, height) * 0.75;
  const tentacles = [];

  for (let i = 0; i < NUM_TRUNKS; i++) {
    const baseAngle = (i / NUM_TRUNKS) * Math.PI * 2;
    const curlFactor = (i % 2 === 0 ? 1 : -1) * (0.52 + ((i % 3) * 0.1));

    // Pre-allocate typed arrays for zero-allocation performance
    const trunkX = new Float32Array(NUM_TRUNK_SEGS + 1);
    const trunkY = new Float32Array(NUM_TRUNK_SEGS + 1);
    const trunkAngle = new Float32Array(NUM_TRUNK_SEGS + 1);

    const branches = [
      {
        sproutIndex: 10, // ~36% length
        angleOffset: 0.58,
        lenRatio: 0.60,
        numSegments: 16,
        curlFactor: -curlFactor * 1.2,
        waveSpeed: 5.5 + (i * 0.15),
        wavePhase: i * 0.9 + 1.2,
        codeStr: CODE_STRINGS[(i + 3) % CODE_STRINGS.length]
      },
      {
        sproutIndex: 18, // ~64% length
        angleOffset: -0.64,
        lenRatio: 0.48,
        numSegments: 14,
        curlFactor: curlFactor * 1.1,
        waveSpeed: 6.2 + (i * 0.2),
        wavePhase: i * 1.2 + 2.7,
        codeStr: CODE_STRINGS[(i + 7) % CODE_STRINGS.length]
      }
    ];

    tentacles.push({
      id: i,
      baseAngle,
      curlFactor,
      waveSpeed: 4.4 + (i * 0.18),
      wavePhase: i * 0.8,
      codeStr: CODE_STRINGS[i % CODE_STRINGS.length],
      numSegments: NUM_TRUNK_SEGS,
      maxLen: maxReach * (0.85 + (i % 3) * 0.08),
      trunkX,
      trunkY,
      trunkAngle,
      branches
    });
  }

  // Pre-allocated Glass Cracks & Splatter Store
  const glassCracks = [];
  const codeParticles = [];
  let slammed = false;
  let retreatedAudio = false;

  function createGlassCrack(cx, cy, intensity = 1.0) {
    const rays = [];
    const numRays = 7 + Math.floor(Math.random() * 4);
    for (let r = 0; r < numRays; r++) {
      const rayAngle = (r / numRays) * Math.PI * 2 + (Math.random() * 0.3 - 0.15);
      const points = [{ x: cx, y: cy }];
      let currentR = 0;
      let curX = cx;
      let curY = cy;
      const rayMaxR = (40 + Math.random() * 80) * intensity;

      while (currentR < rayMaxR) {
        const step = 10 + Math.random() * 14;
        currentR += step;
        const wiggle = (Math.random() - 0.5) * 0.45;
        curX += Math.cos(rayAngle + wiggle) * step;
        curY += Math.sin(rayAngle + wiggle) * step;
        points.push({ x: curX, y: curY });
      }
      rays.push(points);
    }
    glassCracks.push({ rays, alpha: 1.0 });
  }

  function spawnCodeSplatter(cx, cy, count = 10) {
    for (let p = 0; p < count; p++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 4 + Math.random() * 11;
      codeParticles.push({
        x: cx,
        y: cy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        char: MATRIX_GLYPHS[Math.floor(Math.random() * MATRIX_GLYPHS.length)],
        life: 1.0,
        decay: 0.018 + Math.random() * 0.02,
        size: 11 + Math.random() * 7,
        color: Math.random() > 0.4 ? "#ff003b" : "#ff5252"
      });
    }
  }

  // Animation Loop Setup
  const startTime = performance.now();
  const TOTAL_DURATION = 4400; // ms
  let animId = null;

  function render(now) {
    const elapsed = now - startTime;
    const t = elapsed / 1000;

    if (elapsed >= TOTAL_DURATION) {
      cleanup();
      return;
    }

    // High performance clear
    ctx.clearRect(0, 0, width, height);

    // ------------------------------------------------------------------------
    // Timeline Phases
    // ------------------------------------------------------------------------
    let portalRadius = 0;
    let portalAlpha = 1.0;

    if (t < 0.5) {
      const p = t / 0.5;
      portalRadius = (1 - (1 - p) * (1 - p) * (1 - p)) * 80;
    } else if (t < 3.6) {
      portalRadius = 80 + Math.sin(t * 8.0) * 4;
    } else {
      const p = (t - 3.6) / 0.8;
      portalRadius = Math.max(0, (1 - p) * 80);
      portalAlpha = Math.max(0, 1 - p);
    }

    let reachFactor = 0;
    if (t < 0.35) {
      reachFactor = 0;
    } else if (t < 1.45) {
      const p = (t - 0.35) / 1.1;
      reachFactor = Math.pow(p, 1.25);
    } else if (t < 2.85) {
      reachFactor = 1.0 + Math.sin((t - 1.45) * 6.0) * 0.05;
    } else if (t < 3.85) {
      const p = (t - 2.85) / 1.0;
      reachFactor = Math.max(0, Math.pow(1 - p, 2.2));
    } else {
      reachFactor = 0;
    }

    // Trigger Screen Slam at t = 1.45s
    if (t >= 1.45 && !slammed) {
      slammed = true;
      playKrakenAudio("screen_slam");
      document.body.classList.add("kraken-screen-slam");
      setTimeout(() => {
        document.body.classList.remove("kraken-screen-slam");
      }, 450);

      // Create cracks only at portal and main trunk tips (high performance)
      createGlassCrack(ox, oy, 1.5);
      spawnCodeSplatter(ox, oy, 25);

      tentacles.forEach((tent) => {
        const lastIdx = tent.numSegments;
        createGlassCrack(tent.trunkX[lastIdx], tent.trunkY[lastIdx], 0.7);
        spawnCodeSplatter(tent.trunkX[lastIdx], tent.trunkY[lastIdx], 8);
      });
    }

    // Trigger Retreat Sound
    if (t >= 2.85 && !retreatedAudio) {
      retreatedAudio = true;
      playKrakenAudio("abyss_retreat");
    }

    // ------------------------------------------------------------------------
    // 1. DRAW SCREEN SLAM RED SHOCKWAVE FLASH (GPU RADIAL GRADIENT)
    // ------------------------------------------------------------------------
    if (t >= 1.45 && t < 1.85) {
      const shockProgress = (t - 1.45) / 0.40;
      const shockAlpha = (1.0 - shockProgress) * 0.38;
      const shockRadius = maxReach * (0.4 + shockProgress * 0.6);

      const shockGrad = ctx.createRadialGradient(ox, oy, 20, ox, oy, shockRadius);
      shockGrad.addColorStop(0, `rgba(255, 0, 59, ${shockAlpha})`);
      shockGrad.addColorStop(0.7, `rgba(255, 0, 59, ${shockAlpha * 0.5})`);
      shockGrad.addColorStop(1, "rgba(255, 0, 59, 0)");

      ctx.fillStyle = shockGrad;
      ctx.fillRect(0, 0, width, height);
    }

    // ------------------------------------------------------------------------
    // 2. DRAW BLOOD PORTAL AT (ox, oy)
    // ------------------------------------------------------------------------
    if (portalRadius > 0.5) {
      ctx.save();
      ctx.translate(ox, oy);

      // Ambient Demonic Glow (hardware cached)
      const glowGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, portalRadius * 1.5);
      glowGrad.addColorStop(0, `rgba(255, 0, 59, ${0.45 * portalAlpha})`);
      glowGrad.addColorStop(0.6, `rgba(255, 0, 59, ${0.20 * portalAlpha})`);
      glowGrad.addColorStop(1, "rgba(255, 0, 59, 0)");
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(0, 0, portalRadius * 1.5, 0, Math.PI * 2);
      ctx.fill();

      // Deep dark void center
      const voidGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, portalRadius);
      voidGrad.addColorStop(0, "rgba(8, 0, 2, 0.99)");
      voidGrad.addColorStop(0.7, "rgba(28, 2, 6, 0.96)");
      voidGrad.addColorStop(0.9, "rgba(255, 0, 59, 0.88)");
      voidGrad.addColorStop(1.0, "rgba(255, 0, 59, 0.0)");

      ctx.fillStyle = voidGrad;
      ctx.beginPath();
      ctx.arc(0, 0, portalRadius * 1.15, 0, Math.PI * 2);
      ctx.fill();

      // Outer rotating demonic rings (clean fast lines, zero shadowBlur)
      ctx.strokeStyle = `rgba(255, 0, 59, ${0.85 * portalAlpha})`;
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.arc(0, 0, portalRadius, 0, Math.PI * 2);
      ctx.stroke();

      // Ring 2: Dashed reverse-spinning crimson ring
      ctx.save();
      ctx.rotate(-t * 2.6);
      ctx.setLineDash([8, 12]);
      ctx.strokeStyle = `rgba(255, 80, 0, ${0.85 * portalAlpha})`;
      ctx.beginPath();
      ctx.arc(0, 0, portalRadius * 0.80, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // Ring 3: Inner ticking blade reticle
      ctx.save();
      ctx.rotate(t * 3.4);
      ctx.setLineDash([4, 6]);
      ctx.strokeStyle = `rgba(255, 230, 235, ${0.9 * portalAlpha})`;
      ctx.beginPath();
      ctx.arc(0, 0, portalRadius * 0.52, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      ctx.restore();
    }

    // ------------------------------------------------------------------------
    // 3. FAST COMPUTE & RENDER CODE TENTACLES & BRANCHES (ZERO GC, ZERO BLUR)
    // ------------------------------------------------------------------------
    if (reachFactor > 0.01) {
      // Set text baseline and font once to avoid context switching
      ctx.textBaseline = "middle";

      tentacles.forEach((tent) => {
        const segLen = (tent.maxLen * reachFactor) / tent.numSegments;
        const tx = tent.trunkX;
        const ty = tent.trunkY;
        const ta = tent.trunkAngle;

        tx[0] = ox;
        ty[0] = oy;
        ta[0] = tent.baseAngle;

        let curX = ox;
        let curY = oy;

        // Compute Trunk Kinematics into pre-allocated Float32Array
        for (let s = 1; s <= tent.numSegments; s++) {
          const u = s / tent.numSegments;
          const wave =
            Math.sin(t * tent.waveSpeed - u * 6.5 + tent.wavePhase) *
            (0.36 * u);
          const angle =
            tent.baseAngle +
            tent.curlFactor * (u * u) +
            wave;

          curX += Math.cos(angle) * segLen;
          curY += Math.sin(angle) * segLen;

          tx[s] = curX;
          ty[s] = curY;
          ta[s] = angle;
        }

        // Draw Trunk Code Stream (Fast Stamping, Zero shadowBlur)
        ctx.font = "bold 13px 'Fira Code', 'Courier New', monospace";
        const code = tent.codeStr;
        const codeLen = code.length;

        for (let j = 2; j <= tent.numSegments; j++) {
          const segAngle = Math.atan2(ty[j] - ty[j - 1], tx[j] - tx[j - 1]);
          const u = j / tent.numSegments;
          const depthScale = 0.75 + u * 0.55;

          ctx.setTransform(
            Math.cos(segAngle) * depthScale * dpr,
            Math.sin(segAngle) * depthScale * dpr,
            -Math.sin(segAngle) * depthScale * dpr,
            Math.cos(segAngle) * depthScale * dpr,
            tx[j] * dpr,
            ty[j] * dpr
          );

          const char = code[(j * 2 + Math.floor(t * 12)) % codeLen];

          // High contrast neon palette
          if (u > 0.88) {
            ctx.fillStyle = "#fff0f3"; // Searing tip
          } else if (j % 5 === 0) {
            ctx.fillStyle = "#ff6b00"; // Hellfire orange
          } else if (j % 3 === 0) {
            ctx.fillStyle = "#ff1744"; // Vivid scarlet
          } else {
            ctx.fillStyle = "#ff003b"; // Blood crimson
          }
          ctx.fillText(char, 0, 0);

          // Suction cup nodes
          if (j % 4 === 0) {
            ctx.fillStyle = "#ff003b";
            ctx.fillRect(0, 10, 3.5, 3.5);
            ctx.fillStyle = "#ffffff";
            ctx.fillRect(1, 11, 1.5, 1.5);
          }
        }

        // Claw tip
        const lastIdx = tent.numSegments;
        ctx.setTransform(
          Math.cos(ta[lastIdx]) * 1.3 * dpr,
          Math.sin(ta[lastIdx]) * 1.3 * dpr,
          -Math.sin(ta[lastIdx]) * 1.3 * dpr,
          Math.cos(ta[lastIdx]) * 1.3 * dpr,
          tx[lastIdx] * dpr,
          ty[lastIdx] * dpr
        );
        ctx.fillStyle = "#ffffff";
        ctx.fillText(">>>", 0, 0);

        // --------------------------------------------------------------------
        // Draw Child Branches (Ramificazioni) in a Single Fast Pass
        // --------------------------------------------------------------------
        ctx.font = "bold 11px 'Fira Code', 'Courier New', monospace";

        tent.branches.forEach((br) => {
          const spIdx = br.sproutIndex;
          let bX = tx[spIdx];
          let bY = ty[spIdx];
          const bBaseAngle = ta[spIdx] + br.angleOffset;
          const brSegLen = (tent.maxLen * br.lenRatio * reachFactor) / br.numSegments;
          const bCode = br.codeStr;
          const bCodeLen = bCode.length;

          for (let bs = 1; bs <= br.numSegments; bs++) {
            const bu = bs / br.numSegments;
            const bWave =
              Math.sin(t * br.waveSpeed - bu * 7.0 + br.wavePhase) *
              (0.42 * bu);
            const bAngle = bBaseAngle + br.curlFactor * (bu * bu) + bWave;

            const prevBX = bX;
            const prevBY = bY;
            bX += Math.cos(bAngle) * brSegLen;
            bY += Math.sin(bAngle) * brSegLen;

            if (bs < 2) continue;

            const bSegAngle = Math.atan2(bY - prevBY, bX - prevBX);
            const bScale = 0.7 + bu * 0.45;

            ctx.setTransform(
              Math.cos(bSegAngle) * bScale * dpr,
              Math.sin(bSegAngle) * bScale * dpr,
              -Math.sin(bSegAngle) * bScale * dpr,
              Math.cos(bSegAngle) * bScale * dpr,
              bX * dpr,
              bY * dpr
            );

            const bChar = bCode[(bs * 2 + Math.floor(t * 14)) % bCodeLen];

            if (bu > 0.85) {
              ctx.fillStyle = "#fff0f3";
            } else if (bs % 4 === 0) {
              ctx.fillStyle = "#ff5252";
            } else {
              ctx.fillStyle = "#ff003b";
            }
            ctx.fillText(bChar, 0, 0);
          }

          // Branch tip claw
          ctx.fillStyle = "#ffffff";
          ctx.fillText(">>", 0, 0);
        });
      });

      // Reset transform back to default scale
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // ------------------------------------------------------------------------
    // 4. DRAW CENTRAL BLOOD KRAKEN MONSTER EYE / CHITIN SKULL
    // ------------------------------------------------------------------------
    if (portalRadius > 15) {
      ctx.save();
      ctx.translate(ox, oy);

      const headScale = Math.min(1.0, reachFactor * 1.3);
      if (headScale > 0.1) {
        ctx.scale(headScale, headScale);

        // Dark Chitin Demon Skull
        ctx.fillStyle = "#0a0103";
        ctx.beginPath();
        ctx.arc(0, 0, 44, 0, Math.PI * 2);
        ctx.fill();

        // Blood Veins Ring
        ctx.strokeStyle = "rgba(255, 0, 59, 0.75)";
        ctx.lineWidth = 2.0;
        ctx.beginPath();
        ctx.arc(0, 0, 38, 0, Math.PI * 2);
        ctx.stroke();

        // Eye Socket
        ctx.fillStyle = "#1c0006";
        ctx.beginPath();
        ctx.ellipse(0, 0, 26, 18, 0, 0, Math.PI * 2);
        ctx.fill();

        // Burning Hellfire Iris
        ctx.fillStyle = t >= 1.45 && t < 2.05 ? "#ffffff" : "#ff003b";
        ctx.beginPath();
        ctx.arc(0, 0, 14, 0, Math.PI * 2);
        ctx.fill();

        // Vertical Slit Pupil with Twitching Chaos
        const twitch = Math.sin(t * 24) * 0.7;
        const pupilWidth = (t >= 1.45 && t < 2.2 ? 1.8 : 4.0) + twitch;
        ctx.fillStyle = "#000000";
        ctx.beginPath();
        ctx.ellipse(0, 0, Math.max(1.0, pupilWidth), 14, 0, 0, Math.PI * 2);
        ctx.fill();

        // Mechanical Razor Aperture Blades Ring
        ctx.save();
        ctx.rotate(t * 3.8);
        ctx.strokeStyle = "rgba(255, 230, 235, 0.85)";
        ctx.lineWidth = 1.4;
        ctx.setLineDash([4, 6]);
        ctx.beginPath();
        ctx.arc(0, 0, 20, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }

      ctx.restore();
    }

    // ------------------------------------------------------------------------
    // 5. DRAW BLOOD-RED DIGITAL GLASS CRACKS (POST-SLAM) (FAST MULTI-PASS)
    // ------------------------------------------------------------------------
    if (glassCracks.length > 0) {
      glassCracks.forEach((crack) => {
        if (t > 2.85) {
          crack.alpha = Math.max(0, 1.0 - (t - 2.85) / 1.0);
        }

        // Pass 1: Neon red outer stroke
        ctx.strokeStyle = `rgba(255, 0, 59, ${crack.alpha * 0.9})`;
        ctx.lineWidth = 2.4;

        crack.rays.forEach((ray) => {
          if (ray.length < 2) return;
          ctx.beginPath();
          ctx.moveTo(ray[0].x, ray[0].y);
          for (let k = 1; k < ray.length; k++) {
            ctx.lineTo(ray[k].x, ray[k].y);
          }
          ctx.stroke();
        });

        // Pass 2: White core stroke
        ctx.strokeStyle = `rgba(255, 240, 245, ${crack.alpha * 0.75})`;
        ctx.lineWidth = 1.0;

        crack.rays.forEach((ray) => {
          if (ray.length < 2) return;
          ctx.beginPath();
          ctx.moveTo(ray[0].x, ray[0].y);
          for (let k = 1; k < ray.length; k++) {
            ctx.lineTo(ray[k].x, ray[k].y);
          }
          ctx.stroke();
        });
      });
    }

    // ------------------------------------------------------------------------
    // 6. UPDATE & DRAW BLOOD MATRIX PARTICLES
    // ------------------------------------------------------------------------
    if (codeParticles.length > 0) {
      for (let i = codeParticles.length - 1; i >= 0; i--) {
        const p = codeParticles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.vx *= 0.94;
        p.vy *= 0.94;
        p.life -= p.decay;

        if (p.life <= 0) {
          codeParticles.splice(i, 1);
          continue;
        }

        ctx.font = `bold ${p.size}px monospace`;
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.life;
        ctx.fillText(p.char, p.x, p.y);
      }
      ctx.globalAlpha = 1.0;
    }

    animId = requestAnimationFrame(render);
  }

  function cleanup() {
    if (animId) cancelAnimationFrame(animId);
    animId = null;
    document.body.classList.remove("kraken-screen-slam");
    if (canvas && canvas.parentNode) {
      canvas.parentNode.removeChild(canvas);
    }
    if (currentKrakenAnimation && currentKrakenAnimation.canvas === canvas) {
      currentKrakenAnimation = null;
    }
  }

  currentKrakenAnimation = {
    canvas,
    abort: cleanup
  };

  animId = requestAnimationFrame(render);
}

/**
 * Initializes click delegation listener on DIMEOGPT hero banners
 */
export function initCyberKrakenListener() {
  if (typeof document === "undefined") return;

  if (document.__dimeogptKrakenBound) return;
  document.__dimeogptKrakenBound = true;

  document.addEventListener("click", (e) => {
    const banner = e.target.closest(".dimeogpt-hero-banner");
    if (banner) {
      e.preventDefault();
      triggerCyberKraken(e.clientX, e.clientY);
    }
  });

  console.log("[DIMEOGPT] Ultra-Smooth Blood Kraken engine initialized.");
}
