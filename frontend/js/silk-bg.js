// immersive-sun-bg.js — sun glow + fbm flow (v4)
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

      // ── 手机端（≤768px 竖屏）：光球偏右上方 + 缩小半径
      var isMobile = w <= 768 && h > w;
      if (isMobile) {
        uniforms.uCenter.value.set(0.54, 1.25);  // 右移 + 上移
        uniforms.uBaseRadius.value = 0.22;
      } else {
        uniforms.uCenter.value.set(PARAMS.centerX, PARAMS.centerY);
        uniforms.uBaseRadius.value = PARAMS.baseRadius;
      }
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
  }


  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitForThree);
  } else {
    waitForThree();
  }
})();
