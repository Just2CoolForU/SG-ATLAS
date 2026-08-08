# -*- coding: utf-8 -*-
"""
shared_ui.py -- design tokens + reusable UI pieces shared by every page of
the SG-ATLAS site (homepage, tool, database, about).

Kept in one place so the whole site shares one source of truth for colors,
fonts, and the top navigation bar -- change a value here and it updates
everywhere, rather than hunting through four separate page files.

Colors and fonts below were sampled/identified directly from the approved
homepage reference image, not guessed:
  - background:        #FFFFFF
  - title / nav navy:  #1A385E
  - crystal line art:  #ADADAD
  - primary button:    #75C6FB
  - secondary button:  #D3D3CE (fill) / #B9B9B2 (border) / #8B8B84 (text)
  - body/subtitle text:#2E2F2F

Font pairing (per your selection): Poppins for display/body text, Space
Mono for the wide-tracked nav labels and the "6XYO"-style structure code
labels.
"""

import os
import streamlit as st

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#FFFFFF",
    "navy": "#1A385E",
    "navy_dark": "#122C49",
    "crystal_gray": "#ADADAD",
    "btn_primary": "#75C6FB",
    "btn_primary_hover": "#58B4EE",
    "btn_secondary_bg": "#D3D3CE",
    "btn_secondary_border": "#B9B9B2",
    "btn_secondary_text": "#8B8B84",
    "btn_secondary_text_hover": "#5B5B54",
    "charcoal": "#2E2F2F",
}

FONT_DISPLAY = "'Poppins', sans-serif"
FONT_BODY = "'Poppins', sans-serif"
FONT_MONO = "'Space Mono', 'Courier New', monospace"

GOOGLE_FONTS_IMPORT = (
    "https://fonts.googleapis.com/css2?"
    "family=Poppins:wght@400;500;600;700;800;900&"
    "family=Space+Mono:wght@400;700&display=swap"
)


def inject_global_css():
    """Fonts + base styling shared by every page. Call once per page,
    right after st.set_page_config in the entry script -- Streamlit reruns
    the whole script on every interaction, so this is cheap and keeps every
    page visually consistent without importing the CSS four separate times
    with four separate chances to drift out of sync.

    Uses st.html() rather than st.markdown(..., unsafe_allow_html=True).
    The markdown route sends this string through Streamlit's markdown/HTML
    parser first, and that parser has a long-documented failure mode where
    a blank line partway through a big injected <style> block causes
    everything after it to be dumped out as literal visible text instead
    of being applied as CSS (streamlit/streamlit#586, #5868, #859) --
    exactly the "raw CSS text at the top of the page" bug this replaces.
    st.html() renders the string directly with no markdown pass, so this
    class of bug can't happen here regardless of blank lines/formatting."""
    st.html(
        f"""
        <style>
        @import url('{GOOGLE_FONTS_IMPORT}');

        :root {{
            --sg-bg: {COLORS['bg']};
            --sg-navy: {COLORS['navy']};
            --sg-navy-dark: {COLORS['navy_dark']};
            --sg-crystal-gray: {COLORS['crystal_gray']};
            --sg-btn-primary: {COLORS['btn_primary']};
            --sg-btn-primary-hover: {COLORS['btn_primary_hover']};
            --sg-btn-secondary-bg: {COLORS['btn_secondary_bg']};
            --sg-btn-secondary-border: {COLORS['btn_secondary_border']};
            --sg-btn-secondary-text: {COLORS['btn_secondary_text']};
            --sg-btn-secondary-text-hover: {COLORS['btn_secondary_text_hover']};
            --sg-charcoal: {COLORS['charcoal']};
            --font-display: {FONT_DISPLAY};
            --font-body: {FONT_BODY};
            --font-mono: {FONT_MONO};
        }}

        html, body, [class*="css"] {{
            font-family: var(--font-body);
        }}

        .block-container {{
            padding-top: 0 !important;
            padding-bottom: 2rem;
            max-width: 1200px;
        }}

        #MainMenu, footer {{
            background: transparent;
        }}

        /* Streamlit's built-in header (Share / star / edit / GitHub / menu
        icons) stays in the DOM even when made transparent -- it's a
        fixed-position, full-width bar that sits above the rest of the page
        in stacking order. Making it transparent alone left its hit area
        intact, which was silently swallowing clicks aimed at the top nav
        buttons right underneath it. Dropping its z-index below the nav's
        (and raising the nav's z-index) fixes clicks without hiding those
        controls. */
        header[data-testid="stHeader"] {{
            background: transparent;
            z-index: 1 !important;
        }}

        /* ---- Top nav bar (Home / SG Atlas / About) ------------------- */
        .st-key-sg_nav_wrap {{
            position: relative;
            z-index: 999;
            padding: 1.6rem 6% 1rem 6%;
        }}
        .st-key-sg_nav_wrap [data-testid="stButton"] button {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: var(--sg-navy) !important;
            font-family: var(--font-mono) !important;
            font-weight: 700 !important;
            letter-spacing: 0.32em !important;
            font-size: clamp(0.7rem, 1vw, 0.95rem) !important;
            text-transform: uppercase !important;
            padding: 0.35rem 0.2rem !important;
            border-radius: 0 !important;
            transition: opacity 0.15s ease, transform 0.15s ease;
        }}
        .st-key-sg_nav_wrap [data-testid="stButton"] button:hover {{
            opacity: 0.6;
            transform: translateY(-1px);
        }}
        .st-key-sg_nav_wrap [data-testid="stButton"] button:focus-visible {{
            outline: 3px solid var(--sg-btn-primary);
            outline-offset: 3px;
        }}

        /* ---- Hero CTA pill buttons ------------------------------------ */
        .st-key-sg_cta_primary [data-testid="stButton"] button {{
            background: var(--sg-btn-primary) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 999px !important;
            padding: 0.85rem 2.1rem !important;
            font-family: var(--font-display) !important;
            font-weight: 700 !important;
            font-size: clamp(0.9rem, 1vw, 1.05rem) !important;
            box-shadow: 0 10px 22px rgba(117, 198, 251, 0.45) !important;
            transition: background 0.15s ease, transform 0.15s ease;
        }}
        .st-key-sg_cta_primary [data-testid="stButton"] button:hover {{
            background: var(--sg-btn-primary-hover) !important;
            transform: translateY(-2px);
        }}
        .st-key-sg_cta_secondary [data-testid="stButton"] button {{
            background: var(--sg-btn-secondary-bg) !important;
            color: var(--sg-btn-secondary-text) !important;
            border: 2px solid var(--sg-btn-secondary-border) !important;
            border-radius: 999px !important;
            padding: 0.85rem 2.1rem !important;
            font-family: var(--font-display) !important;
            font-weight: 700 !important;
            font-size: clamp(0.9rem, 1vw, 1.05rem) !important;
            box-shadow: none !important;
            transition: color 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
        }}
        .st-key-sg_cta_secondary [data-testid="stButton"] button:hover {{
            color: var(--sg-btn-secondary-text-hover) !important;
            border-color: var(--sg-btn-secondary-text-hover) !important;
            transform: translateY(-2px);
        }}
        .st-key-sg_nav_wrap [data-testid="stButton"] button:active,
        .st-key-sg_cta_primary [data-testid="stButton"] button:active,
        .st-key-sg_cta_secondary [data-testid="stButton"] button:active {{
            transform: translateY(0);
        }}

        /* ---- Floating crystal background ------------------------------ */
        /* Each of the 4 crystal SVGs (assets/crystal_1-4.svg) is a single
        wireframe gem, tightly cropped to its own content -- see the repo's
        asset-prep notes. Position/size is set per-layer here (not a shared
        inset:0 rule) so 3 crystals bleed off the hero's edges and one sits
        large and mostly-visible near the title, matching the approved
        reference mockup. Opacity (not `stroke`) is what lightens these
        toward the site's gray token: the crystal art is a masked raster
        image inside each SVG, not vector <path stroke="...">, so a CSS
        `stroke` override has nothing to attach to -- opacity against the
        white page background is what gets the right visual weight. */
        .sg-crystal-layer {{
            position: absolute;
            pointer-events: none;
            opacity: 0.38;
        }}
        .sg-crystal-layer svg {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        .sg-crystal-1 {{ top: -16%; right: -8%; width: 17%; height: 60%; }}
        .sg-crystal-2 {{ top: 2%; left: 18%; width: 20%; height: 72%; z-index: 1; }}
        .sg-crystal-3 {{ bottom: -14%; left: -10%; width: 19%; height: 66%; }}
        .sg-crystal-4 {{ bottom: -30%; right: 20%; width: 16%; height: 58%; }}
        @keyframes sgFloatA {{
            0%   {{ transform: translate(0px, 0px) rotate(0deg); }}
            50%  {{ transform: translate(6px, -14px) rotate(1.6deg); }}
            100% {{ transform: translate(0px, 0px) rotate(0deg); }}
        }}
        @keyframes sgFloatB {{
            0%   {{ transform: translate(0px, 0px) rotate(0deg); }}
            50%  {{ transform: translate(-10px, 10px) rotate(-2deg); }}
            100% {{ transform: translate(0px, 0px) rotate(0deg); }}
        }}
        @keyframes sgFloatC {{
            0%   {{ transform: translate(0px, 0px) rotate(0deg); }}
            50%  {{ transform: translate(8px, 12px) rotate(1.1deg); }}
            100% {{ transform: translate(0px, 0px) rotate(0deg); }}
        }}
        @keyframes sgFloatD {{
            0%   {{ transform: translate(0px, 0px) rotate(0deg); }}
            50%  {{ transform: translate(-7px, -9px) rotate(-1.4deg); }}
            100% {{ transform: translate(0px, 0px) rotate(0deg); }}
        }}
        .sg-crystal-1 {{ animation: sgFloatA 16s ease-in-out infinite; transform-origin: 85% 10%; }}
        .sg-crystal-2 {{ animation: sgFloatB 21s ease-in-out infinite; transform-origin: 30% 35%; }}
        .sg-crystal-3 {{ animation: sgFloatC 19s ease-in-out infinite; transform-origin: 10% 90%; }}
        .sg-crystal-4 {{ animation: sgFloatD 24s ease-in-out infinite; transform-origin: 90% 90%; }}

        @media (prefers-reduced-motion: reduce) {{
            .sg-crystal-1, .sg-crystal-2, .sg-crystal-3, .sg-crystal-4 {{
                animation: none !important;
            }}
        }}

        /* ---- Generic page shell for non-hero pages --------------------- */
        .sg-page-title {{
            font-family: var(--font-display);
            font-weight: 800;
            color: var(--sg-navy);
            font-size: clamp(2rem, 2.4vw + 1.2rem, 3rem);
            margin: 0.4rem 0 0.2rem 0;
        }}
        .sg-page-subtitle {{
            font-family: var(--font-body);
            color: var(--sg-charcoal);
            opacity: 0.75;
            font-size: clamp(1rem, 0.6vw + 0.85rem, 1.15rem);
            margin-bottom: 1.6rem;
        }}
        .sg-mono-label {{
            font-family: var(--font-mono);
            letter-spacing: 0.25em;
            text-transform: uppercase;
            color: var(--sg-navy);
        }}
        </style>
        """
    )


# ---------------------------------------------------------------------------
# Top navigation bar -- real st.button widgets styled as the wide-tracked
# nav text from the reference image, wired to st.switch_page so this is
# actual site navigation (not a decorative static header).
#
# Wrapped in st.container(key=...) -- Streamlit's own supported mechanism
# for styling a container that holds other widgets -- rather than opening
# an HTML <div> in one call and closing it in another. That "unclosed div"
# trick relies on raw markdown/HTML parsing behavior across separate calls,
# which is the same fragile mechanism behind the bug this whole file just
# got rewritten to avoid.
# ---------------------------------------------------------------------------
def render_top_nav(pages, active=None):
    """pages: dict like {"HOME": home_page, "SG ATLAS": tool_page, "ABOUT": about_page}
    active: key of the currently-active page (reserved for future
    highlighting -- not styled distinctly today since the reference design
    shows all three nav items in the same weight regardless of which page
    you're on)."""
    with st.container(key="sg_nav_wrap"):
        cols = st.columns(len(pages))
        for col, (label, target) in zip(cols, pages.items()):
            with col:
                # use_container_width=True so each label centers within its
                # own equal-width column (left/middle/right thirds) -- the
                # simplest reliable way to get the reference image's
                # evenly-spaced, spread-wide nav layout out of a real button.
                if st.button(label.upper(), key=f"nav_{label}", use_container_width=True):
                    st.switch_page(target)


# ---------------------------------------------------------------------------
# Floating crystal background -- reads 4 SVG assets (assets/crystal_1-4.svg),
# each a single wireframe gem already cropped tightly to its own content and
# scaled to fill its box via preserveAspectRatio="none" (baked into the file,
# not rewritten here). Position/size for each is set in CSS (.sg-crystal-1
# through -4, see inject_global_css) rather than a shared inset:0 rule, so 3
# crystals bleed off the hero's edges and one sits large behind the title --
# matching the approved reference mockup, not just tiling one full-bleed
# sprite behind everything.
# ---------------------------------------------------------------------------
_CRYSTAL_FILES = ["crystal_1.svg", "crystal_2.svg", "crystal_3.svg", "crystal_4.svg"]


@st.cache_data(show_spinner=False)
def _load_crystal_svgs():
    svgs = []
    for fname in _CRYSTAL_FILES:
        path = os.path.join(ASSETS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                svgs.append(f.read())
        except FileNotFoundError:
            svgs.append(None)
    return svgs


def render_crystal_background():
    """Emits the 4 layered, slowly-floating crystal SVGs. Must be called
    inside a positioned (position:relative) container so the absolutely
    positioned layers anchor to that container rather than the page.

    If none of the 4 SVG assets could be loaded (e.g. the assets/ folder
    wasn't deployed alongside the app), there's nothing to render -- calling
    st.html("") in that case raises StreamlitAPIException("st.html body
    cannot be empty") and crashes the whole page. Skip the call entirely
    instead; the hero still renders, just without the floating background."""
    svgs = _load_crystal_svgs()
    html_parts = []
    for i, svg in enumerate(svgs, start=1):
        if svg is None:
            continue
        html_parts.append(
            f'<div class="sg-crystal-layer sg-crystal-{i}">{svg}</div>'
        )
    if not html_parts:
        return
    st.html("".join(html_parts))


# ---------------------------------------------------------------------------
# Protein showcase placeholder -- functional stand-in for the real 6XYO
# animation, which will be dropped in later. Kept behind one function so
# swapping in the real animation later means editing only this function.
# ---------------------------------------------------------------------------
def render_protein_showcase(pdb_id="6XYO", height=200):
    """
    PLACEHOLDER for the future 6XYO structure animation.

    Renders an original static ball-and-stick illustration in the same
    spot/size the real animation will occupy, so the layout, spacing, and
    surrounding chevron/label elements never need to move when the real
    animation is dropped in -- only the inside of this function changes.

    To wire in the real animation later: replace the st.markdown(...) call
    below with the animation's own render call (e.g. an HTML/JS component,
    a py3Dmol view via pymol_viewer.render_pdb_3d, or a Streamlit custom
    component), keeping the same `height` footprint so surrounding layout
    is undisturbed.
    """
    dot_colors = ["#E63946", "#2A6FB0", "#3FA34D", "#F2A93B", "#7C5CBF", "#3FA34D", "#E63946", "#2A6FB0"]
    # A loose zig-zag backbone with alternating side atoms -- an original
    # illustration, not a reproduction of any specific PDB rendering.
    points = [(20, 70), (55, 40), (90, 65), (125, 35), (160, 60), (195, 30), (225, 55), (255, 40)]
    branch_offsets = [(-14, 26), (16, -24), (-16, 26), (14, -26), (-14, 26), (16, -24), (-14, 24), (14, -22)]

    circles = []
    lines = []
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#B9B9B9" stroke-width="3"/>')
    for i, (x, y) in enumerate(points):
        bx, by = branch_offsets[i]
        lines.append(f'<line x1="{x}" y1="{y}" x2="{x+bx}" y2="{y+by}" stroke="#B9B9B9" stroke-width="3"/>')
        circles.append(f'<circle cx="{x+bx}" cy="{y+by}" r="7" fill="{dot_colors[(i+3) % len(dot_colors)]}"/>')
        circles.append(f'<circle cx="{x}" cy="{y}" r="9" fill="{dot_colors[i % len(dot_colors)]}"/>')

    svg = f"""
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:{height}px;">
      <svg viewBox="0 0 275 100" style="width:100%; max-width:340px; height:auto; overflow:visible;">
        <ellipse cx="140" cy="95" rx="95" ry="9" fill="#000000" opacity="0.06"/>
        {''.join(lines)}
        {''.join(circles)}
      </svg>
      <div class="sg-mono-label" style="margin-top: 0.6rem; font-size: clamp(1rem, 1.3vw, 1.4rem); font-weight:700;">
        {pdb_id}
      </div>
    </div>
    """
    st.html(svg)


def render_chevrons(direction="left"):
    """Decorative layered chevron stack matching the reference image's
    arrow motif flanking the protein showcase. Purely decorative (no
    click behavior specified in the brief)."""
    flip = "scaleX(-1)" if direction == "right" else "none"
    paths = []
    opacities = [1, 0.65, 0.4, 0.2]
    for i, op in enumerate(opacities):
        offset = i * 11
        paths.append(
            f'<polyline points="{34-offset},4 {6-offset},34 {34-offset},64" '
            f'fill="none" stroke="var(--sg-navy)" stroke-width="4" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="{op}"/>'
        )
    svg = f"""
    <div style="display:flex; align-items:center; justify-content:center; height:100%; transform:{flip};">
      <svg viewBox="-10 0 55 68" style="width:56px; height:auto;">
        {''.join(paths)}
      </svg>
    </div>
    """
    st.html(svg)
