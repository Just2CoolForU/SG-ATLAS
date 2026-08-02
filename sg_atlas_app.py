# -*- coding: utf-8 -*-
"""
sg_atlas_app.py -- SG-ATLAS researcher-facing dashboard.

Single-file Streamlit app: no separate backend, reads only from the local
cache (sg_atlas_cache.db) and the curated reference table
(known_structures.csv). Fragment-matching runs in-process by calling
sg_atlas_fragments.py directly.

Design principle carried over from the rest of the project: never fabricate
a number we don't actually have. Fields not present in the local cache
(EM software, atom counts, wwPDB validation percentiles) are labeled
"Not cached" with a link out to RCSB, rather than shown as static/guessed
values.
"""

import sqlite3
import pandas as pd
import streamlit as st

from sg_atlas_fragments import (
    match_observed_fragments, score_all_candidates, RESIDUE_MASS, WATER_MASS,
)

try:
    from pymol_viewer import render_pdb_3d
    VIEWER_AVAILABLE = True
except Exception:
    VIEWER_AVAILABLE = False

DB_PATH = "sg_atlas_cache.db"
CSV_PATH = "known_structures.csv"
MODE = "full-core"

st.set_page_config(
    page_title="SG-ATLAS",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Styling -- light theme, plain text, matching the reference wireframe
# (thin black borders, no gradients/pill badges, gray secondary text)
# ---------------------------------------------------------------------------
def inject_css():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1200px; }

        .top-nav {
            display: flex; gap: 28px; padding-bottom: 0.75rem;
            border-bottom: 1px solid #dddddd; margin-bottom: 1.75rem;
            font-size: 16px; font-weight: 700; color: #111111;
        }
        .top-nav span.active { border-bottom: 3px solid #2e7d32; padding-bottom: 6px; }
        .top-nav span.inactive { opacity: 0.55; }

        .header-title { font-size: 2.2rem; font-weight: 800; color: #111111; margin: 0; line-height: 1.15; }
        .header-subtitle { font-size: 1.05rem; color: #666666; margin: 2px 0 0 0; }
        .confidence-plain { font-size: 1.35rem; font-weight: 800; color: #111111; text-align: right; }
        .confidence-plain .pct { color: #1e3c72; }

        .detail-item {
            display: flex; justify-content: space-between; padding: 7px 0;
            border-bottom: 1px solid #eeeeee; font-size: 14px; color: #111111;
        }
        .detail-item:last-child { border-bottom: none; }
        .detail-label { color: #555555; }
        .detail-value { font-weight: 600; }
        .detail-value.na { color: #999999; font-weight: 400; font-style: italic; }

        .card-title { font-weight: 700; font-size: 15px; color: #111111; margin-bottom: 6px; }
        .not-cached-note { font-size: 12.5px; color: #888888; margin-top: 6px; }
        .not-cached-note a { color: #1e3c72; }

        .viewer-box {
            border: 1.5px solid #111111; border-radius: 10px; overflow: hidden;
            min-height: 420px; display: flex; align-items: center; justify-content: center;
            background: #fafafa;
        }
        .viewer-fallback { color: #999999; font-family: sans-serif; text-align: center; padding: 40px; }

        .footer-disclaimer { font-size: 12.5px; color: #999999; margin-top: 1.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()

# ---------------------------------------------------------------------------
# Data loading -- all read-only, all from local files, all cached
# ---------------------------------------------------------------------------
@st.cache_data
def load_known_structures():
    df = pd.read_csv(CSV_PATH)
    df["pdb_id"] = df["pdb_id"].str.upper()
    return df


@st.cache_data
def load_curated_atlas():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM curated_atlas", conn)
    conn.close()
    return df


@st.cache_data
def load_structure_ids():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT pdb_id, chain_ids FROM structures WHERE mode=?", conn, params=(MODE,)
    )
    conn.close()
    return sorted(df["pdb_id"].tolist())


@st.cache_data
def get_structure_profile(pdb_id):
    """Everything we can honestly say about a structure from local cache alone."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT chain_id, residue, amino_acid FROM residues WHERE pdb_id=? AND mode=?",
        (pdb_id, MODE),
    )
    rows = cur.fetchall()
    cur2 = conn.execute(
        "SELECT chain_ids FROM structures WHERE pdb_id=? AND mode=?", (pdb_id, MODE)
    )
    chain_row = cur2.fetchone()
    conn.close()

    if not rows:
        return None

    by_chain = {}
    for cid, resseq, aa in rows:
        by_chain.setdefault(cid, {})[resseq] = aa

    best_chain = max(by_chain, key=lambda c: len(by_chain[c]))
    profile = by_chain[best_chain]
    residues_sorted = sorted(profile.keys())
    est_mass = sum(RESIDUE_MASS.get(aa, 110.0) for aa in profile.values()) + WATER_MASS

    import json
    core_chain_count = len(json.loads(chain_row[0])) if chain_row else len(by_chain)

    return {
        "best_chain": best_chain,
        "modeled_residue_count": len(profile),
        "residue_range": (residues_sorted[0], residues_sorted[-1]),
        "core_chain_count": core_chain_count,
        "est_mass_kda": round(est_mass / 1000, 2),
    }


@st.cache_data
def run_mass_matching(observed_masses_tuple, tolerance_pct):
    return match_observed_fragments(
        list(observed_masses_tuple), tolerance_pct=tolerance_pct, db_path=DB_PATH
    )


@st.cache_data
def run_position_matching(observed_fragments_tuple, tolerance_window):
    return score_all_candidates(
        list(observed_fragments_tuple), tolerance_window=tolerance_window, db_path=DB_PATH
    )


known_df = load_known_structures()
curated_df = load_curated_atlas()
all_ids = load_structure_ids()

if not all_ids:
    st.error(
        "No structures found in sg_atlas_cache.db. Make sure the populated "
        "cache database is committed to the repo alongside this file."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Nav (decorative, matches reference)
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="top-nav"><span class="active">Home</span>'
    '<span class="inactive">About</span><span class="inactive">Contact Us</span></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Matching controls -- the actual input that drives the ranked table.
# Two independent modes, matching what sg_atlas_fragments.py supports:
#   1. Mass weights from MS/gel  -> match_observed_fragments()
#   2. Residue boundary positions -> score_all_candidates()
# Visible by default -- this got hidden behind a collapsed expander before,
# which is why the app looked static. Not doing that again.
# ---------------------------------------------------------------------------
st.subheader("Match your data against the cache")
mode = st.radio(
    "Input type",
    ["Mass weights (MS/gel)", "Residue positions (boundaries)"],
    horizontal=True,
)

def parse_masses(text):
    out = []
    for tok in text.split(","):
        tok = tok.strip()
        if tok:
            try:
                out.append(float(tok))
            except ValueError:
                pass
    return tuple(out)

def parse_positions(text):
    """Parses 'start-end, start-end' pairs into a tuple of (start, end) ints."""
    out = []
    for tok in text.split(","):
        tok = tok.strip()
        if not tok or "-" not in tok:
            continue
        a, _, b = tok.partition("-")
        try:
            out.append((int(a.strip()), int(b.strip())))
        except ValueError:
            pass
    return tuple(out)

if mode == "Mass weights (MS/gel)":
    st.caption(
        "Compares your gel/MS fragment masses against every cached structure's "
        "predicted Proteinase K digestion ladder."
    )
    masses_input = st.text_input(
        "Observed fragment masses (Da), comma-separated",
        value="4200, 8100, 12300",
    )
    tolerance = st.slider("Match tolerance (%)", 1.0, 15.0, 5.0, 0.5)
    run_clicked = st.button("Run test again", type="primary")

    if "match_results" not in st.session_state or run_clicked or st.session_state.get("last_mode") != "mass":
        masses = parse_masses(masses_input)
        if masses:
            with st.spinner("Matching against cached structures..."):
                raw = run_mass_matching(masses, tolerance)
                st.session_state["match_results"] = [
                    {"pdb_id": r["pdb_id"], "score": r["score"],
                     "matched_count": r["matched_count"], "evaluable_count": r["evaluable_count"]}
                    for r in raw
                ]
                st.session_state["last_mode"] = "mass"
                st.session_state["selected_pdb"] = None
        else:
            st.session_state["match_results"] = []

else:
    st.caption(
        "Compares observed fragment boundary residues (e.g. from N/C-terminal "
        "sequencing or a truncation you've mapped) against each cached "
        "structure's predicted cleavage sites. Uses a binomial test with "
        "Benjamini-Hochberg FDR correction across all structures."
    )
    positions_input = st.text_input(
        "Observed fragment boundaries, comma-separated pairs (start-end)",
        value="37-97, 40-90",
    )
    tol_window = st.slider("Position tolerance (residues)", 0, 5, 2, 1)
    run_clicked = st.button("Run test again", type="primary")

    if "match_results" not in st.session_state or run_clicked or st.session_state.get("last_mode") != "position":
        positions = parse_positions(positions_input)
        if positions:
            with st.spinner("Matching against cached structures..."):
                raw = run_position_matching(positions, tol_window)
                st.session_state["match_results"] = [
                    {"pdb_id": r["pdb_id"], "score": r["confidence"],
                     "matched_count": r["matches"], "evaluable_count": r["trials"],
                     "low_power_warning": r.get("low_power_warning", False)}
                    for r in raw
                ]
                st.session_state["last_mode"] = "position"
                st.session_state["selected_pdb"] = None
        else:
            st.session_state["match_results"] = []

results = st.session_state.get("match_results", [])

# Build the ranked candidates table from REAL results, not mock data
if results:
    rows = []
    for r in results[:25]:
        pdb_id = r["pdb_id"]
        known_row = known_df[known_df["pdb_id"] == pdb_id]
        curated_row = curated_df[curated_df["pdb_id"] == pdb_id]
        polymorph = known_row["polymorph_name"].iloc[0] if not known_row.empty else "Uncategorized"
        disease = known_row["disease_association"].iloc[0] if not known_row.empty else ""
        disease = disease if isinstance(disease, str) and disease.strip() else "Uncategorized"
        profile = get_structure_profile(pdb_id)
        bounds = f"{profile['residue_range'][0]}-{profile['residue_range'][1]}" if profile else "N/A"
        flag = " ⚠" if r.get("low_power_warning") else ""
        rows.append({
            "Structure": pdb_id,
            "Polymorph": polymorph,
            "Associated disease": disease,
            "Confidence": r["score"],
            "Bounds (cached)": bounds,
            "Evaluable": f"{r['matched_count']}/{r['evaluable_count']}{flag}",
        })
    candidates_df = pd.DataFrame(rows)
    default_pdb = candidates_df.iloc[0]["Structure"]
else:
    candidates_df = pd.DataFrame(
        columns=["Structure", "Polymorph", "Associated disease", "Confidence", "Bounds (cached)", "Evaluable"]
    )
    default_pdb = all_ids[0]

selected_pdb = st.session_state.get("selected_pdb") or default_pdb
if selected_pdb not in all_ids:
    selected_pdb = all_ids[0]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
curated_row = curated_df[curated_df["pdb_id"] == selected_pdb]
known_row = known_df[known_df["pdb_id"] == selected_pdb]
polymorph_name = known_row["polymorph_name"].iloc[0] if not known_row.empty else "Uncategorized"

score_for_selected = None
for r in results:
    if r["pdb_id"] == selected_pdb:
        score_for_selected = r["score"]
        break

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(f'<p class="header-title">{selected_pdb}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="header-subtitle">{polymorph_name}</p>', unsafe_allow_html=True)
with col_h2:
    if score_for_selected is not None:
        st.markdown(
            f'<div class="confidence-plain"><span class="pct">{score_for_selected*100:.0f}%</span> '
            f'Match Score</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="confidence-plain" style="color:#999;">Not yet matched</div>', unsafe_allow_html=True)

# switcher, kept low-key: lets you browse any of the 201 cached structures
# directly, independent of the matching results above
picked = st.selectbox(
    "View a different cached structure",
    options=all_ids,
    index=all_ids.index(selected_pdb),
    label_visibility="collapsed",
)
if picked != selected_pdb:
    st.session_state["selected_pdb"] = picked
    st.rerun()

left_col, right_col = st.columns([1.7, 1], gap="large")

# ---------------------------------------------------------------------------
# Left column: real 3D viewer + ranked candidates table
# ---------------------------------------------------------------------------
with left_col:
    st.markdown('<div class="viewer-box">', unsafe_allow_html=True)
    if VIEWER_AVAILABLE:
        try:
            render_pdb_3d(selected_pdb)
        except Exception as e:
            st.markdown(
                f'<div class="viewer-fallback">Could not load live structure for '
                f'{selected_pdb} from RCSB ({e}).<br>Check network access from '
                f'this deployment.</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="viewer-fallback">3D viewer unavailable -- stmol / py3Dmol '
            'not installed. Check requirements.txt.</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    st.subheader("All candidates, ranked by confidence")
    if not candidates_df.empty:
        st.dataframe(
            candidates_df,
            column_config={
                "Confidence": st.column_config.ProgressColumn(
                    "Confidence",
                    help=("Fraction of evaluable observed masses matched"
                          if st.session_state.get("last_mode") == "mass"
                          else "FDR-adjusted statistical confidence (1 - adjusted p-value)"),
                    format="%.2f", min_value=0, max_value=1,
                ),
                "Structure": st.column_config.TextColumn("Structure", width="small"),
                "Bounds (cached)": st.column_config.TextColumn("Bounds (cached)", width="small"),
            },
            hide_index=True,
            width="stretch",
        )
        caption_text = (
            "Ranked on evaluable coverage first, match quality second -- a structure "
            "tested against more of your real data outranks one that trivially "
            '"wins" by having too little resolved sequence to be meaningfully tested.'
        )
        if any(r.get("low_power_warning") for r in results):
            caption_text += "  ⚠ = few trials for this structure; confidence is unreliable at this coverage."
        st.caption(caption_text)
    else:
        st.info("Enter your observed data above and run the test to populate this table.")

# ---------------------------------------------------------------------------
# Right column: real cached metadata, honest about what isn't cached
# ---------------------------------------------------------------------------
with right_col:
    with st.expander("About this Structure", expanded=True):
        if not curated_row.empty:
            row = curated_row.iloc[0]
            st.write(f"**{selected_pdb}** -- {row['title']}")
            if isinstance(row.get("citation_title"), str) and row["citation_title"]:
                st.caption(f"{row['citation_title']} ({row.get('journal', '')}, {row.get('year', '')})")
        else:
            st.write(f"**{selected_pdb}** has no curated summary in known_structures.csv yet.")
        rcsb_url = f"https://www.rcsb.org/structure/{selected_pdb}"
        st.markdown(f"[View full entry on RCSB]({rcsb_url})")

    profile = get_structure_profile(selected_pdb)
    with st.container(border=True):
        st.markdown('<div class="card-title">Macromolecule Content (from cache)</div>', unsafe_allow_html=True)
        if profile:
            st.markdown(
                f"""
                <div class="detail-item"><div class="detail-label">Core-shielded chains</div>
                    <div class="detail-value">{profile['core_chain_count']}</div></div>
                <div class="detail-item"><div class="detail-label">Modeled residues (cached profile)</div>
                    <div class="detail-value">{profile['modeled_residue_count']}</div></div>
                <div class="detail-item"><div class="detail-label">Profile residue range</div>
                    <div class="detail-value">{profile['residue_range'][0]}-{profile['residue_range'][1]}</div></div>
                <div class="detail-item"><div class="detail-label">Est. mass of cached region</div>
                    <div class="detail-value">{profile['est_mass_kda']} kDa</div></div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(
                "These reflect the core-shielded region computed by the contact-graph "
                "analysis, not necessarily the full deposited construct."
            )
        else:
            st.markdown('<div class="detail-value na">Not cached for this structure</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="card-title">Experimental Data</div>', unsafe_allow_html=True)
        resolution = curated_row["resolution"].iloc[0] if not curated_row.empty else None
        st.markdown(
            f"""
            <div class="detail-item"><div class="detail-label">Method</div>
                <div class="detail-value">Cryo-Electron Microscopy</div></div>
            <div class="detail-item"><div class="detail-label">Resolution</div>
                <div class="detail-value">{f'{resolution:.2f} Å' if resolution else 'N/A'}</div></div>
            <div class="detail-item"><div class="detail-label">EM software, atom count</div>
                <div class="detail-value na">Not cached</div></div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="not-cached-note">Software versions and full validation metrics '
            f'live in the wwPDB validation report, not in this cache. '
            f'<a href="{rcsb_url}" target="_blank">View on RCSB</a></div>',
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.markdown('<div class="card-title">Structure Validation</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="not-cached-note">Clashscore, Ramachandran outliers, and Q-score '
            'are computed by wwPDB validation pipelines and are not stored locally -- '
            f'showing a made-up number here would be worse than not showing one. '
            f'<a href="{rcsb_url}" target="_blank">Full Validation Report on RCSB</a></div>',
            unsafe_allow_html=True,
        )

st.markdown(
    '<div class="footer-disclaimer">SG-ATLAS is a hypothesis-generation aid for choosing '
    'which structural strain to investigate further -- not a diagnostic tool.</div>',
    unsafe_allow_html=True,
)
