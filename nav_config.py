# -*- coding: utf-8 -*-
"""
nav_config.py -- single source of truth for the site's pages.

Every page file imports its own st.Page object from here (rather than each
page constructing its own) so that st.navigation (in sg_atlas_app.py) and
every st.switch_page() call (in shared_ui.render_top_nav / hero buttons)
are always pointing at the exact same page objects. Two different st.Page
instances that happen to reference the same file are NOT guaranteed to be
treated as identical by Streamlit's router, so this is the safe pattern.
"""

import streamlit as st

home_page = st.Page("home_page.py", title="Home", url_path="home", default=True)
tool_page = st.Page("sg_atlas_tool.py", title="SG Atlas", url_path="sg-atlas")
database_page = st.Page("database_page.py", title="Discover Database", url_path="database")
about_page = st.Page("about_page.py", title="About", url_path="about")

ALL_PAGES = [home_page, tool_page, database_page, about_page]

# What the top nav bar shows, in order -- matches the reference image
# exactly (Home / SG Atlas / About only; the database page is reached via
# the homepage's "Discover Database" button, not the top nav).
TOP_NAV_PAGES = {
    "Home": home_page,
    "SG Atlas": tool_page,
    "About": about_page,
}
