"""
Achilles Hardware Digital Twin — standalone entry point.

Run directly and independently of the existing Achilles simulation app:

    streamlit run hardware/app.py

This file does not import `hardware` as a package (it imports its
sibling module `scene` directly, since Streamlit adds this script's
own directory to sys.path), and it does not import, modify, or start
any existing Achilles simulation code (dashboard, attack_injector, db,
detection, topology, ledger, ied_simulator, etc.).

First-draft scope, intentionally minimal: a pure Tinkercad-style 3D
circuit workspace. No navigation, no dashboard, no status panels.
"""

import streamlit as st

from scene import render_hardware_scene

st.set_page_config(
    page_title="Hardware Digital Twin",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Remove default Streamlit chrome/padding so the 3D canvas is the
# entire workspace — not a dashboard with a visualization inside it.
st.markdown(
    """
    <style>
      #MainMenu { visibility: hidden; }
      footer { visibility: hidden; }
      header { visibility: hidden; }
      .block-container { padding: 0; max-width: 100%; }
    </style>
    """,
    unsafe_allow_html=True,
)

render_hardware_scene(height=900)