// immersive-sun-bg.js — sun glow + fbm flow + tunable panel (v4)
(function () {
  if (typeof window === 'undefined') return;
  console.log('%c[silk-bg] v4 LOADED — tunable panel', 'background:#ff6b6b;color:#fff;padding:2px 8px;border-radius:3px;font-weight:bold');

  var DEFAULTS = {
    centerX: 0.89, centerY: 1.00, baseRadius: 0.33,
    breathAmp1: 0.035, breathSpeed1: 0.75, breathAmp2: 0.07, breathSpeed2: 0.30,
    flowOffsetScale: 0.06, flowSpeed: 0.51,
    rippleFreq1: 9.0, rippleSpeed1: 5.9, rippleFreq2: 44.0, rippleSpeed2: 6.0,
    rippleIdleAmp: 0.012, rippleVoiceAmp: 0.025,
    edgeWobbleAmp: 0.06, edgeWobbleVoice: 0.15, edgeWobbleSpeedT: 0.30, edgeWobbleSpeedR: 0.60, edgeAngularFreq: 4.0,
    atmosphericBase: 0.12, atmosphericVoice: 0.24, atmosphericDecay: 1.50,
    coreFalloff1: 0.40, coreFalloff2: 0.70, coreFalloff3: 1.10,
    coreGlowInner: 1.12, coreGlowOuter: 2.00, coreMixWeight: 0.79, coreBloomVoice: 0.57,
    voiceRadiusGain: 0.50, volumeGain: 4.50, volumeBias: 0.06, volumePow: 0.45, volumeMax: 1.05,
    attackSpeed: 18.0, decaySpeed: 5.5,
    ringRadiusMul: 1.64, ringVoiceExpand: 0.165, ringWidthBase: 0.03, ringWidthVoice: 0.06,
    ringNoiseAmp: 0.05, ringOpacityBase: 0.25, ringOpacityVoice: 0.45,
    bgFlowAmp: 0.11, bgFlowSpeed: 0.05, bgMixGain: 0.42, ditherAmp: 0.02,
    colCore: '#fffffa', colMid1: '#f9d6a4', colMid2: '#ecd8a1', colGlow: '#fffaf5',
    bgWarm: '#f0f2fa', bgCool: '#ffeacc', ringColor: '#ffffff'
  };

  var GROUPS = [
    ['Sphere',     ['centerX','centerY','baseRadius']],
    ['Breath',     ['breathAmp1','breathSpeed1','breathAmp2','breathSpeed2']],
    ['Ripple',     ['flowOffsetScale','flowSpeed','rippleFreq1','rippleSpeed1','rippleFreq2','rippleSpeed2','rippleIdleAmp','rippleVoiceAmp']],
    ['Edge',       ['edgeWobbleAmp','edgeWobbleVoice','edgeWobbleSpeedT','edgeWobbleSpeedR','edgeAngularFreq']],
    ['Atmosphere', ['atmosphericBase','atmosphericVoice','atmosphericDecay']],
    ['Core',       ['coreFalloff1','coreFalloff2','coreFalloff3','coreGlowInner','coreGlowOuter','coreMixWeight','coreBloomVoice']],
    ['Volume',     ['voiceRadiusGain','volumeGain','volumeBias','volumePow','volumeMax','attackSpeed','decaySpeed']],
    ['Ring',       ['ringRadiusMul','ringVoiceExpand','ringWidthBase','ringWidthVoice','ringNoiseAmp','ringOpacityBase','ringOpacityVoice']],
    ['Background', ['bgFlowAmp','bgFlowSpeed','bgMixGain','ditherAmp']],
    ['Colors',     ['colCore','colMid1','colMid2','colGlow','bgWarm','bgCool','ringColor']]
  ];

  var RANGES = {
    centerX:[-1,1,0.01], centerY:[-1,1,0.01], baseRadius:[0.05,1.2,0.01],
    breathAmp1:[0,0.3,0.005], breathSpeed1:[0,5,0.05], breathAmp2:[0,0.3,0.005], breathSpeed2:[0,5,0.05],
    flowOffsetScale:[0,0.6,0.005], flowSpeed:[0,2,0.01],
    rippleFreq1:[0,80,0.5], rippleSpeed1:[0,15,0.1], rippleFreq2:[0,120,0.5], rippleSpeed2:[0,20,0.1],
    rippleIdleAmp:[0,0.1,0.001], rippleVoiceAmp:[0,0.2,0.001],
    edgeWobbleAmp:[0,0.3,0.005], edgeWobbleVoice:[0,0.6,0.005], edgeWobbleSpeedT:[0,3,0.02], edgeWobbleSpeedR:[0,3,0.02],
    edgeAngularFreq:[0,20,0.1],
    atmosphericBase:[0,1,0.005], atmosphericVoice:[0,2,0.01], atmosphericDecay:[0,6,0.05],
    coreFalloff1:[0.05,2,0.01], coreFalloff2:[0.05,3,0.01], coreFalloff3:[0.05,4,0.01],
    coreGlowInner:[0,4,0.02], coreGlowOuter:[0,8,0.05], coreMixWeight:[0,1.5,0.01], coreBloomVoice:[0,2,0.01],
    voiceRadiusGain:[0,2,0.01], volumeGain:[0,15,0.1], volumeBias:[-2,2,0.01], volumePow:[0.05,2,0.01], volumeMax:[0.2,3,0.05],
    attackSpeed:[1,60,0.5], decaySpeed:[0.5,40,0.5],
    ringRadiusMul:[0.5,3,0.01], ringVoiceExpand:[0,1,0.005], ringWidthBase:[0,0.3,0.002], ringWidthVoice:[0,0.5,0.002],
    ringNoiseAmp:[0,0.3,0.002], ringOpacityBase:[0,1,0.01], ringOpacityVoice:[0,1.5,0.01],
    bgFlowAmp:[0,0.6,0.005], bgFlowSpeed:[0,1,0.01], bgMixGain:[0,2,0.01], ditherAmp:[0,0.1,0.001]
  };

  var COLOR_KEYS = ['colCore','colMid1','colMid2','colGlow','bgWarm','bgCool','ringColor'];
  var STORAGE_KEY = 'silkbg_params_v1';
  var PARAMS = Object.assign({}, DEFAULTS);
  try {
    var saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    Object.keys(saved).forEach(function (k) { if (k in PARAMS) PARAMS[k] = saved[k]; });
  } catch (e) {}

  function savePersist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(PARAMS)); } catch (e) {}
  }

  function hexToVec3(hex) {
    var h = (hex || '#000').replace('#','');
    if (h.length === 3) h = h.split('').map(function(c){return c+c;}).join('');
    return [parseInt(h.substr(0,2),16)/255, parseInt(h.substr(2,2),16)/255, parseInt(h.substr(4,2),16)/255];
  }

  var waited = 0;
  function waitForThree() {
    if (typeof THREE !== 'undefined') { start(); return; }
    waited += 100;
    if (waited > 10000) { console.error('[silk-bg] THREE never loaded'); return; }
    setTimeout(waitForThree, 100);
  }

  function start() {
    var canvas = document.getElementById('silkCanvas');
    if (!canvas) { console.warn('[silk-bg] #silkCanvas not found'); return; }

    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: false });
    } catch (e) { console.error('[silk-bg] WebGLRenderer ctor failed', e); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    var scene = new THREE.Scene();
    var camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    var fragmentShader = [
      'precision highp float;',
      'uniform float uTime; uniform float uVolume; uniform vec2 uResolution;',
      'uniform vec2 uCenter; uniform float uBaseRadius;',
      'uniform vec4 uBreath;',
      'uniform float uFlowOffsetScale, uFlowSpeed;',
      'uniform vec4 uRipple1;',
      'uniform vec2 uRippleAmp;',
      'uniform vec4 uEdge;',
      'uniform float uEdgeFreq;',
      'uniform vec3 uAtmo;',
      'uniform vec4 uCoreF;',
      'uniform vec3 uCoreG;',
      'uniform float uVoiceRadiusGain;',
      'uniform vec4 uRing;',
      'uniform vec3 uRingB;',
      'uniform vec3 uBg;',
      'uniform float uDither;',
      'uniform vec3 uColCore, uColMid1, uColMid2, uColGlow, uBgWarm, uBgCool, uRingColor;',
      'float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
      'float noise(vec2 p){',
      '  vec2 i=floor(p); vec2 f=fract(p);',
      '  float a=hash(i), b=hash(i+vec2(1.0,0.0)), c=hash(i+vec2(0.0,1.0)), d=hash(i+vec2(1.0,1.0));',
      '  vec2 u=f*f*(3.0-2.0*f);',
      '  return mix(a,b,u.x)+(c-a)*u.y*(1.0-u.x)+(d-b)*u.x*u.y;',
      '}',
      'float fbm(vec2 p){ float f=0.0,w=0.5; for(int i=0;i<4;i++){ f+=w*noise(p); p*=2.0; w*=0.5;} return f; }',
      'void main(){',
      '  vec2 uv = gl_FragCoord.xy / uResolution.xy;',
      '  uv = uv*2.0 - 1.0;',
      '  uv.x *= uResolution.x / uResolution.y;',
      '  vec2 p = uv - uCenter;',
      '  float dist = length(p);',
      '  float angle = atan(p.y, p.x);',
      '  float idleBreath = sin(uTime*uBreath.y)*uBreath.x + cos(uTime*uBreath.w)*uBreath.z;',
      '  float voiceEnergy = smoothstep(0.01, 1.0, uVolume);',
      '  float targetRadius = uBaseRadius + idleBreath + voiceEnergy * uVoiceRadiusGain;',
      '  float flowOffset = fbm(p*2.0 + vec2(uTime*uFlowSpeed)) * uFlowOffsetScale;',
      '  float ripple1 = sin((dist + flowOffset) * uRipple1.x - uTime*uRipple1.y) * (uRippleAmp.x + uRippleAmp.y * voiceEnergy);',
      '  float ripple2 = cos((dist - flowOffset*0.5) * uRipple1.z - uTime*uRipple1.w) * (uRippleAmp.x*0.4 + uRippleAmp.y*0.4 * voiceEnergy);',
      '  float edgeNoise = fbm(vec2(angle*uEdgeFreq + uTime*uEdge.z, uTime*uEdge.w));',
      '  float edgeWobble = (edgeNoise - 0.5) * (uEdge.x + voiceEnergy * uEdge.y);',
      '  float dEff = dist + ripple1 + ripple2 + edgeWobble;',
      '  float globalFlow = fbm(uv + uTime*uBg.y) * uBg.x;',
      '  vec3 bgColor = mix(uBgWarm, uBgCool, clamp(dEff*uBg.z + globalFlow, 0.0, 1.0));',
      '  float d = dEff / max(targetRadius, 0.0001);',
      '  vec3 color = bgColor;',
      '  float atmosphericGlow = exp(-dEff * uAtmo.z) * (uAtmo.x + voiceEnergy * uAtmo.y);',
      '  color += mix(uColMid1, vec3(1.0), 0.5) * atmosphericGlow;',
      '  if (d < 2.0) {',
      '    float fCore = pow(clamp(1.0 - d/uCoreF.x, 0.0, 1.0), 1.5);',
      '    float fMid1 = pow(clamp(1.0 - d/uCoreF.y, 0.0, 1.0), 1.2);',
      '    float fMid2 = pow(clamp(1.0 - d/uCoreF.z, 0.0, 1.0), 1.0);',
      '    float fGlow = smoothstep(uCoreG.y, uCoreG.x, d);',
      '    vec3 sunColor = mix(uColGlow, uColMid2, fMid2);',
      '    sunColor = mix(sunColor, uColMid1, fMid1);',
      '    sunColor = mix(sunColor, uColCore, fCore);',
      '    sunColor += vec3(voiceEnergy * uCoreG.z) * fCore;',
      '    color = mix(color, sunColor, fGlow * uCoreF.w);',
      '  }',
      '  float dithering = (hash(gl_FragCoord.xy) - 0.5) * uDither;',
      '  color += vec3(dithering);',
      '  float ringRadius = targetRadius * uRing.x + voiceEnergy * uRing.y;',
      '  float ringWidth  = uRing.z + voiceEnergy * uRing.w;',
      '  float ringNoise  = fbm(vec2(angle*5.0 + uTime*0.4, uTime*0.3)) * uRingB.x;',
      '  float ringDist   = abs(dist - ringRadius + ringNoise);',
      '  float ringAlpha  = smoothstep(max(ringWidth,0.0001), 0.0, ringDist);',
      '  float ringOpacity = ringAlpha * (uRingB.y + voiceEnergy * uRingB.z);',
      '  color = mix(color, uRingColor, ringOpacity);',
      '  gl_FragColor = vec4(color, 1.0);',
      '}'
    ].join('\n');

    var vertexShader = 'void main(){ gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }';

    var uniforms = {
      uTime: { value: 0 }, uVolume: { value: 0 },
      uResolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
      uCenter: { value: new THREE.Vector2() }, uBaseRadius: { value: 0 },
      uBreath: { value: new THREE.Vector4() },
      uFlowOffsetScale: { value: 0 }, uFlowSpeed: { value: 0 },
      uRipple1: { value: new THREE.Vector4() }, uRippleAmp: { value: new THREE.Vector2() },
      uEdge: { value: new THREE.Vector4() }, uEdgeFreq: { value: 0 },
      uAtmo: { value: new THREE.Vector3() },
      uCoreF: { value: new THREE.Vector4() }, uCoreG: { value: new THREE.Vector3() },
      uVoiceRadiusGain: { value: 0 },
      uRing: { value: new THREE.Vector4() }, uRingB: { value: new THREE.Vector3() },
      uBg: { value: new THREE.Vector3() }, uDither: { value: 0 },
      uColCore: { value: new THREE.Vector3() }, uColMid1: { value: new THREE.Vector3() },
      uColMid2: { value: new THREE.Vector3() }, uColGlow: { value: new THREE.Vector3() },
      uBgWarm: { value: new THREE.Vector3() }, uBgCool: { value: new THREE.Vector3() },
      uRingColor: { value: new THREE.Vector3() }
    };

    function syncUniforms() {
      var u = uniforms, P = PARAMS;
      u.uCenter.value.set(P.centerX, P.centerY);
      u.uBaseRadius.value = P.baseRadius;
      u.uBreath.value.set(P.breathAmp1, P.breathSpeed1, P.breathAmp2, P.breathSpeed2);
      u.uFlowOffsetScale.value = P.flowOffsetScale;
      u.uFlowSpeed.value = P.flowSpeed;
      u.uRipple1.value.set(P.rippleFreq1, P.rippleSpeed1, P.rippleFreq2, P.rippleSpeed2);
      u.uRippleAmp.value.set(P.rippleIdleAmp, P.rippleVoiceAmp);
      u.uEdge.value.set(P.edgeWobbleAmp, P.edgeWobbleVoice, P.edgeWobbleSpeedT, P.edgeWobbleSpeedR);
      u.uEdgeFreq.value = P.edgeAngularFreq;
      u.uAtmo.value.set(P.atmosphericBase, P.atmosphericVoice, P.atmosphericDecay);
      u.uCoreF.value.set(P.coreFalloff1, P.coreFalloff2, P.coreFalloff3, P.coreMixWeight);
      u.uCoreG.value.set(P.coreGlowInner, P.coreGlowOuter, P.coreBloomVoice);
      u.uVoiceRadiusGain.value = P.voiceRadiusGain;
      u.uRing.value.set(P.ringRadiusMul, P.ringVoiceExpand, P.ringWidthBase, P.ringWidthVoice);
      u.uRingB.value.set(P.ringNoiseAmp, P.ringOpacityBase, P.ringOpacityVoice);
      u.uBg.value.set(P.bgFlowAmp, P.bgFlowSpeed, P.bgMixGain);
      u.uDither.value = P.ditherAmp;
      COLOR_KEYS.forEach(function (k) {
        var v = hexToVec3(P[k]);
        var name = 'u' + k.charAt(0).toUpperCase() + k.slice(1);
        if (u[name]) u[name].value.set(v[0], v[1], v[2]);
      });
    }
    syncUniforms();

    var material = new THREE.ShaderMaterial({ vertexShader: vertexShader, fragmentShader: fragmentShader, uniforms: uniforms });
    var plane = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    scene.add(plane);

    try { renderer.compile(scene, camera); console.log('[silk-bg] shader compiled OK'); }
    catch (e) { console.error('[silk-bg] shader compile FAILED', e); }

    function resize() {
      var w = window.innerWidth, h = window.innerHeight;
      renderer.setSize(w, h);
      uniforms.uResolution.value.set(w, h);
    }
    window.addEventListener('resize', resize); resize();

    var currentVolume = 0;
    var clock = new THREE.Clock();
    function render() {
      requestAnimationFrame(render);
      var dt = clock.getDelta();
      uniforms.uTime.value += dt;

      var raw = window.aiActiveVolume || 0;
      var targetVol = Math.min(PARAMS.volumeMax, Math.pow(raw + 0.001, PARAMS.volumePow) * PARAMS.volumeGain - PARAMS.volumeBias);
      if (targetVol < 0) targetVol = 0;
      var speed = (targetVol > currentVolume) ? PARAMS.attackSpeed : PARAMS.decaySpeed;
      currentVolume += (targetVol - currentVolume) * Math.min(1.0, dt * speed);
      uniforms.uVolume.value = currentVolume;

      var aiText = document.getElementById('immersiveAiText');
      if (aiText) aiText.style.setProperty('--ai-vol', currentVolume.toFixed(3));

      renderer.render(scene, camera);
    }
    render();

    buildPanel(syncUniforms);
  }

  function buildPanel(syncUniforms) {
    if (document.getElementById('silkbgPanel')) return;

    var style = document.createElement('style');
    style.textContent = [
      '#silkbgPanel{position:fixed;top:12px;right:12px;width:340px;max-height:88vh;overflow-y:auto;',
      '  background:rgba(20,20,28,.92);color:#eef1f7;font:12px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;',
      '  border-radius:10px;padding:10px 12px;box-shadow:0 8px 32px rgba(0,0,0,.4);z-index:99999;',
      '  backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.08);display:none;}',
      '#silkbgPanel.open{display:block;}',
      '#silkbgPanel h4{margin:10px 0 6px;font-size:11px;letter-spacing:.5px;color:#ffb359;text-transform:uppercase;font-weight:600;}',
      '#silkbgPanel h4:first-of-type{margin-top:4px;}',
      '#silkbgPanel .row{display:flex;align-items:center;gap:8px;margin:3px 0;}',
      '#silkbgPanel .row label{flex:0 0 110px;font-size:11px;color:#aab3c5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
      '#silkbgPanel .row input[type=range]{flex:1;height:14px;}',
      '#silkbgPanel .row .val{flex:0 0 56px;text-align:right;font:11px/1 SF Mono,Consolas,monospace;color:#9be7c4;}',
      '#silkbgPanel .row input[type=color]{width:48px;height:22px;border:0;background:transparent;cursor:pointer;padding:0;}',
      '#silkbgPanel .toolbar{display:flex;gap:6px;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,.1);position:sticky;top:0;background:rgba(20,20,28,.95);z-index:2;}',
      '#silkbgPanel button{flex:1;padding:6px 8px;background:#3b82f6;border:0;border-radius:5px;color:#fff;font-size:11px;cursor:pointer;font-weight:600;}',
      '#silkbgPanel button.sec{background:#475569;}',
      '#silkbgPanel button.close{flex:0 0 28px;background:#64748b;}',
      '#silkbgPanel button:hover{filter:brightness(1.15);}',
      '#silkbgPanel .hint{font-size:10px;color:#7b8294;margin-top:8px;text-align:center;}',
      '#silkbgToggle{position:fixed;top:12px;right:12px;width:36px;height:36px;border-radius:50%;',
      '  background:rgba(20,20,28,.85);color:#ffb359;border:1px solid rgba(255,255,255,.18);',
      '  font-size:18px;cursor:pointer;z-index:99998;display:flex;align-items:center;justify-content:center;',
      '  box-shadow:0 4px 12px rgba(0,0,0,.3);}',
      '#silkbgToggle:hover{background:rgba(40,40,52,.95);transform:scale(1.05);}'
    ].join('');
    document.head.appendChild(style);

    var toggle = document.createElement('button');
    toggle.id = 'silkbgToggle';
    toggle.title = 'Halo debug panel (toggle with ` key)';
    toggle.textContent = '\u2699';
    document.body.appendChild(toggle);

    var panel = document.createElement('div');
    panel.id = 'silkbgPanel';
    document.body.appendChild(panel);

    var toolbar = document.createElement('div');
    toolbar.className = 'toolbar';
    toolbar.innerHTML =
      '<button id="silkbgReset" class="sec">↺ 重置</button>' +
      '<button id="silkbgExport">📋 导出 JSON</button>' +
      '<button id="silkbgClose" class="close">×</button>';
    panel.appendChild(toolbar);

    var rows = {};

    GROUPS.forEach(function (group) {
      var h4 = document.createElement('h4');
      h4.textContent = group[0];
      panel.appendChild(h4);
      group[1].forEach(function (key) {
        var row = document.createElement('div');
        row.className = 'row';
        var label = document.createElement('label');
        label.textContent = key;
        label.title = key;
        row.appendChild(label);

        var input, val;
        if (COLOR_KEYS.indexOf(key) >= 0) {
          input = document.createElement('input');
          input.type = 'color';
          input.value = PARAMS[key];
          row.appendChild(input);
          val = document.createElement('span');
          val.className = 'val';
          val.textContent = PARAMS[key];
          row.appendChild(val);
          input.addEventListener('input', function () {
            PARAMS[key] = input.value;
            val.textContent = input.value;
            syncUniforms(); savePersist();
          });
        } else {
          var r = RANGES[key] || [0, 1, 0.01];
          input = document.createElement('input');
          input.type = 'range';
          input.min = r[0]; input.max = r[1]; input.step = r[2];
          input.value = PARAMS[key];
          row.appendChild(input);
          val = document.createElement('span');
          val.className = 'val';
          val.textContent = (+PARAMS[key]).toFixed(3);
          row.appendChild(val);
          input.addEventListener('input', function () {
            var v = parseFloat(input.value);
            PARAMS[key] = v;
            val.textContent = v.toFixed(3);
            syncUniforms(); savePersist();
          });
        }
        rows[key] = { input: input, val: val };
        panel.appendChild(row);
      });
    });

    var hint = document.createElement('div');
    hint.className = 'hint';
    hint.textContent = '按 ` 键 (Tab 上方) 切换面板 · 修改自动保存';
    panel.appendChild(hint);

    function openPanel() { panel.classList.add('open'); toggle.style.display = 'none'; }
    function closePanel() { panel.classList.remove('open'); toggle.style.display = 'flex'; }

    document.getElementById('silkbgClose').onclick = closePanel;
    toggle.onclick = openPanel;
    document.addEventListener('keydown', function (e) {
      if (e.key === '`' || e.key === '~') {
        if (panel.classList.contains('open')) closePanel(); else openPanel();
      }
    });

    document.getElementById('silkbgReset').onclick = function () {
      if (!confirm('恢复全部默认值？')) return;
      Object.keys(DEFAULTS).forEach(function (k) { PARAMS[k] = DEFAULTS[k]; });
      Object.keys(rows).forEach(function (k) {
        rows[k].input.value = PARAMS[k];
        rows[k].val.textContent = COLOR_KEYS.indexOf(k) >= 0 ? PARAMS[k] : (+PARAMS[k]).toFixed(3);
      });
      syncUniforms(); savePersist();
    };

    document.getElementById('silkbgExport').onclick = function () {
      var pretty = JSON.stringify(PARAMS, null, 2);
      var done = function () {
        var btn = document.getElementById('silkbgExport');
        var old = btn.textContent; btn.textContent = '✓ 已复制';
        setTimeout(function () { btn.textContent = old; }, 1500);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(pretty).then(done).catch(function () {
          console.log('[silk-bg] PARAMS:\n' + pretty);
          alert('已打印到控制台 (F12)');
        });
      } else {
        console.log('[silk-bg] PARAMS:\n' + pretty);
        alert('已打印到控制台 (F12)');
      }
    };

    window.silkbgParams = PARAMS;
    window.silkbgSync = syncUniforms;
    console.log('[silk-bg] panel ready. Press ` to open, or click top-right gear.');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitForThree);
  } else {
    waitForThree();
  }
})();
