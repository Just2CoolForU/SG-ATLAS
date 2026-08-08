# -*- coding: utf-8 -*-
"""
sg_atlas_app.py -- SG-ATLAS site entry point.

This is the file Streamlit Cloud should point at (it's the same filename
that was already configured as the deployment's main file, so no dashboard
settings need to change). Its only job is: set page config once, load the
shared fonts/CSS once, and hand off to st.navigation so every page (Home,
SG Atlas tool, Discover Database, About) is a real, routable, shareable
page rather than a single static script.

The researcher-facing matching dashboard that used to live directly in
this file has moved to sg_atlas_tool.py unchanged in behavior -- it's now
one page among four instead of the only thing this app could show.
"""

import streamlit as st

from nav_config import ALL_PAGES
from shared_ui import inject_global_css

st.set_page_config(
    page_title="SG-ATLAS",
    page_icon="\U0001F48E",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_global_css()

# position="hidden" removes Streamlit's default sidebar page list -- the
# reference design uses its own top nav bar (rendered per-page via
# shared_ui.render_top_nav), not Streamlit's built-in sidebar navigation.
pg = st.navigation(ALL_PAGES, position="hidden")
pg.run()
