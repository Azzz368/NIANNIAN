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

      void main() {
        vec2 uv = gl_FragCoord.xy / uResolution.xy;
        uv = uv * 2.0 - 1.0;
        uv.x *= uResolution.x / uResolution.y;

        float dist = length(uv);
        float targetRadius = 0.4 + uVolume * 1.5;
        targetRadius += sin(uTime * 1.5) * 0.015;

        float ripple = sin(dist * 30.0 - uTime * 6.0) * 0.01 * uVolume;
        dist += ripple;

        vec3 bgColor = mix(vec3(0.5, 0.8, 0.5), vec3(0.85, 0.95, 0.85), clamp(dist*0.5, 0.0, 1.0));

        vec3 colCore = vec3(1.0, 0.95, 0.2);
        vec3 colMid1 = vec3(1.0, 0.6, 0.2);
        vec3 colMid2 = vec3(1.0, 0.4, 0.45);
        vec3 colGlow = vec3(1.0, 0.98, 0.98);

        float d = dist / targetRadius;
        vec3 color = bgColor;
        if (d < 1.5) {
            float fCore = smoothstep(0.3, 0.0, d);
            float fMid1 = smoothstep(0.6, 0.2, d);
            float fMid2 = smoothstep(0.9, 0.5, d);
            float fGlow = smoothstep(1.5, 0.8, d);

            vec3 sunColor = mix(colGlow, colMid2, fMid2);
            sunColor = mix(sunColor, colMid1, fMid1);
            sunColor = mix(sunColor, colCore, fCore);

            color = mix(bgColor, sunColor, fGlow);
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

    function render() {
      requestAnimationFrame(render);
      var dt = clock.getDelta();
      material.uniforms.uTime.value += dt;

      var targetVol = window.aiActiveVolume || 0;
      targetVol = Math.pow(targetVol, 0.8) * 1.2;
      
      currentVolume += (targetVol - currentVolume) * (dt * 15.0);
      material.uniforms.uVolume.value = currentVolume;

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
