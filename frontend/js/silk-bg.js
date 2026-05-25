// immersive-sun-bg.js - Replacement for silk-bg.js
(function () {
  if (typeof window === 'undefined') return;
  function start() {
    var canvas = document.getElementById('silkCanvas');
    if (!canvas) { return; }
    if (typeof THREE === 'undefined') { return; }

    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: false });
    } catch (e) {
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    var scene = new THREE.Scene();
    var camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    var fragmentShader = `
      uniform float uTime;
      uniform float uVolume;
      uniform vec2 uResolution;

      // 简单 2D 噪声（用于光晕扰动）
      float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float noise(vec2 p){
        vec2 i = floor(p); vec2 f = fract(p);
        float a = hash(i);
        float b = hash(i + vec2(1.0, 0.0));
        float c = hash(i + vec2(0.0, 1.0));
        float d = hash(i + vec2(1.0, 1.0));
        vec2 u = f * f * (3.0 - 2.0 * f);
        return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
      }

      void main() {
        vec2 uv = gl_FragCoord.xy / uResolution.xy;
        uv = uv * 2.0 - 1.0;
        uv.x *= uResolution.x / uResolution.y;

        // 光晕中心：大幅上移到屏幕外，只露出底部柔光
        vec2 center = vec2(0.0, 0.5);
        vec2 p = uv - center;

        float dist = length(p);
        float angle = atan(p.y, p.x);

        // 基础半径（已缩小约 50%）
        float baseRadius = 0.42;
        float idleBreath = sin(uTime * 1.8) * 0.012;
        float voicePulse = uVolume * 0.55;          // 主缩放：跟随 AI 音量
        float targetRadius = baseRadius + idleBreath + voicePulse;

        // 多层涟漪：低频大波 + 高频小波（仅在 AI 说话时显现）
        float ripple1 = sin(dist * 22.0 - uTime * 5.0) * 0.022 * uVolume;
        float ripple2 = sin(dist * 50.0 - uTime * 9.0) * 0.010 * uVolume;
        // 边缘扰动噪声（让光环呼吸时不那么"规则"）
        float n = noise(vec2(angle * 3.0 + uTime * 0.7, uTime * 0.4));
        float edgeWobble = (n - 0.5) * 0.03 * (0.4 + uVolume * 1.5);

        float dEff = dist + ripple1 + ripple2 + edgeWobble;

        // 背景：暖米黄 -> 淡绿（保留原有静谧氛围）
        vec3 bgColor = mix(vec3(0.96, 0.93, 0.82), vec3(0.78, 0.90, 0.78), clamp(dist * 0.6, 0.0, 1.0));

        // 太阳配色：核心亮黄 -> 橙 -> 粉红 -> 外圈白光
        vec3 colCore = vec3(1.0, 0.96, 0.32);
        vec3 colMid1 = vec3(1.0, 0.62, 0.22);
        vec3 colMid2 = vec3(1.0, 0.42, 0.48);
        vec3 colGlow = vec3(1.0, 0.98, 0.96);

        float d = dEff / targetRadius;
        vec3 color = bgColor;

        // 整体外晕（随音量增大变亮）
        float outerGlow = smoothstep(2.2, 0.0, dEff) * (0.18 + uVolume * 0.6);
        color += vec3(1.0, 0.78, 0.5) * outerGlow;

        if (d < 1.8) {
            float fCore = smoothstep(0.35, 0.0, d);
            float fMid1 = smoothstep(0.65, 0.2, d);
            float fMid2 = smoothstep(0.95, 0.5, d);
            float fGlow = smoothstep(1.8, 0.8, d);

            vec3 sunColor = mix(colGlow, colMid2, fMid2);
            sunColor = mix(sunColor, colMid1, fMid1);
            sunColor = mix(sunColor, colCore, fCore);

            // 核心高亮：音量越大越"通透"
            sunColor += vec3(uVolume * 0.5) * fCore;

            color = mix(color, sunColor, fGlow);
        }

        gl_FragColor = vec4(color, 1.0);
      }
    `;

    var vertexShader = `
      void main() {
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `;

    var material = new THREE.ShaderMaterial({
      vertexShader: vertexShader,
      fragmentShader: fragmentShader,
      uniforms: {
        uTime: { value: 0 },
        uVolume: { value: 0 },
        uResolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) }
      }
    });

    var plane = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    scene.add(plane);

    var resize = function () {
      var w = window.innerWidth, h = window.innerHeight;
      renderer.setSize(w, h);
      material.uniforms.uResolution.value.set(w, h);
    };
    window.addEventListener('resize', resize);
    resize();

    var currentVolume = 0;
    var clock = new THREE.Clock();

    // 临时调试：右上角显示 AI 音量条（确认数据是否流通）
    var dbg = document.createElement('div');
    dbg.id = '__volDbg';
    dbg.style.cssText = 'position:fixed;top:8px;right:8px;width:140px;height:10px;background:rgba(0,0,0,0.25);border:1px solid #fff8;z-index:9999;pointer-events:none;';
    var dbgBar = document.createElement('div');
    dbgBar.style.cssText = 'height:100%;width:0;background:linear-gradient(90deg,#ffeb3b,#ff5722);transition:width 0.05s;';
    dbg.appendChild(dbgBar);
    document.body.appendChild(dbg);

    function render() {
      requestAnimationFrame(render);
      var dt = clock.getDelta();
      material.uniforms.uTime.value += dt;

      // AI 音量驱动：rms 通常 0.005~0.15，需要强放大
      var raw = window.aiActiveVolume || 0;
      var targetVol = Math.min(1.5, Math.pow(raw, 0.4) * 6.0);

      // 攻击快、衰减慢，更像音频包络（envelope follower）
      var speed = (targetVol > currentVolume) ? 22.0 : 5.0;
      currentVolume += (targetVol - currentVolume) * Math.min(1.0, dt * speed);
      material.uniforms.uVolume.value = currentVolume;

      // 调试条
      if (dbgBar) dbgBar.style.width = Math.min(100, currentVolume * 80).toFixed(1) + '%';

      // 同步到 CSS：让文字也跟随轻微缩放发光
      var aiText = document.getElementById('immersiveAiText');
      if (aiText) aiText.style.setProperty('--ai-vol', currentVolume.toFixed(3));

      renderer.render(scene, camera);
    }
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
