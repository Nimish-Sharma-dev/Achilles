// Achilles Hardware Digital Twin — Tinkercad-style breadboard scene.
// Pure Three.js. No frameworks, no UI chrome — just the 3D workspace.

(function () {
  "use strict";

  var container = document.getElementById("twin-canvas");

  // ---------------------------------------------------------------
  // Renderer / Scene / Camera
  // ---------------------------------------------------------------
  var renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf4f5f7);

  var camera = new THREE.PerspectiveCamera(
    42,
    container.clientWidth / container.clientHeight,
    0.1,
    500
  );
  camera.position.set(11.5, 17.5, 15.5);

  // ---------------------------------------------------------------
  // Controls
  // ---------------------------------------------------------------
  var controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.45, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 8;
  controls.maxDistance = 55;
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.update();

  // ---------------------------------------------------------------
  // Lighting
  // ---------------------------------------------------------------
  scene.add(new THREE.AmbientLight(0xffffff, 0.65));

  var sun = new THREE.DirectionalLight(0xffffff, 0.85);
  sun.position.set(12, 22, 10);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -20;
  sun.shadow.camera.right = 20;
  sun.shadow.camera.top = 20;
  sun.shadow.camera.bottom = -20;
  sun.shadow.camera.far = 60;
  scene.add(sun);

  var fill = new THREE.DirectionalLight(0xffffff, 0.25);
  fill.position.set(-14, 10, -8);
  scene.add(fill);

  // Workspace floor grid (Tinkercad-style light grid, not a UI element)
  var grid = new THREE.GridHelper(80, 80, 0xd7dade, 0xe8eaed);
  grid.position.y = -0.02;
  scene.add(grid);

  var floor = new THREE.Mesh(
    new THREE.PlaneGeometry(200, 200),
    new THREE.MeshStandardMaterial({ color: 0xf4f5f7, roughness: 1 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.03;
  floor.receiveShadow = true;
  scene.add(floor);

  // ---------------------------------------------------------------
  // Materials (reused)
  // ---------------------------------------------------------------
  var mat = {
    board: new THREE.MeshStandardMaterial({ color: 0xf1efe6, roughness: 0.85 }),
    hole: new THREE.MeshStandardMaterial({ color: 0x2b2b2f, roughness: 0.9 }),
    railRed: new THREE.MeshStandardMaterial({ color: 0xd23c3c, roughness: 0.6 }),
    railBlue: new THREE.MeshStandardMaterial({ color: 0x2f6fd2, roughness: 0.6 }),
    pcbBlue: new THREE.MeshStandardMaterial({ color: 0x1560bd, roughness: 0.55 }),
    pcbDark: new THREE.MeshStandardMaterial({ color: 0x14181d, roughness: 0.5 }),
    pcbGreen: new THREE.MeshStandardMaterial({ color: 0x1f7a4c, roughness: 0.55 }),
    pcbPurple: new THREE.MeshStandardMaterial({ color: 0x4a2e73, roughness: 0.55 }),
    chip: new THREE.MeshStandardMaterial({ color: 0x111114, roughness: 0.4 }),
    shield: new THREE.MeshStandardMaterial({ color: 0xb9bcc2, roughness: 0.3, metalness: 0.6 }),
    pin: new THREE.MeshStandardMaterial({ color: 0xc7c9cc, roughness: 0.3, metalness: 0.7 }),
    terminalBlue: new THREE.MeshStandardMaterial({ color: 0x2255aa, roughness: 0.5 }),
    sensorBlue: new THREE.MeshStandardMaterial({ color: 0x3a8fd6, roughness: 0.5 }),
    usb: new THREE.MeshStandardMaterial({ color: 0x8a8d91, roughness: 0.4, metalness: 0.5 }),
    ledRed: new THREE.MeshStandardMaterial({ color: 0xff3b3b, emissive: 0x661010, roughness: 0.3 }),
    ledYellow: new THREE.MeshStandardMaterial({ color: 0xffd23b, emissive: 0x665510, roughness: 0.3 }),
    ledGreen: new THREE.MeshStandardMaterial({ color: 0x3bff6e, emissive: 0x106622, roughness: 0.3 }),
    wireLead: new THREE.MeshStandardMaterial({ color: 0xb7bcc2, roughness: 0.5, metalness: 0.6 }),
  };

  function box(w, h, d, material) {
    var m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
    m.castShadow = true;
    m.receiveShadow = true;
    return m;
  }

    // ---------------------------------------------------------------
    // Breadboard
    // ---------------------------------------------------------------

    var HOLE_SPACING = 0.42;
    var COLS = 42;

    var BOARD_W = COLS * HOLE_SPACING + 1.6;
    var BOARD_D = 8.6;
    var BOARD_H = 0.48;

    var breadboardGroup = new THREE.Group();


    // ---------------------------------------------------------------
    // Main body
    // ---------------------------------------------------------------

    var base = box(
    BOARD_W,
    BOARD_H,
    BOARD_D,
    mat.board
    );

    base.position.y = BOARD_H / 2;

    breadboardGroup.add(base);


    // ---------------------------------------------------------------
    // Central isolation channel
    // ---------------------------------------------------------------

    var channelMaterial =
    new THREE.MeshStandardMaterial({
        color: 0xd6d4ca,
        roughness: 0.9
    });

    var centerChannel = box(
    BOARD_W - 0.7,
    0.035,
    0.52,
    channelMaterial
    );

    centerChannel.position.set(
    0,
    BOARD_H + 0.018,
    0
    );

    centerChannel.castShadow = false;

    breadboardGroup.add(centerChannel);


    // ---------------------------------------------------------------
    // Terminal block separators
    // ---------------------------------------------------------------

    var separatorMaterial =
    new THREE.MeshStandardMaterial({
        color: 0xc8c6bc,
        roughness: 0.9
    });


    // upper block separator
    var upperSeparator = box(
    BOARD_W - 0.7,
    0.035,
    0.07,
    separatorMaterial
    );

    upperSeparator.position.set(
    0,
    BOARD_H + 0.018,
    1.72
    );

    breadboardGroup.add(upperSeparator);


    // lower block separator
    var lowerSeparator = box(
    BOARD_W - 0.7,
    0.035,
    0.07,
    separatorMaterial
    );

    lowerSeparator.position.set(
    0,
    BOARD_H + 0.018,
    -1.72
    );

    breadboardGroup.add(lowerSeparator);


    // ---------------------------------------------------------------
    // Power rails
    // ---------------------------------------------------------------

    function railStripe(zPos, material) {

    var rail = box(
        BOARD_W - 0.65,
        0.055,
        0.11,
        material
    );

    rail.position.set(
        0,
        BOARD_H + 0.055,
        zPos
    );

    rail.castShadow = false;

    breadboardGroup.add(rail);
    }


    railStripe(
    BOARD_D / 2 - 0.34,
    mat.railRed
    );

    railStripe(
    BOARD_D / 2 - 0.66,
    mat.railBlue
    );

    railStripe(
    -BOARD_D / 2 + 0.66,
    mat.railBlue
    );

    railStripe(
    -BOARD_D / 2 + 0.34,
    mat.railRed
    );


    // ---------------------------------------------------------------
    // Rail separators
    // ---------------------------------------------------------------

    var railSeparatorMaterial =
    new THREE.MeshStandardMaterial({
        color: 0xc5c3b9,
        roughness: 0.9
    });


    function railSeparator(zPos) {

    var separator = box(
        BOARD_W - 0.65,
        0.025,
        0.05,
        railSeparatorMaterial
    );

    separator.position.set(
        0,
        BOARD_H + 0.055,
        zPos
    );

    breadboardGroup.add(separator);
    }


    railSeparator(BOARD_D / 2 - 0.49);
    railSeparator(-BOARD_D / 2 + 0.49);


    // ---------------------------------------------------------------
    // Hole layout
    // ---------------------------------------------------------------

    var holeRowsZ = [];


    // Upper terminal block — five rows
    for (var upperRow = 0; upperRow < 5; upperRow++) {

    holeRowsZ.push(
        1.48 - upperRow * HOLE_SPACING
    );
    }


    // Lower terminal block — five rows
    for (var lowerRow = 0; lowerRow < 5; lowerRow++) {

    holeRowsZ.push(
        -0.68 - lowerRow * HOLE_SPACING
    );
    }


    // Power rails
    holeRowsZ.push(
    BOARD_D / 2 - 0.34,
    BOARD_D / 2 - 0.66,
    -BOARD_D / 2 + 0.66,
    -BOARD_D / 2 + 0.34
    );


    var holeCount =
    holeRowsZ.length * COLS;


    var holeGeometry =
    new THREE.CylinderGeometry(
        0.055,
        0.055,
        0.035,
        10
    );


    var holeMesh =
    new THREE.InstancedMesh(
        holeGeometry,
        mat.hole,
        holeCount
    );


    var dummy =
    new THREE.Object3D();


    var startX =
    -(COLS - 1) *
    HOLE_SPACING / 2;


    var idx = 0;


    for (
    var rowIndex = 0;
    rowIndex < holeRowsZ.length;
    rowIndex++
    ) {

    for (
        var columnIndex = 0;
        columnIndex < COLS;
        columnIndex++
    ) {

        dummy.position.set(
        startX +
            columnIndex * HOLE_SPACING,

        BOARD_H + 0.065,

        holeRowsZ[rowIndex]
        );

        dummy.rotation.x =
        Math.PI / 2;

        dummy.updateMatrix();

        holeMesh.setMatrixAt(
        idx,
        dummy.matrix
        );

        idx++;
    }
    }


    holeMesh.instanceMatrix.needsUpdate = true;

    holeMesh.receiveShadow = true;

    breadboardGroup.add(holeMesh);


    // ---------------------------------------------------------------
    // Breadboard end caps
    // ---------------------------------------------------------------

    var endCapMaterial =
    new THREE.MeshStandardMaterial({
        color: 0xe1dfd5,
        roughness: 0.85
    });


    var leftCap = box(
    0.35,
    0.62,
    BOARD_D + 0.15,
    endCapMaterial
    );

    leftCap.position.set(
    -BOARD_W / 2 - 0.03,
    0.30,
    0
    );

    breadboardGroup.add(leftCap);


    var rightCap = box(
    0.35,
    0.62,
    BOARD_D + 0.15,
    endCapMaterial
    );

    rightCap.position.set(
    BOARD_W / 2 + 0.03,
    0.30,
    0
    );

    breadboardGroup.add(rightCap);


    // ---------------------------------------------------------------
    // Add breadboard to scene
    // ---------------------------------------------------------------

    scene.add(breadboardGroup);
  // ---------------------------------------------------------------
  // Helper: pin headers along a component's long edges
  // ---------------------------------------------------------------
  function addPinRow(group, count, spacing, xOffset, z, y) {
    var startXLocal = xOffset - ((count - 1) * spacing) / 2;
    for (var i = 0; i < count; i++) {
      var pin = box(0.05, 0.22, 0.05, mat.pin);
      pin.position.set(startXLocal + i * spacing, y, z);
      group.add(pin);
    }
  }

  // ---------------------------------------------------------------
  // Component: STM32 IED MCU (blue-pill style board, left of board)
  // ---------------------------------------------------------------
  function buildSTM32() {
    var g = new THREE.Group();
    var pcb = box(4.6, 0.14, 1.9, mat.pcbBlue);
    pcb.position.y = 0.6;
    g.add(pcb);

    var mcuChip = box(1.1, 0.16, 1.1, mat.chip);
    mcuChip.position.set(-0.4, 0.75, 0);
    g.add(mcuChip);

    var crystal = box(0.35, 0.16, 0.22, mat.pin);
    crystal.position.set(0.9, 0.75, 0.5);
    g.add(crystal);

    // Mounting holes
    var mountingPositions = [
      [-2.0, -0.65],
      [-2.0,  0.65],
      [ 1.8, -0.65],
      [ 1.8,  0.65]
    ];

    mountingPositions.forEach(function(pos) {
      var hole = new THREE.Mesh(
        new THREE.CylinderGeometry(0.11, 0.11, 0.08, 16),
        mat.hole
      );

      hole.rotation.x = Math.PI / 2;
      hole.position.set(pos[0], 0.69, pos[1]);

      g.add(hole);
    });

    var usbConn = box(0.7, 0.35, 0.55, mat.usb);
    usbConn.position.set(-2.55, 0.72, 0);
    g.add(usbConn);

    addPinRow(g, 20, 0.2, 0, 0.98, 0.67);
    addPinRow(g, 20, 0.2, 0, -0.98, 0.67);

    var indicator = new THREE.Mesh(
      new THREE.SphereGeometry(0.06, 8, 8),
      mat.ledRed
    );
    indicator.position.set(1.9, 0.72, 0.75);
    g.add(indicator);

    return g;
  }

  // ---------------------------------------------------------------
  // Component: ESP32 Wi-Fi gateway (shielded module on dark PCB)
  // ---------------------------------------------------------------
  function buildESP32() {
    var g = new THREE.Group();
    var pcb = box(2.6, 0.14, 3.0, mat.pcbDark);
    pcb.position.y = 0.6;
    g.add(pcb);

    var shield = box(1.7, 0.32, 1.7, mat.shield);
    shield.position.set(0, 0.78, 0.5);
    g.add(shield);

    var antennaTab = box(1.0, 0.05, 0.6, mat.pcbDark);
    antennaTab.position.set(0, 0.63, -1.2);
    g.add(antennaTab);

    addPinRow(g, 15, 0.19, 0, 1.42, 0.67);
    addPinRow(g, 15, 0.19, 0, -1.42, 0.67);

    return g;
  }

  // ---------------------------------------------------------------
  // Component: DHT22 temperature / humidity sensor
  // ---------------------------------------------------------------
  function buildDHT22() {
    var g = new THREE.Group();
    var body = box(1.05, 1.3, 0.55, mat.sensorBlue);
    body.position.y = 1.1;
    g.add(body);

    var grilleMaterial =
    new THREE.MeshStandardMaterial({
      color: 0x1c2530,
      roughness: 0.8
    });

    var grille = box(
      0.78,
      0.82,
      0.07,
      grilleMaterial
    );

    grille.position.set(
      0,
      1.18,
      0.30
    );

    g.add(grille);

    for (var row = 0; row < 5; row++) {

      var grilleLine = box(
        0.62,
        0.035,
        0.02,
        mat.sensorBlue
      );

      grilleLine.position.set(
        0,
        0.88 + row * 0.14,
        0.35
      );

      g.add(grilleLine);
    }

    for (var i = 0; i < 4; i++) {
      var lead = box(0.05, 0.55, 0.05, mat.wireLead);
      lead.position.set(-0.35 + i * 0.23, 0.32, 0.15);
      g.add(lead);
    }
    return g;
  }

  // ---------------------------------------------------------------
  // Component: INA219 power monitor breakout
  // ---------------------------------------------------------------
  function buildINA219() {
    var g = new THREE.Group();
    var pcb = box(1.5, 0.12, 1.05, mat.pcbPurple);
    pcb.position.y = 0.6;
    g.add(pcb);

    var chip = box(0.4, 0.1, 0.35, mat.chip);
    chip.position.set(-0.2, 0.68, 0);
    g.add(chip);

    var terminal = box(0.55, 0.28, 0.3, mat.terminalBlue);
    terminal.position.set(0.6, 0.72, 0);
    g.add(terminal);

    addPinRow(g, 5, 0.2, -0.4, 0.56, 0.62);
    return g;
  }

  // ---------------------------------------------------------------
  // Component: W25Q128 SPI flash breakout
  // ---------------------------------------------------------------
  function buildFlash() {
    var g = new THREE.Group();
    var pcb = box(1.1, 0.1, 1.4, mat.pcbGreen);
    pcb.position.y = 0.58;
    g.add(pcb);

    var chip = box(0.55, 0.12, 0.85, mat.chip);
    chip.position.y = 0.66;
    g.add(chip);

    addPinRow(g, 4, 0.28, 0, 0.75, 0.55);
    addPinRow(g, 4, 0.28, 0, -0.75, 0.55);
    return g;
  }

  // ---------------------------------------------------------------
  // Component: MAX485 RS-485 transceiver
  // ---------------------------------------------------------------
  function buildMAX485() {
    var g = new THREE.Group();
    var pcb = box(1.6, 0.1, 1.1, mat.pcbGreen);
    pcb.position.y = 0.58;
    g.add(pcb);

    var chip = box(0.55, 0.1, 0.4, mat.chip);
    chip.position.set(-0.35, 0.66, 0);
    g.add(chip);

    var terminal = box(0.75, 0.3, 0.35, mat.terminalBlue);
    terminal.position.set(0.7, 0.73, 0);
    g.add(terminal);

    addPinRow(g, 4, 0.24, -0.3, 0.58, 0.62);
    return g;
  }

  // ---------------------------------------------------------------
  // Component: status LED (with leg pins into the breadboard)
  // ---------------------------------------------------------------
  function buildLED(material) {
    var g = new THREE.Group();
    var body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.14, 0.14, 0.3, 12),
      material
    );
    body.position.y = 0.75;
    body.castShadow = true;
    g.add(body);

    var dome = new THREE.Mesh(
      new THREE.SphereGeometry(0.14, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2),
      material
    );
    dome.position.y = 0.9;
    g.add(dome);

    var legL = box(0.03, 0.55, 0.03, mat.wireLead);
    legL.position.set(-0.06, 0.35, 0);
    g.add(legL);
    var legR = box(0.03, 0.7, 0.03, mat.wireLead);
    legR.position.set(0.06, 0.28, 0.02);
    g.add(legR);

    return g;
  }

    // ---------------------------------------------------------------
    // Place components on the board
    // ---------------------------------------------------------------

    var stm32 = buildSTM32();

    stm32.position.set(
    -4.4,
    0,
    0.95
    );

    scene.add(stm32);


    var esp32 = buildESP32();

    esp32.position.set(
    0.4,
    0,
    1.0
    );

    scene.add(esp32);


    var dht22 = buildDHT22();

    dht22.position.set(
    3.65,
    0,
    1.25
    );

    scene.add(dht22);


    var ina219 = buildINA219();

    ina219.position.set(
    3.55,
    0,
    -0.55
    );

    scene.add(ina219);


    var flash = buildFlash();

    flash.position.set(
    -3.1,
    0,
    -1.85
    );

    scene.add(flash);


    var max485 = buildMAX485();

    max485.position.set(
    1.15,
    0,
    -1.95
    );

    scene.add(max485);


    // ---------------------------------------------------------------
    // Status LEDs
    // ---------------------------------------------------------------

    var ledRed = buildLED(mat.ledRed);

    ledRed.position.set(
    -0.55,
    0,
    -2.55
    );

    scene.add(ledRed);


    var ledYellow = buildLED(mat.ledYellow);

    ledYellow.position.set(
    0,
    0,
    -2.55
    );

    scene.add(ledYellow);


    var ledGreen = buildLED(mat.ledGreen);

    ledGreen.position.set(
    0.55,
    0,
    -2.55
    );

    scene.add(ledGreen);
  // ---------------------------------------------------------------
  // Resize + render loop
  // ---------------------------------------------------------------
  function onResize() {
    var w = container.clientWidth;
    var h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener("resize", onResize);

  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();
})();