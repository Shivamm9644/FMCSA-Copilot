// compliance_r3f.js - Pure Three.js FMCSA Processing Engine
// NOTE: React Three Fiber has NO browser UMD build (all CDN paths 404).
//       This file uses Three.js directly - confirmed 200 OK at unpkg.

(function () {
  'use strict';

  /* -------------------------------------------------------
     STATE BRIDGE  (kept compatible with portfolio.js)
  ------------------------------------------------------- */
  window.complianceR3FState = window.complianceR3FState || {
    mode: 'idle',
    recordsCount: 0,
    violationsCount: 0,
    repairedCount: 0,
    listeners: [],
    subscribe(fn) { this.listeners.push(fn); },
    unsubscribe(fn) { this.listeners = this.listeners.filter(l => l !== fn); },
    update(u) {
      Object.assign(this, u);
      this.listeners.forEach(l => l(this));
    }
  };

  /* -------------------------------------------------------
     HELPERS
  ------------------------------------------------------- */
  function makeCanvasTexture(drawFn, w, h) {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    drawFn(c.getContext('2d'), w, h);
    const tex = new THREE.CanvasTexture(c);
    tex.needsUpdate = true;
    return tex;
  }

  function labelTexture(text, color, fs) {
    fs = fs || 18;
    return makeCanvasTexture((ctx, w, h) => {
      ctx.clearRect(0, 0, w, h);
      ctx.shadowColor = color;
      ctx.shadowBlur = 8;
      ctx.font = `bold ${fs}px "Fira Code",monospace`;
      ctx.fillStyle = color;
      ctx.textAlign = 'center';
      ctx.fillText(text, w / 2, h * 0.7);
    }, 256, 56);
  }

  function holoScreen(title, lines, statusColor) {
    return makeCanvasTexture((ctx, w, h) => {
      ctx.fillStyle = 'rgba(0,0,0,0.85)';
      ctx.fillRect(0, 0, w, h);

      // Grid
      ctx.strokeStyle = 'rgba(0,240,255,0.06)';
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 32) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
      for (let y = 0; y < h; y += 32) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }

      // Border
      ctx.strokeStyle = 'rgba(0,240,255,0.35)';
      ctx.lineWidth = 2;
      ctx.strokeRect(4, 4, w - 8, h - 8);

      // Corner ticks
      ctx.fillStyle = '#00f0ff';
      [[4, 4], [w - 24, 4], [4, h - 8], [w - 24, h - 8]].forEach(([x, y]) => ctx.fillRect(x, y, 20, 3));
      [[4, 4], [w - 8, 4], [4, h - 24], [w - 8, h - 24]].forEach(([x, y]) => ctx.fillRect(x, y, 3, 20));

      // Title
      ctx.font = 'bold 20px "Fira Code",monospace';
      ctx.fillStyle = '#fff';
      ctx.shadowColor = '#00f0ff'; ctx.shadowBlur = 6;
      ctx.fillText(title, w / 2, 38);

      // Status
      ctx.shadowBlur = 0;
      ctx.fillStyle = statusColor;
      ctx.font = 'bold 11px "Fira Code",monospace';
      ctx.fillText(statusColor === '#10b981' ? '● PASS' : '● ACTIVE', w - 70, 38);

      // Divider
      ctx.strokeStyle = 'rgba(0,240,255,0.15)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(16, 52); ctx.lineTo(w - 16, 52); ctx.stroke();

      // Lines
      ctx.font = '13px "Fira Code",monospace';
      ctx.fillStyle = 'rgba(255,255,255,0.88)';
      lines.forEach((ln, i) => ctx.fillText(ln, w / 2, 76 + i * 26));
    }, 512, 220);
  }

  function comparisonTexture(before, after) {
    return makeCanvasTexture((ctx, w, h) => {
      ctx.fillStyle = 'rgba(0,0,0,0.9)';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = 'rgba(0,240,255,0.25)';
      ctx.lineWidth = 1.5; ctx.strokeRect(4, 4, w - 8, h - 8);

      // Divider
      ctx.beginPath(); ctx.moveTo(w / 2, 8); ctx.lineTo(w / 2, h - 8); ctx.stroke();

      ctx.font = 'bold 11px "Fira Code",monospace';
      ctx.fillStyle = '#ef4444'; ctx.fillText('BEFORE CORRECTION', 64, 26);
      ctx.fillStyle = '#10b981'; ctx.fillText('AFTER CORRECTION', 64 + w / 2, 26);

      ctx.font = '12px "Fira Code",monospace';
      ctx.fillStyle = '#ef4444'; ctx.fillText(before, 64, 60);
      ctx.fillStyle = '#10b981'; ctx.fillText(after, 64 + w / 2, 60);
    }, 480, 80);
  }

  /* -------------------------------------------------------
     SCENE BOOTSTRAP
  ------------------------------------------------------- */
  function init() {
    const container = document.getElementById('csv-3d-root');
    if (!container) return;

    // Prevent double-init
    if (container._threeInit) return;
    container._threeInit = true;

    /* Renderer */
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setSize(container.clientWidth || 800, container.clientHeight || 500);
    container.appendChild(renderer.domElement);

    /* Scene */
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x03000a, 0.028);

    /* Camera */
    const W = container.clientWidth || 800;
    const H = container.clientHeight || 500;
    const camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 120);
    camera.position.set(0, 3.8, 15);
    camera.lookAt(0, -1, 0);

    /* Orbit Controls – inline (no import needed) */
    let orbitDragging = false;
    let orbitSph = { theta: 0, phi: Math.PI / 3 };
    const orbitTarget = new THREE.Vector3(0, -1, 0);
    const orbitR = () => camera.position.distanceTo(orbitTarget);

    function updateCamera() {
      const r = orbitR();
      camera.position.set(
        orbitTarget.x + r * Math.sin(orbitSph.phi) * Math.sin(orbitSph.theta),
        orbitTarget.y + r * Math.cos(orbitSph.phi),
        orbitTarget.z + r * Math.sin(orbitSph.phi) * Math.cos(orbitSph.theta)
      );
      camera.lookAt(orbitTarget);
    }

    let lastMouse = { x: 0, y: 0 };
    renderer.domElement.addEventListener('mousedown', e => { orbitDragging = true; lastMouse = { x: e.clientX, y: e.clientY }; });
    window.addEventListener('mouseup', () => { orbitDragging = false; });
    window.addEventListener('mousemove', e => {
      if (!orbitDragging) return;
      const dx = (e.clientX - lastMouse.x) * 0.005;
      const dy = (e.clientY - lastMouse.y) * 0.005;
      orbitSph.theta -= dx;
      orbitSph.phi = Math.max(0.15, Math.min(Math.PI * 0.48, orbitSph.phi + dy));
      lastMouse = { x: e.clientX, y: e.clientY };
      updateCamera();
    });
    renderer.domElement.addEventListener('wheel', e => {
      const r = orbitR();
      const newR = Math.max(6, Math.min(40, r + e.deltaY * 0.02));
      const factor = newR / r;
      camera.position.sub(orbitTarget).multiplyScalar(factor).add(orbitTarget);
    }, { passive: true });

    // Mouse parallax (when not dragging)
    let mouseNX = 0, mouseNY = 0;
    window.addEventListener('mousemove', e => {
      mouseNX = (e.clientX / window.innerWidth - 0.5) * 2;
      mouseNY = (e.clientY / window.innerHeight - 0.5) * 2;
    });

    /* Lights */
    scene.add(new THREE.AmbientLight(0xffffff, 0.22));
    const pL1 = new THREE.PointLight(0x00f0ff, 2.0, 60);
    pL1.position.set(10, 15, 10); scene.add(pL1);
    const pL2 = new THREE.PointLight(0xbd00ff, 1.2, 50);
    pL2.position.set(-10, -10, -10); scene.add(pL2);
    const pL3 = new THREE.PointLight(0x10b981, 1.0, 40);
    pL3.position.set(0, 5, 18); scene.add(pL3);

    /* -------------------------------------------------------
       CONVEYOR GRID
    ------------------------------------------------------- */
    const conveyorGroup = new THREE.Group();
    conveyorGroup.position.y = -2.5;
    scene.add(conveyorGroup);
    const gridHelper = new THREE.GridHelper(35, 18, 0x00f0ff, 0x071b2f);
    conveyorGroup.add(gridHelper);
    [[-3.5], [3.5]].forEach(([x]) => {
      const rail = new THREE.Mesh(
        new THREE.CylinderGeometry(0.07, 0.07, 35, 6),
        new THREE.MeshBasicMaterial({ color: 0x00f0ff, transparent: true, opacity: 0.3 })
      );
      rail.rotation.z = Math.PI / 2;
      rail.position.x = x;
      conveyorGroup.add(rail);
    });

    /* -------------------------------------------------------
       LABEL SPRITE HELPER
    ------------------------------------------------------- */
    function makeLabel(text, color, pos, scaleX, scaleY) {
      scaleX = scaleX || 2.0; scaleY = scaleY || 0.5;
      const mat = new THREE.MeshBasicMaterial({
        map: labelTexture(text, color),
        transparent: true, opacity: 0.9,
        side: THREE.DoubleSide, depthWrite: false
      });
      const m = new THREE.Mesh(new THREE.PlaneGeometry(scaleX, scaleY), mat);
      m.position.copy(pos);
      return m;
    }

    /* -------------------------------------------------------
       NODE FACTORY  – each pipeline stage
    ------------------------------------------------------- */

    // 1. UPLOAD GATE  Z=-14.5
    const uploadGate = new THREE.Group(); uploadGate.position.set(0, -1.8, -14.5); scene.add(uploadGate);
    const ugRing = new THREE.Mesh(new THREE.TorusGeometry(1.5, 0.08, 6, 24), new THREE.MeshBasicMaterial({ color: 0x3b82f6 }));
    uploadGate.add(ugRing);
    uploadGate.add(makeLabel('UPLOAD_GATE', '#3b82f6', new THREE.Vector3(0, 1.5, 0), 2.0, 0.5));

    // 2. PARSER  Z=-11
    const parserGroup = new THREE.Group(); parserGroup.position.set(0, -1.5, -11); scene.add(parserGroup);
    const parserCage = new THREE.Mesh(new THREE.BoxGeometry(1.6, 1.6, 1.6), new THREE.MeshBasicMaterial({ color: 0x3b82f6, wireframe: true, transparent: true, opacity: 0.6 }));
    const parserCore = new THREE.Mesh(new THREE.SphereGeometry(0.4, 8, 8), new THREE.MeshBasicMaterial({ color: 0x3b82f6 }));
    parserGroup.add(parserCage, parserCore);
    parserGroup.add(makeLabel('CSV_PARSER', '#3b82f6', new THREE.Vector3(0, 1.4, 0)));

    // 3. VALIDATION CHAMBER  Z=-7.5
    const valGroup = new THREE.Group(); valGroup.position.set(0, -1.5, -7.5); scene.add(valGroup);
    const valCyl = new THREE.Mesh(new THREE.CylinderGeometry(1.3, 1.3, 2.2, 16), new THREE.MeshPhongMaterial({ color: 0x00f0ff, transparent: true, opacity: 0.12, shininess: 90 }));
    const valRing = new THREE.Mesh(new THREE.TorusGeometry(1.1, 0.05, 4, 16), new THREE.MeshBasicMaterial({ color: 0x00f0ff }));
    // scan plane
    const scanPlane = new THREE.Mesh(new THREE.PlaneGeometry(3, 0.05), new THREE.MeshBasicMaterial({ color: 0x00f0ff, transparent: true, opacity: 0.6, side: THREE.DoubleSide }));
    valGroup.add(valCyl, valRing, scanPlane);
    valGroup.add(makeLabel('VALIDATION_CHAMBER', '#00f0ff', new THREE.Vector3(0, 1.6, 0), 2.6, 0.5));

    // 4. RULE UNIVERSE – 6 gates
    const ruleGates = [
      { name: 'Event Sequence', z: -4.5, color: 0x00f0ff },
      { name: 'Engine Hours', z: -2.5, color: 0xbd00ff },
      { name: 'Odometer Logs', z: -0.5, color: 0xec4899 },
      { name: 'Driver Logins', z: 1.5, color: 0x10b981 },
      { name: 'Diagnostics', z: 3.5, color: 0xeab308 },
      { name: 'Malfunctions', z: 5.5, color: 0xef4444 },
    ];
    const ruleObjects = ruleGates.map(g => {
      const grp = new THREE.Group(); grp.position.set(0, -1.6, g.z); scene.add(grp);
      const ring = new THREE.Mesh(new THREE.TorusGeometry(1.2, 0.025, 4, 24), new THREE.MeshBasicMaterial({ color: g.color, transparent: true, opacity: 0.5 }));
      grp.add(ring);
      grp.add(makeLabel(g.name, '#' + g.color.toString(16).padStart(6, '0'), new THREE.Vector3(0, 1.1, 0), 1.3, 0.28));
      return { grp, ring, color: g.color };
    });

    // 5. AI NEURAL CORE  (offset left)
    const neuralGroup = new THREE.Group(); neuralGroup.position.set(-5.8, 1.8, -1); scene.add(neuralGroup);
    neuralGroup.add(makeLabel('AI NEURAL CORE', '#a855f7', new THREE.Vector3(0, 2.1, 0), 2.3, 0.52));

    const nodePositions = [
      { pos: [0, 1.1, 0], label: 'RULE_MATCH', color: 0x00f0ff },
      { pos: [-1.1, 0, 0], label: 'ROOT_CAUSE', color: 0xa855f7 },
      { pos: [1.1, 0, 0], label: 'FIX_GENERATOR', color: 0xec4899 },
      { pos: [0, -1.1, 0], label: 'CHECKSUM_ENG', color: 0xeab308 },
    ];
    const neuralNodes = nodePositions.map(n => {
      const grp = new THREE.Group(); grp.position.set(...n.pos); neuralGroup.add(grp);
      const core = new THREE.Mesh(new THREE.SphereGeometry(0.32, 12, 12), new THREE.MeshBasicMaterial({ color: n.color }));
      const shell = new THREE.Mesh(new THREE.SphereGeometry(0.5, 10, 10), new THREE.MeshBasicMaterial({ color: n.color, wireframe: true, transparent: true, opacity: 0.25 }));
      grp.add(core, shell);
      const lpos = new THREE.Vector3(0, n.pos[1] >= 0 ? 0.65 : -0.65, 0);
      grp.add(makeLabel(n.label, '#' + n.color.toString(16).padStart(6, '0'), lpos, 1.2, 0.28));
      return { grp, core, shell, color: n.color };
    });

    // Synapse lines between nodes
    const synapsePoints = [
      [0, 1.1, 0], [-1.1, 0, 0], [-1.1, 0, 0], [0, -1.1, 0],
      [0, -1.1, 0], [1.1, 0, 0], [1.1, 0, 0], [0, 1.1, 0],
      [0, 1.1, 0], [0, -1.1, 0], [-1.1, 0, 0], [1.1, 0, 0],
    ];
    const synGeo = new THREE.BufferGeometry();
    synGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(synapsePoints.flat()), 3));
    const synLine = new THREE.LineSegments(synGeo, new THREE.LineBasicMaterial({ color: 0xa855f7, transparent: true, opacity: 0.3 }));
    neuralGroup.add(synLine);

    // 6. ROOT CAUSE ANALYZER  Z=6.5
    const rcaGroup = new THREE.Group(); rcaGroup.position.set(0, -1.5, 6.5); scene.add(rcaGroup);
    const rcaRing = new THREE.Mesh(new THREE.TorusGeometry(1.1, 0.05, 6, 24), new THREE.MeshBasicMaterial({ color: 0xef4444, transparent: true, opacity: 0.7 }));
    const rcaCone = new THREE.Mesh(new THREE.ConeGeometry(0.6, 1.4, 8), new THREE.MeshBasicMaterial({ color: 0xef4444, wireframe: true, transparent: true, opacity: 0.5 }));
    rcaCone.position.y = -0.5;
    rcaGroup.add(rcaRing, rcaCone);
    rcaGroup.add(makeLabel('ROOT_CAUSE_ENGINE', '#ef4444', new THREE.Vector3(0, 1.5, 0), 2.5, 0.5));

    // 7. AUTO CORRECTION  Z=7.5
    const welderGroup = new THREE.Group(); welderGroup.position.set(0, -1.5, 7.5); scene.add(welderGroup);
    welderGroup.add(makeLabel('AUTO_CORRECTION_ENGINE', '#eab308', new THREE.Vector3(0, 1.6, 0), 2.6, 0.5));
    const welderArms = [-2, 2].map(x => {
      const arm = new THREE.Group(); arm.position.x = x;
      const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 1.0, 6), new THREE.MeshBasicMaterial({ color: 0x475569 }));
      rod.rotation.z = Math.PI / 2; rod.position.x = x > 0 ? -0.5 : 0.5;
      const tip = new THREE.Mesh(new THREE.SphereGeometry(0.18, 8, 8), new THREE.MeshBasicMaterial({ color: 0x475569 }));
      tip.position.x = x > 0 ? -1 : 0;
      arm.add(rod, tip);
      welderGroup.add(arm);
      return { arm, tip };
    });

    // Before/After hologram
    const compPanel = new THREE.Mesh(
      new THREE.PlaneGeometry(4.5, 0.8),
      new THREE.MeshBasicMaterial({ map: comparisonTexture('DRV1092,OFF,--,FAIL', 'DRV1092,OFF,0x9B,PASS'), transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false })
    );
    compPanel.position.set(0, 1.6, 7.5);
    scene.add(compPanel);

    // 8. CHECKSUM PROCESSOR  Z=10.5
    const csGroup = new THREE.Group(); csGroup.position.set(0, -1.4, 10.5); scene.add(csGroup);
    const csTorus1 = new THREE.Mesh(new THREE.TorusGeometry(1.2, 0.06, 6, 24), new THREE.MeshBasicMaterial({ color: 0x10b981 }));
    const csTorus2 = new THREE.Mesh(new THREE.TorusGeometry(1.4, 0.04, 4, 20), new THREE.MeshBasicMaterial({ color: 0x00f0ff }));
    csTorus2.rotation.x = Math.PI / 2;
    csGroup.add(csTorus1, csTorus2);
    csGroup.add(makeLabel('CHECKSUM_SIGNATURE', '#10b981', new THREE.Vector3(0, 1.4, 0), 2.2, 0.45));

    // 9. REVALIDATION  Z=13  +  OUTPUT GATE  Z=15
    const revalGroup = new THREE.Group(); revalGroup.position.set(0, -1.2, 13); scene.add(revalGroup);
    const revalSphere = new THREE.Mesh(new THREE.SphereGeometry(0.9, 12, 12), new THREE.MeshBasicMaterial({ color: 0x10b981, wireframe: true, transparent: true, opacity: 0.5 }));
    revalGroup.add(revalSphere);
    revalGroup.add(makeLabel('REVALIDATOR', '#10b981', new THREE.Vector3(0, 1.3, 0), 1.9, 0.45));

    const outGate = new THREE.Group(); outGate.position.set(0, -1.8, 15); scene.add(outGate);
    const outRing = new THREE.Mesh(new THREE.TorusGeometry(1.5, 0.08, 6, 24), new THREE.MeshBasicMaterial({ color: 0x10b981, transparent: true, opacity: 0.8 }));
    outGate.add(outRing);
    outGate.add(makeLabel('COMPLIANT_OUTPUT', '#10b981', new THREE.Vector3(0, 1.5, 0), 2.2, 0.5));

    /* -------------------------------------------------------
       COMPLIANCE SCOREBOARD HUD
    ------------------------------------------------------- */
    let scoreValue = 88;
    let scoreTex = holoScreen('FMCSA COMPLIANCE SCORE', [`STATUS: AWAITING AUDIT`, 'SCORE: 88%', 'ERRORS: --', 'MODE: STANDBY'], '#00f0ff');
    const scoreMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(5.2, 2.6),
      new THREE.MeshBasicMaterial({ map: scoreTex, transparent: true, opacity: 0.92, depthWrite: false })
    );
    scoreMesh.position.set(6, 2.2, -4);
    scoreMesh.rotation.y = -0.4;
    scene.add(scoreMesh);

    function refreshScoreboard(score, mode, violations) {
      const s = Math.floor(score);
      const statusColor = s === 100 ? '#10b981' : (mode === 'investigating' ? '#ef4444' : '#00f0ff');
      const tex = holoScreen('FMCSA COMPLIANCE SCORE', [
        `STATUS: ${s === 100 ? '100% COMPLIANT' : mode.toUpperCase()}`,
        `SCORE TRANSFORM: ${s}%`,
        `ERRORS DETECTED: ${s === 100 ? '0' : (violations || '--')}`,
        `ENGINE: PROCESSING`
      ], statusColor);
      scoreMesh.material.map = tex;
      scoreMesh.material.needsUpdate = true;
    }

    /* -------------------------------------------------------
       DATA PACKETS
    ------------------------------------------------------- */
    const PACKET_COUNT = 7;
    const packets = Array.from({ length: PACKET_COUNT }, (_, i) => {
      const mat = new THREE.MeshBasicMaterial({ color: 0x3b82f6, transparent: true, opacity: 0.85 });
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.25, 0.6), mat);
      const wire = new THREE.Mesh(new THREE.BoxGeometry(1.55, 0.28, 0.64), new THREE.MeshBasicMaterial({ color: 0xffffff, wireframe: true, transparent: true, opacity: 0.08 }));
      const grp = new THREE.Group();
      grp.add(mesh, wire);
      grp.position.set(0, -2.1, -18 + i * 5.2);
      scene.add(grp);

      // Violation hologram label
      const vlMat = new THREE.MeshBasicMaterial({ map: labelTexture('CFR 395.15 CHECKSUM FAIL', '#ef4444', 14), transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false });
      const vlPlane = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 0.35), vlMat);
      vlPlane.position.y = 0.9;
      grp.add(vlPlane);

      return { grp, mesh, mat, wire, vlPlane, vlMat, z: -18 + i * 5.2, anomalous: false, repaired: false, failFlash: 0 };
    });

    /* -------------------------------------------------------
       BACKGROUND SPARKLES
    ------------------------------------------------------- */
    const sparkPositions = new Float32Array(240);
    for (let i = 0; i < 240; i += 3) {
      sparkPositions[i] = (Math.random() - 0.5) * 30;
      sparkPositions[i + 1] = (Math.random() - 0.5) * 18;
      sparkPositions[i + 2] = (Math.random() - 0.5) * 30;
    }
    const sparkGeo = new THREE.BufferGeometry();
    sparkGeo.setAttribute('position', new THREE.BufferAttribute(sparkPositions, 3));
    const sparkMesh = new THREE.Points(sparkGeo, new THREE.PointsMaterial({ size: 0.07, color: 0xa855f7, transparent: true, opacity: 0.4 }));
    scene.add(sparkMesh);

    /* -------------------------------------------------------
       AUTO-CYCLE IDLE DEMO  (so visitors see workflow immediately)
    ------------------------------------------------------- */
    const DEMO_STAGES = ['parsing', 'validating', 'investigating', 'correcting', 'recalculating', 'complete'];
    let demoStageIdx = 0;
    let demoTimer = 0;
    const DEMO_STAGE_DUR = 2.8; // seconds per stage in idle demo

    /* -------------------------------------------------------
       MAIN RENDER LOOP
    ------------------------------------------------------- */
    let lastT = 0;
    let scoreTarget = 88;

    function animate(ts) {
      requestAnimationFrame(animate);
      const t = ts * 0.001;
      const dt = t - lastT; lastT = t;

      const state = window.complianceR3FState;
      const mode = state.mode;

      // AUTO-CYCLE when idle  
      if (mode === 'idle') {
        demoTimer += dt;
        if (demoTimer >= DEMO_STAGE_DUR) {
          demoTimer = 0;
          demoStageIdx = (demoStageIdx + 1) % DEMO_STAGES.length;
          // Don't mutate real state — use local variable
        }
      } else {
        demoTimer = 0;
        demoStageIdx = 0;
      }
      const effectiveMode = (mode === 'idle') ? DEMO_STAGES[demoStageIdx] : mode;

      // Conveyor scroll
      conveyorGroup.position.z = (t * 2) % 2;

      // Upload gate spin
      ugRing.rotation.y = t * 1.5;
      outRing.rotation.z = t * 1.2;

      // Parser
      parserCage.rotation.x = t * (effectiveMode === 'parsing' ? 3 : 0.5) * 0.02;
      parserCage.rotation.y = t * (effectiveMode === 'parsing' ? 3 : 0.5) * 0.03;
      parserCore.material.color.set(effectiveMode === 'parsing' ? 0xd946ef : 0x3b82f6);

      // Validation chamber scanner
      valRing.position.y = Math.sin(t * 4) * 0.7;
      valRing.material.color.set(effectiveMode === 'validating' ? 0xec4899 : 0x00f0ff);
      scanPlane.position.y = Math.sin(t * 3) * 1.0;
      scanPlane.material.color.set(effectiveMode === 'validating' ? 0xef4444 : 0x00f0ff);
      scanPlane.material.opacity = effectiveMode === 'validating' ? 0.7 : 0.2;

      // Rule gates pulsing
      ruleObjects.forEach((r, i) => {
        const isActive = effectiveMode === 'validating' || effectiveMode === 'investigating';
        r.ring.material.opacity = isActive ? 0.5 + Math.sin(t * 3 + i) * 0.3 : 0.15;
        r.ring.rotation.y = t * (0.5 + i * 0.1);
      });

      // Neural core node pulsing
      neuralNodes.forEach((n, i) => {
        n.grp.rotation.y = t * (1.2 + i * 0.15) * (i % 2 === 0 ? 1 : -1);
        const isActive = effectiveMode !== 'idle';
        const activeColors = [0x00f0ff, 0xa855f7, 0xec4899, 0xeab308];
        const inactiveColor = 0x334155;
        n.core.material.color.set(isActive ? activeColors[i] : inactiveColor);
        n.shell.material.color.set(isActive ? activeColors[i] : inactiveColor);
        n.shell.material.opacity = isActive ? 0.2 + Math.sin(t * 2 + i) * 0.1 : 0.05;
      });
      synLine.material.opacity = effectiveMode !== 'idle' ? 0.25 + Math.sin(t * 2) * 0.15 : 0.06;

      // Root cause analyzer
      rcaRing.rotation.z = t * 1.2;
      rcaCone.position.y = -0.5 + Math.sin(t * 3) * 0.2;
      const rcaActive = effectiveMode === 'investigating' || effectiveMode === 'correcting';
      rcaRing.material.color.set(rcaActive ? 0xef4444 : 0x334155);
      rcaRing.material.opacity = rcaActive ? 0.75 : 0.2;

      // Welder arms
      const weldActive = effectiveMode === 'correcting' || effectiveMode === 'recalculating';
      welderArms[0].arm.position.y = -0.5 + Math.sin(t * 5) * 0.18;
      welderArms[1].arm.position.y = -0.5 - Math.sin(t * 5) * 0.18;
      welderArms.forEach(w => w.tip.material.color.set(weldActive ? 0xeab308 : 0x334155));

      // Before/After panel
      compPanel.material.opacity = weldActive ? 0.88 + Math.sin(t * 2) * 0.05 : 0;
      compPanel.position.y = 1.6 + Math.sin(t * 1.5) * 0.06;

      // Checksum processor
      csTorus1.rotation.y = t * 1.5;
      csTorus2.rotation.x = -t * 1.2;
      const csActive = effectiveMode === 'recalculating' || effectiveMode === 'complete';
      csTorus1.material.color.set(csActive ? 0x10b981 : 0x334155);
      csTorus2.material.color.set(csActive ? 0x00f0ff : 0x334155);

      // Revalidation sphere
      revalSphere.rotation.y = t * 0.8;
      revalSphere.material.color.set(effectiveMode === 'complete' ? 0x10b981 : 0x334155);
      revalSphere.material.opacity = effectiveMode === 'complete' ? 0.5 + Math.sin(t * 3) * 0.2 : 0.15;

      // Out ring
      outRing.material.color.set(effectiveMode === 'complete' ? 0x10b981 : 0x3b82f6);

      /* ---- Data Packets ---- */
      const vCount = state.violationsCount || 0;
      packets.forEach((p, i) => {
        p.z += 0.055;
        if (p.z > 16.5) {
          p.z = -18;
          p.anomalous = false;
          p.repaired = false;
        }
        p.grp.position.z = p.z;

        // Mark anomalous at validation zone
        if (p.z >= -3.0 && p.z <= -0.2 && vCount > 0 && i % 2 === 0) {
          p.anomalous = true;
        }
        // In idle demo, make every other packet anomalous briefly for visual effect
        if (mode === 'idle' && p.z >= -3.0 && p.z <= -0.2 && i % 2 === 0) {
          p.anomalous = true;
        }

        // Repair at welder zone
        if (p.anomalous && p.z >= 6.5 && p.z <= 8.5) {
          if (weldActive || mode === 'idle') { p.anomalous = false; p.repaired = true; }
        }

        // Color
        let col;
        if (p.z <= -14) col = 0x3b82f6;
        else if (p.z <= -11) col = 0xbd00ff;
        else if (p.z <= -7.5) col = 0xec4899;
        else if (p.anomalous) {
          p.failFlash = (p.failFlash || 0) + dt;
          col = Math.floor(p.failFlash * 8) % 2 === 0 ? 0xef4444 : 0x7f1d1d;
        } else if (p.repaired) { col = 0xeab308; }
        else if (p.z > 8.5) col = 0x10b981;
        else col = 0x3b82f6;

        p.mat.color.set(col);
        p.vlMat.opacity = p.anomalous ? 0.9 : 0;
      });

      /* ---- Score climb ---- */
      if (effectiveMode === 'correcting' || effectiveMode === 'recalculating' || effectiveMode === 'complete') {
        scoreTarget = 100;
      } else if (effectiveMode === 'parsing' || effectiveMode === 'validating' || effectiveMode === 'investigating') {
        scoreTarget = 88;
      }
      scoreValue += (scoreTarget - scoreValue) * Math.min(dt * 0.4, 1);
      if (Math.abs(scoreValue - scoreTarget) > 0.3) {
        refreshScoreboard(scoreValue, effectiveMode, vCount || state.violationsCount);
      }

      /* ---- Sparkles drift ---- */
      sparkMesh.rotation.y = t * 0.04;

      /* ---- Passive parallax (non-drag) ---- */
      if (!orbitDragging) {
        camera.position.x += (mouseNX * 1.5 - camera.position.x) * 0.03;
        camera.lookAt(orbitTarget);
      }

      renderer.render(scene, camera);
    }

    /* -------------------------------------------------------
       RESIZE HANDLER
    ------------------------------------------------------- */
    function onResize() {
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }
    window.addEventListener('resize', onResize);
    // Also observe container size changes
    if (typeof ResizeObserver !== 'undefined') {
      new ResizeObserver(onResize).observe(container);
    }

    /* -------------------------------------------------------
       STAGE OVERLAY UPDATE (pipeline label bar in DOM)
    ------------------------------------------------------- */
    const stageBar = document.getElementById('fmcsa-stage-bar');
    const stageSteps = stageBar ? stageBar.querySelectorAll('[data-stage]') : [];

    function updateStageBar(mode) {
      const order = ['parsing', 'validating', 'investigating', 'correcting', 'recalculating', 'complete'];
      const idx = order.indexOf(mode);
      stageSteps.forEach((el, i) => {
        el.classList.remove('stage-active', 'stage-done', 'stage-pending');
        if (i < idx) el.classList.add('stage-done');
        else if (i === idx) el.classList.add('stage-active');
        else el.classList.add('stage-pending');
      });
    }

    window.complianceR3FState.subscribe(s => {
      updateStageBar(s.mode);
    });

    /* -------------------------------------------------------
       START
    ------------------------------------------------------- */
    animate(0);
  }

  /* -------------------------------------------------------
     MOUNT after DOM ready
  ------------------------------------------------------- */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    // DOM already ready – delay one tick so layout settles
    setTimeout(init, 0);
  }

})();
