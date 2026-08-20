"""
Achilles Hardware Digital Twin — scene builder.

Standalone Three.js/WebGL breadboard visualization, rendered via
streamlit.components.v1.html. This module has no dependency on, and
makes no reference to, the existing Achilles simulation app. It is
used only by hardware/app.py.
"""

import os
from pathlib import Path

import streamlit.components.v1 as components

_HERE = Path(os.path.dirname(os.path.abspath(__file__)))
_SCENE_JS_PATH = _HERE / "scene.js"

# Classic (non-module) UMD builds — avoids ES-module/import-map issues
# inside the sandboxed iframe that components.html renders into, which
# is the most common cause of a blank Three.js canvas in that context.
_THREE_JS_CDN = "https://unpkg.com/three@0.128.0/build/three.min.js"
_ORBIT_CONTROLS_CDN = "https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js"


def _build_html(scene_js: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  html, body {{ margin: 0; padding: 0; background: #f4f5f7; overflow: hidden; }}
  #twin-canvas {{ width: 100%; height: 100vh; display: block; }}
  canvas {{ display: block; }}
</style>
</head>
<body>
<div id="twin-canvas"></div>
<script src="{_THREE_JS_CDN}"></script>
<script src="{_ORBIT_CONTROLS_CDN}"></script>
<script>
  window.addEventListener("error", function (e) {{
    var el = document.getElementById("twin-canvas");
    if (el && (!window.THREE || !THREE.OrbitControls)) {{
      el.innerHTML =
        '<div style="font-family:monospace;color:#8a1f1f;padding:16px;">' +
        'Three.js failed to load from CDN (' + (e && e.message ? e.message : "unknown error") +
        '). Check network access to unpkg.com.</div>';
    }}
  }});
</script>
<script>
{scene_js}
</script>
</body>
</html>"""


def render_hardware_scene(height: int = 760) -> None:
    """Render the breadboard digital twin. Call this and nothing else
    for the hardware view — it is a standalone 3D workspace, not a
    dashboard panel."""
    scene_js = _SCENE_JS_PATH.read_text(encoding="utf-8")
    html = _build_html(scene_js)
    components.html(html, height=height, scrolling=False)