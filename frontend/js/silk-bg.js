// silk-bg.js — Three.js 金纹丝绸背景（增强对比版）
(function () {
  if (typeof window === 'undefined') return;
  function start() {
    var canvas = document.getElementById('silkCanvas');
    if (!canvas) { console.warn('[silk] canvas #silkCanvas not found'); return; }
    if (typeof THREE === 'undefined') {
      console.error('[silk] THREE 未加载，回退到 CSS 渐变');
      document.body.style.background = 'linear-gradient(135deg,#F4ECDB 0%,#EFE3C9 50%,#F4ECDB 100%)';
      return;
    }
    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: false });
    } catch (e) {
      console.error('[silk] WebGL 不可用', e);
      document.body.style.background = 'linear-gradient(135deg,#F4ECDB 0%,#EFE3C9 50%,#F4ECDB 100%)';
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0xF4ECDB, 1);

    var scene  = new THREE.Scene();
    var camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, 10);
    camera.position.z = 1;

    var geo = new THREE.PlaneGeometry(2, 2, 220, 220);

    var vsh = [
      'uniform float uTime;',
      'varying vec2 vUv;',
      'varying float vWave;',
      'vec2 hash2(vec2 p){',
      '  p = vec2(dot(p,vec2(127.1,311.7)), dot(p,vec2(269.5,183.3)));',
      '  return -1.0 + 2.0*fract(sin(p)*43758.5453);',
      '}',
      'float noise(vec2 p){',
      '  vec2 i=floor(p); vec2 f=fract(p);',
      '  vec2 u=f*f*(3.0-2.0*f);',
      '  return mix(mix(dot(hash2(i),f), dot(hash2(i+vec2(1,0)),f-vec2(1,0)),u.x),',
      '             mix(dot(hash2(i+vec2(0,1)),f-vec2(0,1)), dot(hash2(i+vec2(1,1)),f-vec2(1,1)),u.x), u.y);',
      '}',
      'void main(){',
      '  vUv = uv;',
      '  vec3 pos = position;',
      '  float t = uTime * 0.25;',
      '  float w = noise(vec2(pos.x*2.2 + t*0.55, pos.y*1.6 + t*0.38)) * 0.07',
      '          + noise(vec2(pos.x*4.0 - t*0.32, pos.y*3.0 + t*0.50)) * 0.035',
      '          + noise(vec2(pos.x*8.0 + t*0.85, pos.y*7.0 - t*0.27)) * 0.012;',
      '  pos.z += w; vWave = w;',
      '  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);',
      '}'
    ].join('\n');

    // 关键：拉大颜色对比 → 暖米黄底 + 明显金色丝纹
    var fsh = [
      'uniform float uTime;',
      'varying vec2 vUv;',
      'varying float vWave;',
      'void main(){',
      '  vec3 cBase  = vec3(0.957, 0.925, 0.855);',  // 暖米色
      '  vec3 cWarm  = vec3(0.918, 0.855, 0.722);',  // 浅金黄
      '  vec3 cGold  = vec3(0.812, 0.643, 0.345);',  // 真金色
      '  vec3 cDeep  = vec3(0.694, 0.510, 0.231);',  // 暗金
      '  vec3 cSheen = vec3(0.996, 0.972, 0.910);',  // 高光丝白
      '  float t = uTime * 0.16;',
      '  float stripe = sin((vUv.y*9.0 + vUv.x*4.0) + t + vWave*22.0) * 0.5 + 0.5;',
      '  float ripple = sin(vUv.x*16.0 - t*0.8 + vWave*30.0) * 0.5 + 0.5;',
      '  float diag   = sin((vUv.x + vUv.y)*6.0 + t*0.45) * 0.5 + 0.5;',
      '  float sheen  = smoothstep(0.55, 1.0, sin(vUv.x*2.5 - vUv.y*1.8 + t*0.6)*0.5+0.5);',
      '  vec3 col = mix(cBase, cWarm, stripe * 0.85);',
      '  col = mix(col, cGold, ripple * 0.32);',
      '  col = mix(col, cDeep, diag * 0.10);',
      '  col = mix(col, cSheen, sheen * 0.55);',
      '  float dist = distance(vUv, vec2(0.5));',
      '  col *= 1.0 - smoothstep(0.55, 1.05, dist) * 0.25;',
      '  gl_FragColor = vec4(col, 1.0);',
      '}'
    ].join('\n');

    var mat = new THREE.ShaderMaterial({
      vertexShader: vsh, fragmentShader: fsh,
      uniforms: { uTime: { value: 0 } }
    });
    scene.add(new THREE.Mesh(geo, mat));

    function resize() { renderer.setSize(window.innerWidth, window.innerHeight, false); }
    resize();
    window.addEventListener('resize', resize);

    function animate(t) {
      requestAnimationFrame(animate);
      mat.uniforms.uTime.value = t * 0.001;
      renderer.render(scene, camera);
    }
    animate(0);
    console.log('[silk] Three.js 金纹丝绸背景已启动 (vertices=' + (221*221) + ')');
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
