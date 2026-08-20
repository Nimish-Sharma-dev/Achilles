// Achilles Hardware Digital Twin — Tinkercad-style breadboard scene.
// Pure Three.js. No frameworks, no UI chrome — just the 3D workspace.

(function () {
  "use strict";

  var container = document.getElementById("twin-canvas");
  container.style.position = "relative";
  container.style.overflow = "hidden";
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
  // ---------------------------------------------------------------
  // Tinkercad-style navigation cube
  // ---------------------------------------------------------------

  var navCubeScene = new THREE.Scene();

  var navCubeCamera = new THREE.OrthographicCamera(
    -2.4, 2.4, 2.4, -2.4, 0.1, 100
  );

  navCubeCamera.position.set(0, 0, 6);
  navCubeCamera.lookAt(0, 0, 0);

  var navCubeRenderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true
  });

  navCubeRenderer.setPixelRatio(
    Math.min(window.devicePixelRatio, 2)
  );

  navCubeRenderer.setSize(170, 170);

  navCubeRenderer.domElement.style.position = "absolute";
  navCubeRenderer.domElement.style.top = "16px";
  navCubeRenderer.domElement.style.right = "16px";
  navCubeRenderer.domElement.style.width = "170px";
  navCubeRenderer.domElement.style.height = "170px";
  navCubeRenderer.domElement.style.zIndex = "20";
  navCubeRenderer.domElement.style.cursor = "pointer";

  container.style.position = "relative";
  container.appendChild(navCubeRenderer.domElement);


  // ---------------------------------------------------------------
  // Cube — Tinkercad-style navigation cube
  // ---------------------------------------------------------------

  var navCubeGeometry =
    new THREE.BoxGeometry(2.0, 2.0, 2.0);

  // Flat materials keep the cube clean and readable.
  var navCubeMaterials = [
    new THREE.MeshBasicMaterial({ color: 0xdfe7ec }),
    new THREE.MeshBasicMaterial({ color: 0xdfe7ec }),
    new THREE.MeshBasicMaterial({ color: 0xc9d7df }),
    new THREE.MeshBasicMaterial({ color: 0xc9d7df }),
    new THREE.MeshBasicMaterial({ color: 0xb9cbd5 }),
    new THREE.MeshBasicMaterial({ color: 0xb9cbd5 })
  ];

  var navCube = new THREE.Mesh(
    navCubeGeometry,
    navCubeMaterials
  );

  navCubeScene.add(navCube);

  // Dark outline
  var navCubeEdges = new THREE.LineSegments(
    new THREE.EdgesGeometry(navCubeGeometry),
    new THREE.LineBasicMaterial({
      color: 0x53636d,
      transparent: true,
      opacity: 0.95
    })
  );

  navCube.add(navCubeEdges);

  // ---------------------------------------------------------------
  // Face labels
  // ---------------------------------------------------------------

  function makeCubeLabel(text) {

    var canvas = document.createElement("canvas");

    canvas.width = 512;
    canvas.height = 256;

    var ctx = canvas.getContext("2d");

    ctx.clearRect(
      0,
      0,
      canvas.width,
      canvas.height
    );

    ctx.font =
      "700 58px Arial, sans-serif";

    ctx.fillStyle = "#26343d";

    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.fillText(
      text,
      256,
      128
    );

    var texture =
      new THREE.CanvasTexture(canvas);

    texture.minFilter =
      THREE.LinearFilter;

    texture.magFilter =
      THREE.LinearFilter;

    var material =
      new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        depthWrite: false
      });

    return new THREE.Mesh(
      new THREE.PlaneGeometry(1.35, 0.68),
      material
    );
  }

  // TOP
  var topLabel =
    makeCubeLabel("TOP");

  topLabel.position.set(
    0,
    1.006,
    0
  );

  topLabel.rotation.x =
    -Math.PI / 2;

  navCube.add(topLabel);

  // FRONT
  var frontLabel =
    makeCubeLabel("FRONT");

  frontLabel.position.set(
    0,
    0,
    1.006
  );

  navCube.add(frontLabel);

  // RIGHT
  var rightLabel =
    makeCubeLabel("RIGHT");

  rightLabel.position.set(
    1.006,
    0,
    0
  );

  rightLabel.rotation.y =
    Math.PI / 2;

  navCube.add(rightLabel);

  // LEFT
  var leftLabel =
    makeCubeLabel("LEFT");

  leftLabel.position.set(
    -1.006,
    0,
    0
  );

  leftLabel.rotation.y =
    -Math.PI / 2;

  navCube.add(leftLabel);

  // BACK
  var backLabel =
    makeCubeLabel("BACK");

  backLabel.position.set(
    0,
    0,
    -1.006
  );

  backLabel.rotation.y =
    Math.PI;

  navCube.add(backLabel);

  // BOTTOM
  var bottomLabel =
    makeCubeLabel("BOTTOM");

  bottomLabel.position.set(
    0,
    -1.006,
    0
  );

  bottomLabel.rotation.x =
    Math.PI / 2;

  navCube.add(bottomLabel);

  // ---------------------------------------------------------------
  // Lighting
  // ---------------------------------------------------------------

  navCubeScene.add(
    new THREE.AmbientLight(0xffffff, 2.0)
  );

  var navLight =
    new THREE.DirectionalLight(0xffffff, 2.5);

  navLight.position.set(3, 5, 6);

  navCubeScene.add(navLight);


  // ---------------------------------------------------------------
  // Cube interaction
  // ---------------------------------------------------------------

  var navRaycaster = new THREE.Raycaster();

  var navMouse = new THREE.Vector2();

  navCubeRenderer.domElement.addEventListener(
    "click",
    function(event) {

      var rect =
        navCubeRenderer.domElement.getBoundingClientRect();

      navMouse.x =
        ((event.clientX - rect.left) / rect.width) * 2 - 1;

      navMouse.y =
        -((event.clientY - rect.top) / rect.height) * 2 + 1;

      navRaycaster.setFromCamera(
        navMouse,
        navCubeCamera
      );

      var hits =
        navRaycaster.intersectObject(navCube);

      if (!hits.length) {
        return;
      }

      // Determine the clicked point on the cube.
      var localPoint =
        hits[0].point.clone();

      // Convert the point into cube-local coordinates.
      localPoint.applyQuaternion(
        navCube.quaternion.clone().invert()
      );

      // Convert the clicked point into a direction.
      // This is what enables face + edge + corner views.
      var direction =
        localPoint.normalize();

      // Convert back to world space.
      var worldDirection =
        direction.clone().applyQuaternion(
          navCube.quaternion
        );

      snapCameraToDirection(worldDirection);
    }
  );


  // ---------------------------------------------------------------
  // Camera snapping
  // ---------------------------------------------------------------

  function snapCameraToDirection(direction) {

    var distance = 22;

    var target =
      controls.target.clone();

    // Quantize the direction slightly so edge/corner clicks
    // produce stable Tinkercad-style orthographic directions.
    var x = Math.abs(direction.x) > 0.28
      ? Math.sign(direction.x)
      : 0;

    var y = Math.abs(direction.y) > 0.28
      ? Math.sign(direction.y)
      : 0;

    var z = Math.abs(direction.z) > 0.28
      ? Math.sign(direction.z)
      : 0;

    // Safety fallback.
    if (x === 0 && y === 0 && z === 0) {
      y = 1;
    }

  var snappedDirection =
    new THREE.Vector3(x, y, z).normalize();

  var destination =
    target.clone().add(
      snappedDirection.multiplyScalar(distance)
    );
    var start =
      camera.position.clone();

    var startTime =
      performance.now();

    var duration = 400;

    function animateSnap(now) {

      var t =
        Math.min(
          (now - startTime) / duration,
          1
        );

      var eased =
        t * (2 - t);

      camera.position.lerpVectors(
        start,
        destination,
        eased
      );

      camera.lookAt(target);

      if (t < 1) {

        requestAnimationFrame(
          animateSnap
        );

      } else {

        controls.target.copy(target);
        controls.update();

      }
    }

    requestAnimationFrame(
      animateSnap
    );
  }
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
  // Achilles physical telemetry state
  // ---------------------------------------------------------------

  var telemetry = {
    mode: "NORMAL",

    dht22: {
      temperature: 31.6,
      humidity: 63.2,
      status: "NORMAL"
    },

    ina219: {
      voltage: 12.08,
      current: 0.82,
      power: 9.91,
      status: "NORMAL"
    },

    flash: {
      firmware: "W25Q128",
      hash: "MATCH",
      attestation: "VALID",
      status: "NORMAL"
    },

    max485: {
      rx: "ACTIVE",
      tx: "ACTIVE",
      packetLoss: 0.2,
      status: "TRUSTED"
    },

    trustScore: 98,
    decision: "TRUSTED"
  };

  // ---------------------------------------------------------------
  // Physical telemetry inspection panel
  // ---------------------------------------------------------------

  var telemetryPanel =
    document.createElement("div");

  telemetryPanel.style.position = "absolute";
  telemetryPanel.style.left = "18px";
  telemetryPanel.style.top = "18px";
  telemetryPanel.style.width = "250px";
  telemetryPanel.style.padding = "14px";
  telemetryPanel.style.background = "rgba(247,250,252,0.97)";
  telemetryPanel.style.boxShadow =
  "0 8px 24px rgba(0,0,0,0.18)";
  telemetryPanel.style.borderLeft =
    "4px solid #1683c7";
  telemetryPanel.style.lineHeight =
    "1.45";
  telemetryPanel.style.border = "1px solid #cfd3d8";
  telemetryPanel.style.borderRadius = "6px";
  telemetryPanel.style.fontFamily = "Arial, sans-serif";
  telemetryPanel.style.fontSize = "12px";
  telemetryPanel.style.color = "#20242a";
  telemetryPanel.style.zIndex = "15";
  telemetryPanel.style.display = "none";
  telemetryPanel.style.pointerEvents = "none";

  container.appendChild(telemetryPanel);

  // ---------------------------------------------------------------
  // Power-grid topology context
  // ---------------------------------------------------------------

  var gridContext = document.createElement("div");

  gridContext.style.position = "absolute";
  gridContext.style.left = "18px";
  gridContext.style.bottom = "110px";
  gridContext.style.width = "300px";
  gridContext.style.height = "170px";
  gridContext.style.display = "block";
  gridContext.style.visibility = "visible";
  gridContext.style.opacity = "1";
  gridContext.style.background = "rgba(255,255,255,0.94)";
  gridContext.style.border = "1px solid #9aa9b3";
  gridContext.style.borderRadius = "6px";
  gridContext.style.boxShadow =
    "0 6px 18px rgba(0,0,0,0.16)";
  gridContext.style.zIndex = "12";
  gridContext.style.pointerEvents = "none";
  gridContext.style.fontFamily =
    "Arial, sans-serif";

  gridContext.innerHTML = `
  <svg
    width="300"
    height="170"
    viewBox="0 0 300 170"
    xmlns="http://www.w3.org/2000/svg"
  >

    <text
      x="150"
      y="20"
      text-anchor="middle"
      font-family="Arial"
      font-size="13"
      font-weight="700"
      fill="#26343d"
    >
      POWER GRID — IED LOCATION
    </text>

    <!-- Grid connection -->
    <line
      x1="150" y1="48"
      x2="150" y2="70"
      stroke="#596a75"
      stroke-width="2"
    />

    <!-- Control center -->
    <rect
      x="100" y="30"
      width="100"
      height="20"
      rx="3"
      fill="#dfe7ec"
      stroke="#53636d"
    />

    <text
      x="150"
      y="44"
      text-anchor="middle"
      font-family="Arial"
      font-size="10"
      font-weight="600"
      fill="#26343d"
    >
      CONTROL CENTER
    </text>

    <!-- Main bus -->
    <line
      x1="45" y1="72"
      x2="255" y2="72"
      stroke="#53636d"
      stroke-width="3"
    />

    <!-- Branches -->
    <line
      x1="75" y1="72"
      x2="75" y2="100"
      stroke="#53636d"
      stroke-width="2"
    />

    <line
      x1="150" y1="72"
      x2="150" y2="100"
      stroke="#53636d"
      stroke-width="2"
    />

    <line
      x1="225" y1="72"
      x2="225" y2="100"
      stroke="#53636d"
      stroke-width="2"
    />

    <!-- Node 1 -->
    <rect
      x="45" y="100"
      width="60"
      height="24"
      rx="3"
      fill="#eef2f4"
      stroke="#7b8a93"
    />

    <text
      x="75"
      y="115"
      text-anchor="middle"
      font-family="Arial"
      font-size="9"
      fill="#26343d"
    >
      RELAY
    </text>

    <!-- Node 2 -->
    <rect
      x="120" y="100"
      width="60"
      height="24"
      rx="3"
      fill="#eef2f4"
      stroke="#7b8a93"
    />

    <text
      x="150"
      y="115"
      text-anchor="middle"
      font-family="Arial"
      font-size="9"
      fill="#26343d"
    >
      RTU
    </text>

    <!-- Achilles IED -->
    <rect
      x="195" y="96"
      width="60"
      height="32"
      rx="3"
      fill="#d9eef9"
      stroke="#1683c7"
      stroke-width="2"
    />

    <text
      x="225"
      y="110"
      text-anchor="middle"
      font-family="Arial"
      font-size="9"
      font-weight="700"
      fill="#126a9e"
    >
      IED
    </text>

    <text
      x="225"
      y="121"
      text-anchor="middle"
      font-family="Arial"
      font-size="7"
      fill="#126a9e"
    >
      ACHILLES NODE
    </text>

    <!-- Physical node indicator -->
    <line
      x1="225" y1="128"
      x2="225" y2="143"
      stroke="#1683c7"
      stroke-width="2"
    />

    <circle
      cx="225"
      cy="148"
      r="5"
      fill="#1683c7"
    />

    <text
      x="150"
      y="164"
      text-anchor="middle"
      font-family="Arial"
      font-size="8"
      fill="#697780"
    >
      SECURITY HARDWARE ATTACHED AT IED
    </text>

  </svg>
  `;

  container.appendChild(gridContext);
  function showTelemetry(title, rows) {

    telemetryPanel.style.display = "block";

    var html =
      '<div style="font-size:15px;font-weight:700;margin-bottom:10px;">' +
      title +
      '</div>';

    rows.forEach(function(row) {

      html +=
        '<div style="display:flex;justify-content:space-between;margin:5px 0;">' +
        '<span style="color:#6b7077;">' + row[0] + '</span>' +
        '<strong>' + row[1] + '</strong>' +
        '</div>';

    });

    telemetryPanel.innerHTML = html;
  }
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
  function buildResistor() {
    var g = new THREE.Group();

    var body = box(
      0.42,
      0.12,
      0.12,
      new THREE.MeshStandardMaterial({
        color: 0xd7c39b,
        roughness: 0.72
      })
    );

    body.position.y = 0.60;
    g.add(body);

    for (var b = 0; b < 3; b++) {
      var band = box(
        0.035,
        0.125,
        0.125,
        new THREE.MeshStandardMaterial({
          color: 0x6b4b3e,
          roughness: 0.7
        })
      );

      band.position.set(-0.10 + b * 0.10, 0.60, 0);
      g.add(band);
    }

    var lead1 = box(0.20, 0.025, 0.025, mat.wireLead);
    lead1.position.set(-0.31, 0.60, 0);
    g.add(lead1);

    var lead2 = box(0.20, 0.025, 0.025, mat.wireLead);
    lead2.position.set(0.31, 0.60, 0);
    g.add(lead2);

    return g;
  }

  function jumperWire(points, color, radius) {
    var curve = new THREE.CatmullRomCurve3(
      points.map(function(p) {
        return new THREE.Vector3(p[0], p[1], p[2]);
      })
    );

    var geometry = new THREE.TubeGeometry(
      curve,
      Math.max(12, points.length * 8),
      radius || 0.035,
      8,
      false
    );

    var material = new THREE.MeshStandardMaterial({
      color: color,
      roughness: 0.55
    });

    var mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;

    scene.add(mesh);

    return mesh;
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
    // LED current-limiting resistors
    var resistorRed = buildResistor();
    resistorRed.position.set(-0.55, 0, -2.15);
    scene.add(resistorRed);

    var resistorYellow = buildResistor();
    resistorYellow.position.set(0, 0, -2.15);
    scene.add(resistorYellow);

    var resistorGreen = buildResistor();
    resistorGreen.position.set(0.55, 0, -2.15);
    scene.add(resistorGreen);
    // ---------------------------------------------------------------
  // Hardware inspection
  // ---------------------------------------------------------------

  var selectableHardware = [
    {
      object: dht22,
      name: "DHT22",
      type: "dht"
    },
    {
      object: ina219,
      name: "INA219",
      type: "ina"
    },
    {
      object: flash,
      name: "W25Q128",
      type: "flash"
    },
    {
      object: max485,
      name: "MAX485",
      type: "max"
    },
    {
      object: stm32,
      name: "STM32",
      type: "stm"
    }
  ];

  var hardwareRaycaster =
    new THREE.Raycaster();

  var hardwareMouse =
    new THREE.Vector2();

  renderer.domElement.addEventListener(
    "click",
    function(event) {

      // Ignore clicks occurring over the navigation cube.
      if (
        event.clientX >
        window.innerWidth - 210
      ) {
        return;
      }

      var rect =
        renderer.domElement.getBoundingClientRect();

      hardwareMouse.x =
        ((event.clientX - rect.left) / rect.width) * 2 - 1;

      hardwareMouse.y =
        -((event.clientY - rect.top) / rect.height) * 2 + 1;

      hardwareRaycaster.setFromCamera(
        hardwareMouse,
        camera
      );

      for (
        var i = 0;
        i < selectableHardware.length;
        i++
      ) {

        var item =
          selectableHardware[i];

        var hits =
          hardwareRaycaster.intersectObject(
            item.object,
            true
          );

        if (!hits.length) {
          continue;
        }

        if (item.type === "dht") {

          showTelemetry(
            "DHT22 — ENVIRONMENTAL TELEMETRY",
            [
              ["Temperature", telemetry.dht22.temperature + " °C"],
              ["Humidity", telemetry.dht22.humidity + " %"],
              ["Status", telemetry.dht22.status]
            ]
          );

        } else if (item.type === "ina") {

          showTelemetry(
            "INA219 — POWER TELEMETRY",
            [
              ["Voltage", telemetry.ina219.voltage + " V"],
              ["Current", telemetry.ina219.current + " A"],
              ["Power", telemetry.ina219.power + " W"],
              ["Status", telemetry.ina219.status]
            ]
          );

        } else if (item.type === "flash") {

          showTelemetry(
            "W25Q128 — FIRMWARE INTEGRITY",
            [
              ["Firmware", telemetry.flash.firmware],
              ["Hash", telemetry.flash.hash],
              ["Attestation", telemetry.flash.attestation],
              ["Status", telemetry.flash.status]
            ]
          );

        } else if (item.type === "max") {

          showTelemetry(
            "MAX485 — COMMUNICATION TELEMETRY",
            [
              ["RX", telemetry.max485.rx],
              ["TX", telemetry.max485.tx],
              ["Packet loss", telemetry.max485.packetLoss + " %"],
              ["Link", telemetry.max485.status]
            ]
          );

        } else if (item.type === "stm") {

          showTelemetry(
            "STM32 — TRUST DECISION",
            [
              ["Trust score", telemetry.trustScore + " %"],
              ["Decision", telemetry.decision],
              ["Mode", telemetry.mode]
            ]
          );
        }

        return;
      }
    }
  );

    // Physical wiring
    // Red    = VCC
    // Black  = GND
    // Yellow = I2C / sensor
    // Blue   = SPI
    // Green  = UART / RS-485

    jumperWire([
      [-6.1, 0.68, 1.86],
      [-6.0, 0.95, 2.35],
      [3.0, 0.95, 2.35],
      [3.2, 0.68, 1.55]
    ], 0xd23c3c, 0.045);

    jumperWire([
      [-6.0, 0.68, 0.25],
      [-6.2, 0.88, -3.75],
      [3.2, 0.88, -3.75],
      [3.2, 0.68, -0.95]
    ], 0x222222, 0.045);

    jumperWire([
      [-2.25, 0.78, 1.55],
      [-1.55, 1.05, 1.95],
      [-0.75, 0.78, 1.95]
    ], 0xffd23b, 0.038);

    jumperWire([
      [-2.35, 0.78, 0.95],
      [-1.4, 1.15, 0.55],
      [2.25, 1.15, 0.55],
      [3.3, 0.78, 1.25]
    ], 0xffd23b, 0.038);

    jumperWire([
      [-3.55, 0.78, 0.15],
      [-3.85, 1.05, -0.55],
      [-3.35, 0.78, -1.10]
    ], 0x2f6fd2, 0.038);

    jumperWire([
      [-3.25, 0.78, 0.15],
      [-2.95, 1.00, -0.45],
      [-2.85, 0.78, -1.10]
    ], 0x2f6fd2, 0.034);

    jumperWire([
      [-2.35, 0.78, 0.55],
      [-1.55, 1.10, -0.05],
      [2.65, 1.10, -0.05],
      [3.15, 0.78, -0.20]
    ], 0xffd23b, 0.038);

    jumperWire([
      [-2.15, 0.78, 0.35],
      [-1.35, 0.95, -0.35],
      [2.55, 0.95, -0.45],
      [3.15, 0.78, -0.45]
    ], 0xffd23b, 0.034);

    jumperWire([
      [-2.15, 0.78, -0.05],
      [-1.25, 1.00, -0.90],
      [0.65, 1.00, -1.40],
      [0.80, 0.78, -1.45]
    ], 0x22aa55, 0.040);

    jumperWire([
      [-1.95, 0.78, -0.15],
      [-1.10, 0.90, -1.15],
      [0.95, 0.90, -1.55],
      [1.10, 0.78, -1.55]
    ], 0x22aa55, 0.034);
  // ---------------------------------------------------------------
  // Resize + render loop
  // ---------------------------------------------------------------
  function onResize() {

    var w = container.clientWidth;
    var h = container.clientHeight;

    camera.aspect = w / h;
    camera.updateProjectionMatrix();

    renderer.setSize(w, h);

    navCubeRenderer.setSize(
      170,
      170
    );
}
  window.addEventListener("resize", onResize);

  function animate() {
    requestAnimationFrame(animate);

    controls.update();

    // Keep navigation cube oriented with the main camera.
    navCube.quaternion.copy(camera.quaternion).invert();
    navCubeEdges.quaternion.copy(navCube.quaternion);

    renderer.render(scene, camera);

    navCubeRenderer.render(
      navCubeScene,
      navCubeCamera
    );
  }

animate();
})();