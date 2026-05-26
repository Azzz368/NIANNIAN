// immersive-sun-bg.js - Replacement for silk-bg.js
(function () {
  if (typeof window === 'undefined') return;
  console.log('%c[silk-bg] v3 LOADED — sun glow + fbm flow', 'background:#ff6b6b;color:#fff;padding:2px 8px;border-radius:3px;font-weight:bold');

  // 等待 THREE 加载完成（CDN 可能慢，最多等 10 秒）
  var waited = 0;
  function waitForThree() {
    if (typeof THREE !== 'undefined') {
      console.log('[silk-bg] THREE ready after ' + waited + 'ms');
      start();
      return;
    }
    waited += 100;
    if (waited > 10000) {
      console.error('[silk-bg] THREE never loaded after 10s — CDN blocked?');
      return;
    }
    setTimeout(waitForThree, 100);
  }

  function start() {
    var canvas = document.getElementById('silkCanvas');
    if (!canvas) { console.warn('[silk-bg] #silkCanvas not found'); return; }

    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: false });
    } catch (e) {
      console.error('[silk-bg] WebGLRenderer ctor failed', e);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    var scene = new THREE.Scene();
    var camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    var fragmentShader = `
      uniform float uTime;
      uniform float uVolume;
      uniform vec2 uResolution;

      // 简单 2D 噪声 & FBm（用于更高级的光晕扰动）
      float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float noise(vec2 p){
        vec2 i = floor(p); vec2 f = fract(p);
        float a = hash(i); float b = hash(i + vec2(1.0, 0.0));
        float c = hash(i + vec2(0.0, 1.0)); float d = hash(i + vec2(1.0, 1.0));
        vec2 u = f * f * (3.0 - 2.0 * f);
        return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
      }
      float fbm(vec2 p) {
        float f = 0.0;
        float w = 0.5;
        for(int i = 0; i < 4; i++) {
          f += w * noise(p);
          p *= 2.0;
          w *= 0.5;
        }
        return f;
      }

      void main() {
        vec2 uv = gl_FragCoord.xy / uResolution.xy;
        uv = uv * 2.0 - 1.0;
        uv.x *= uResolution.x / uResolution.y;

        // 保持中心位于 0.5，整体依然挂在偏上方
        vec2 center = vec2(0.0, 0.5);
        vec2 p = uv - center;

        float dist = length(p);
        float angle = atan(p.y, p.x);

        // 高级感流体呼吸：分层正弦 + 余弦，幅度调大让闲置时也明显可见
        float idleBreath = sin(uTime * 1.2) * 0.05 + cos(uTime * 0.55) * 0.035;
        float voiceEnergy = smoothstep(0.01, 1.0, uVolume);

        // 保持现在的合适比例
        float baseRadius = 0.42;
        float targetRadius = baseRadius + idleBreath + voiceEnergy * 0.5;

        // 光感涟漪：加入流体噪声扰乱相位，让边缘像液态金属/极光持续蠕动
        // 即使没有 AI 说话，也有缓慢的基础涟漪（idleAmp）
        float idleAmp = 0.012;
        float flowOffset = fbm(p * 2.0 + vec2(uTime * 0.25)) * 0.12;
        float ripple1 = sin((dist + flowOffset) * 16.0 - uTime * 3.5) * (idleAmp + 0.025 * voiceEnergy);
        float ripple2 = cos((dist - flowOffset * 0.5) * 32.0 - uTime * 6.0) * (idleAmp * 0.4 + 0.01 * voiceEnergy);

        // 边缘非线性光晕：日冕般的"光丝"，闲置时也会缓慢漂动
        float edgeNoise = fbm(vec2(angle * 4.0 + uTime * 0.3, uTime * 0.6));
        float edgeWobble = (edgeNoise - 0.5) * (0.06 + voiceEnergy * 0.15);

        float dEff = dist + ripple1 + ripple2 + edgeWobble;

        // 极简疗愈系背景：暖米黄过渡到微微淡蓝，增加微弱的全屏流光
        float globalFlow = fbm(uv + uTime * 0.05) * 0.1;
        vec3 bgWarm = vec3(0.94, 0.95, 0.98);   // 近白偏冷蓝
        vec3 bgCool = vec3(0.82, 0.90, 0.97);   // 淡蓝
        vec3 bgColor = mix(bgWarm, bgCool, clamp(dEff * 0.45 + globalFlow, 0.0, 1.0));

        // 太阳/光团 细腻发光：黄 -> 暖橙 -> 樱花粉 -> 白散光
        vec3 colCore = vec3(1.0, 0.98, 0.5);
        vec3 colMid1 = vec3(1.0, 0.70, 0.35);
        vec3 colMid2 = vec3(1.0, 0.50, 0.58);
        vec3 colGlow = vec3(1.0, 0.98, 0.96);

        float d = dEff / targetRadius;
        vec3 color = bgColor;

        // 大气散射效果 (Atmospheric scattering)
        // 即使没有AI说话，外围也有一层非常柔和的泛光
        float atmosphericGlow = exp(-dEff * 1.5) * (0.15 + voiceEnergy * 0.3);
        color += mix(colMid1, vec3(1.0), 0.5) * atmosphericGlow;

        // 内部光核
        if (d < 2.0) {
            float fCore = pow(clamp(1.0 - d/0.4, 0.0, 1.0), 1.5);
            float fMid1 = pow(clamp(1.0 - d/0.7, 0.0, 1.0), 1.2);
            float fMid2 = pow(clamp(1.0 - d/1.1, 0.0, 1.0), 1.0);
            float fGlow = smoothstep(2.0, 0.8, d);

            vec3 sunColor = mix(colGlow, colMid2, fMid2);
            sunColor = mix(sunColor, colMid1, fMid1);
            sunColor = mix(sunColor, colCore, fCore);

            // 当音量大时，核心增加额外的曝光（类似于绽放效果）
            sunColor += vec3(voiceEnergy * 0.4) * fCore;

            // 平滑地将太阳颜色盖在背景上
            color = mix(color, sunColor, fGlow * 0.9);
        }

        // 增加一点非常微妙的全局胶片曝光噪声防色带
        float dithering = (hash(gl_FragCoord.xy) - 0.5) * 0.02;
        color += vec3(dithering);

        // ── 白色光晕环 ──
        // 环半径随闲置呼吸 + AI 音量同步膨胀
        float ringRadius = targetRadius * 1.55 + voiceEnergy * 0.25;
        float ringWidth  = 0.04 + voiceEnergy * 0.06;   // 音量越大越宽
        // 加点噪声让环边缘不规则
        float ringNoise  = fbm(vec2(angle * 5.0 + uTime * 0.4, uTime * 0.3)) * 0.05;
        float ringDist   = abs(dist - ringRadius + ringNoise);
        float ringAlpha  = smoothstep(ringWidth, 0.0, ringDist);
        // 闲置时有 0.25 基础不透明度，说话时增至 0.7
        float ringOpacity = ringAlpha * (0.25 + voiceEnergy * 0.45);
        color = mix(color, vec3(1.0, 1.0, 1.0), ringOpacity);

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

    // 编译诊断：尝试强制编译，若失败把错误打到控制台
    try {
      renderer.compile(scene, camera);
      console.log('[silk-bg] shader compiled OK');
    } catch (e) {
      console.error('[silk-bg] shader compile FAILED', e);
    }

    var resize = function () {
      var w = window.innerWidth, h = window.innerHeight;
      renderer.setSize(w, h);
      material.uniforms.uResolution.value.set(w, h);
    };
    window.addEventListener('resize', resize);
    resize();

    var currentVolume = 0;
    var clock = new THREE.Clock();

    function render() {
      requestAnimationFrame(render);
      var dt = clock.getDelta();
      material.uniforms.uTime.value += dt;

      // AI 音量驱动：增加了一点非线性，让很小的声音也能引发微亮，且封顶柔和
      var raw = window.aiActiveVolume || 0;
      var targetVol = Math.min(1.2, Math.pow(raw + 0.001, 0.45) * 4.5 - 0.25);
      if (targetVol < 0) targetVol = 0;

      // 攻击快、衰减慢，更像高级音频包络
      var speed = (targetVol > currentVolume) ? 18.0 : 4.0;
      currentVolume += (targetVol - currentVolume) * Math.min(1.0, dt * speed);
      material.uniforms.uVolume.value = currentVolume;

      // 同步到 CSS：让文字也跟随轻微缩放发光
      var aiText = document.getElementById('immersiveAiText');
      if (aiText) aiText.style.setProperty('--ai-vol', currentVolume.toFixed(3));

      renderer.render(scene, camera);
    }
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitForThree);
  } else {
    waitForThree();
  }
})();
