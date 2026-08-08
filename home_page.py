# -*- coding: utf-8 -*-
"""
home_page.py -- SG-ATLAS homepage hero.

A direct build of the approved reference design: wide-tracked top nav,
the "SG / ATLAS" display title, corrected subtitle copy ("interpretive"
Cryo-EM tool -- both original typos fixed per your instructions), two CTA
pills that route to real pages, and a decorative molecule showcase flanked
by chevrons. The four crystal SVGs are layered behind everything and float
slowly and independently (see shared_ui.render_crystal_background).

Nothing here is static marketing chrome -- "Use Tool" and "Discover
Database" are real st.switch_page() navigations, same mechanism as the top
nav.
"""

import streamlit as st

from nav_config import TOP_NAV_PAGES, tool_page, database_page
from shared_ui import render_top_nav, render_crystal_background, render_protein_showcase, render_chevrons

# ---------------------------------------------------------------------------
# Hero-specific CSS (kept local to this page since nothing else needs it)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .sg-hero-outer {
        position: relative;
        overflow: hidden;
        min-height: 560px;
        padding-bottom: 3rem;
    }
    .sg-hero-content {
        position: relative;
        z-index: 2;
        padding: 1rem 6% 0 6%;
    }
    .sg-hero-title {
        font-family: var(--font-display);
        font-weight: 900;
        color: var(--sg-navy);
        line-height: 0.86;
        letter-spacing: -0.01em;
        margin: 0.5rem 0 0.9rem 0;
    }
    .sg-hero-title span {
        display: block;
        font-size: clamp(2.6rem, 3.4vw + 1.6rem, 5.1rem);
    }
    .sg-hero-subtitle {
        font-family: var(--font-body);
        font-weight: 500;
        color: var(--sg-charcoal);
        font-size: clamp(1rem, 0.55vw + 0.85rem, 1.2rem);
        margin: 0 0 1.6rem 0;
        max-width: 34ch;
    }
    .st-key-sg_cta_primary [data-testid="stButton"] button,
    .st-key-sg_cta_secondary [data-testid="stButton"] button {
        width: 100%;
    }
    @media (max-width: 640px) {
        .sg-hero-outer { min-height: 0; }
        .sg-hero-title { text-align: center; }
        .sg-hero-subtitle { max-width: none; text-align: center; margin-left: auto; margin-right: auto; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

render_top_nav(TOP_NAV_PAGES, active="Home")

# NOTE: the outer hero div is opened here and only closed at the very end
# of this file. Every Streamlit call in between (crystal layers, columns,
# buttons, the molecule showcase) renders as a real sibling DOM node in
# between the open and close tags, so the browser nests all of it inside
# this div -- the standard, well-documented way to get a Streamlit-native
# "positioned container that spans multiple widgets" without depending on
# internal framework class-naming details for something this layout-critical.
st.markdown('<div class="sg-hero-outer">', unsafe_allow_html=True)

render_crystal_background()

st.markdown('<div class="sg-hero-content">', unsafe_allow_html=True)

left_col, right_col = st.columns([1.05, 0.95], gap="large")

with left_col:
    st.markdown(
        '<div class="sg-hero-title"><span>SG</span><span>ATLAS</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sg-hero-subtitle">An interpretive tool for Cryo-EM Structures</p>',
        unsafe_allow_html=True,
    )

    btn_col1, btn_col2 = st.columns([1, 1.3], gap="small")
    with btn_col1:
        with st.container(key="sg_cta_primary"):
            if st.button("Use Tool", key="cta_use_tool", use_container_width=True):
                st.switch_page(tool_page)
    with btn_col2:
        with st.container(key="sg_cta_secondary"):
            if st.button("Discover Database", key="cta_discover_db", use_container_width=True):
                st.switch_page(database_page)

with right_col:
    chev_l, mol_col, chev_r = st.columns([0.16, 0.68, 0.16])
    with chev_l:
        render_chevrons("left")
    with mol_col:
        render_protein_showcase("6XYO", height=170)
    with chev_r:
        render_chevrons("right")

# Close .sg-hero-content then .sg-hero-outer (opened above).
st.markdown("</div></div>", unsafe_allow_html=True)
