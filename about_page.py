# -*- coding: utf-8 -*-
"""
about_page.py -- placeholder. Per your instruction, this stays a simple
"coming soon" page for now rather than guessing at final copy -- swap the
body of this file for the real About content whenever you're ready and
the top nav / styling won't need to change at all.
"""

import streamlit as st

from nav_config import TOP_NAV_PAGES
from shared_ui import render_top_nav

render_top_nav(TOP_NAV_PAGES, active="About")

st.html('<p class="sg-page-title">About</p>')
st.html(
    '<p class="sg-page-subtitle">Coming soon.</p>',
)

st.write(
    "This page is a placeholder so the site's navigation is fully wired up "
    "end to end. Tell me what you'd like here \u2014 the full project story from "
    "the overview doc, a short blurb, team/citation info, or something else "
    "\u2014 and I'll build it out to match the rest of the site."
)
