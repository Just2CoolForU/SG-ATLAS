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
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

from sg_atlas_fragments import (
    match_observed_fragments, score_all_candidates, RESIDUE_MASS, WATER_MASS,
    compute_rsa, predict_cleavage_sites, predicted_ladder_for_structure,
)

try:
    from pymol_viewer import render_pdb_3d
    VIEWER_AVAILABLE = True
    VIEWER_IMPORT_ERROR = None
except Exception as e:
    VIEWER_AVAILABLE = False
    VIEWER_IMPORT_ERROR = f"{type(e).__name__}: {e}"

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
        "SELECT chain_id, residue, amino_acid, sasa FROM residues WHERE pdb_id=? AND mode=?",
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
    for cid, resseq, aa, sasa in rows:
        by_chain.setdefault(cid, {})[resseq] = {"aa": aa, "sasa": sasa}

    best_chain = max(by_chain, key=lambda c: len(by_chain[c]))
    profile = by_chain[best_chain]
    residues_sorted = sorted(profile.keys())
    est_mass = sum(RESIDUE_MASS.get(d["aa"], 110.0) for d in profile.values()) + WATER_MASS

    import json
    core_chain_ids = json.loads(chain_row[0]) if chain_row else list(by_chain.keys())

    return {
        "best_chain": best_chain,
        "modeled_residue_count": len(profile),
        "residue_range": (residues_sorted[0], residues_sorted[-1]),
        "core_chain_count": len(core_chain_ids),
        "core_chain_ids": core_chain_ids,
        "est_mass_kda": round(est_mass / 1000, 2),
        "raw_profile": profile,  # {resseq: {"aa": ..., "sasa": ...}} for the best/core chain
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


@st.cache_data
def get_predicted_ladder(pdb_id):
    """The actual predicted PK fragment ladder for this structure, straight
    from sg_atlas_fragments.py -- same function the ranked-candidates table
    is scored against, not a separate approximation."""
    return predicted_ladder_for_structure(pdb_id, mode=MODE, db_path=DB_PATH)


LADDER_MARKERS_DA = [2000, 3000, 5000, 7000, 10000, 15000, 20000, 25000]


def compute_band_matches(predicted_masses, observed_masses, tolerance_pct):
    """For each observed mass, is there a predicted band within tolerance?
    Same pass/fail rule match_observed_fragments() uses per-structure,
    applied here just for the currently-viewed structure so the gel and the
    ranked table are always telling the same story."""
    out = []
    for obs in observed_masses:
        if not predicted_masses or obs <= 0:
            out.append((obs, False, None))
            continue
        closest = min(predicted_masses, key=lambda p: abs(p - obs))
        pct_diff = abs(closest - obs) / obs * 100
        out.append((obs, pct_diff <= tolerance_pct, closest))
    return out


def draw_fragment_gel(pdb_id, predicted_fragments, observed_masses=None, tolerance_pct=5.0):
    """Simulated SDS-PAGE-style gel: a reference ladder lane, a lane of this
    structure's predicted PK digestion bands, and (in mass-matching mode) a
    lane of your observed bands colored green/red by whether they land near
    a predicted band. Larger fragments sit near the top, matching how they'd
    actually run on a real gel -- less migration for bigger fragments."""
    predicted_masses = [f["mass_da"] for f in predicted_fragments] if predicted_fragments else []

    lanes = ["Ladder", f"Predicted\n{pdb_id}"]
    if observed_masses:
        lanes.append("Observed")

    fig, ax = plt.subplots(figsize=(1.7 * len(lanes) + 1.4, 5.2))
    fig.patch.set_facecolor("#161616")
    ax.set_facecolor("#161616")
    lane_w = 0.55

    for m in LADDER_MARKERS_DA:
        y = np.log10(m)
        ax.hlines(y, -lane_w / 2, lane_w / 2, color="#f4d35e", linewidth=2.2)
        ax.text(-lane_w / 2 - 0.12, y, f"{m/1000:g}k", color="#f4d35e",
                 fontsize=8, va="center", ha="right")

    if predicted_masses:
        for m in predicted_masses:
            y = np.log10(m)
            ax.hlines(y, 1 - lane_w / 2, 1 + lane_w / 2, color="#eaeaea", linewidth=4.5)
    else:
        ax.text(1, 0.5, "not cached", color="#777777", fontsize=8, ha="center",
                 transform=ax.get_xaxis_transform())

    if observed_masses:
        matches = compute_band_matches(predicted_masses, observed_masses, tolerance_pct)
        for obs, matched, _ in matches:
            y = np.log10(obs)
            color = "#5ec962" if matched else "#e34a4a"
            ax.hlines(y, 2 - lane_w / 2, 2 + lane_w / 2, color=color, linewidth=4.5)
            ax.text(2 + lane_w / 2 + 0.12, y, f"{obs:.0f}", color=color, fontsize=8, va="center")

    ax.set_xlim(-1.15, len(lanes) - 0.25)
    ax.set_xticks(range(len(lanes)))
    ax.set_xticklabels(lanes, color="white", fontsize=9)
    ax.set_yticks([])
    ax.tick_params(colors="white", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    return fig


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
mode = st.selectbox(
    "Input type",
    ["Mass weights (MS/gel)", "Residue positions (boundaries)"],
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
    run_clicked = st.button("Match Profile", type="primary")

    # Tracked live (not gated on the button) so the fragment-bands gel below
    # reflects whatever's currently typed, not just the last matched run.
    gel_observed_masses = parse_masses(masses_input)
    gel_tolerance_pct = tolerance
    st.session_state["gel_observed_masses"] = gel_observed_masses
    st.session_state["gel_tolerance_pct"] = gel_tolerance_pct

    if "match_results" not in st.session_state or run_clicked or st.session_state.get("last_mode") != "mass":
        masses = gel_observed_masses
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
    run_clicked = st.button("Match Profile", type="primary")

    # No observed masses in this mode -- the gel will show predicted bands
    # only, with no observed lane, rather than showing stale mass data from
    # a previous mode.
    st.session_state["gel_observed_masses"] = None
    st.session_state["gel_tolerance_pct"] = None

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

# Clear, hard-to-miss confirmation of what's currently being shown -- shown
# every time results exist (not just right after clicking), so it stays
# accurate even if you've browsed away from the #1 match via the switcher
# below. Plus a one-off toast on the actual click announcing the top match,
# so a fresh result is unmistakable before you even scroll down.
if not candidates_df.empty:
    if score_for_selected is not None:
        st.success(
            f"**Currently viewing: {selected_pdb}** \u2014 {polymorph_name} "
            f"\u2014 {score_for_selected*100:.0f}% confidence"
        )
    else:
        st.info(f"**Currently viewing: {selected_pdb}** \u2014 {polymorph_name} (not in current match results)")
    if run_clicked:
        top_row = candidates_df.iloc[0]
        st.toast(
            f"Top match: {top_row['Structure']} ({top_row['Confidence']*100:.0f}% confidence)",
            icon="\U0001F9EC",
        )

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

# Computed once here (cached) and reused everywhere below, so the viewer,
# the metadata card, and the RSA/cleavage overlays never disagree.
profile = get_structure_profile(selected_pdb)
core_chains = profile["core_chain_ids"] if profile else None
best_chain = profile["best_chain"] if profile else None
raw_profile = profile["raw_profile"] if profile else None

rcsb_url = f"https://www.rcsb.org/structure/{selected_pdb}"

# ---------------------------------------------------------------------------
# Fragment bands -- simulated PK digestion gel. This is the part that
# actually corresponds to what a researcher gets out of a real bench
# experiment, so it sits right up front, not buried below the viewer.
# ---------------------------------------------------------------------------
st.subheader("Predicted Fragment Bands")
ladder_info = get_predicted_ladder(selected_pdb)
predicted_fragments = ladder_info["fragments"] if ladder_info else []
gel_observed = st.session_state.get("gel_observed_masses")
gel_tolerance = st.session_state.get("gel_tolerance_pct") or 5.0

if predicted_fragments or gel_observed:
    gel_fig = draw_fragment_gel(
        selected_pdb, predicted_fragments,
        observed_masses=gel_observed, tolerance_pct=gel_tolerance,
    )
    st.pyplot(gel_fig, width="content")
    plt.close(gel_fig)

    gel_caption = (
        "Simulated Proteinase K digestion, predicted from cached SASA-derived "
        "cleavage sites -- not an actual gel image. Ladder lane is a generic "
        "small-fragment size reference, not run alongside this sample."
    )
    if gel_observed:
        gel_caption += (
            " Green observed bands land within tolerance of a predicted band; "
            "red ones don't."
        )
    st.caption(gel_caption)
else:
    st.info(f"No cached SASA profile for {selected_pdb} -- can't predict a digestion ladder.")

st.write("")

# ---------------------------------------------------------------------------
# Viewer controls -- compact row above the single full-width viewer box
# ---------------------------------------------------------------------------
vc1, vc2, vc3 = st.columns([1.3, 1.3, 1])
with vc1:
    color_mode_label = st.selectbox(
        "Color by",
        ["Core chains", "Solvent accessibility (RSA)"],
        disabled=(profile is None),
    )
    color_mode = "rsa" if color_mode_label.startswith("Solvent") else "chain"
with vc2:
    show_cleavage = st.checkbox(
        "Mark predicted PK cleavage sites", value=False, disabled=(profile is None)
    )
with vc3:
    spin = st.checkbox("Auto-rotate", value=False)

cleavage_sites = None
if show_cleavage and raw_profile:
    cleavage_sites = predict_cleavage_sites(raw_profile)

# ---------------------------------------------------------------------------
# Full-width 3D viewer -- a single box (st.iframe supplies its own frame,
# no extra wrapper div on top of it)
# ---------------------------------------------------------------------------
if VIEWER_AVAILABLE:
    try:
        render_pdb_3d(
            selected_pdb,
            core_chains=core_chains,
            color_mode=color_mode,
            profile_chain=best_chain,
            residue_profile=raw_profile,
            cleavage_sites=cleavage_sites,
            spin=spin,
        )
    except Exception as e:
        st.markdown(
            f'<div class="viewer-fallback">Could not load live structure for '
            f'{selected_pdb} from RCSB ({e}).<br>Check network access from '
            f'this deployment.</div>',
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        f'<div class="viewer-fallback">3D viewer import failed.<br>'
        f'<code>{VIEWER_IMPORT_ERROR}</code><br><br>'
        f'Check "Manage app" &rarr; logs on Streamlit Cloud for the full '
        f'traceback if this doesn\'t explain it.</div>',
        unsafe_allow_html=True,
    )

if profile:
    if color_mode == "rsa":
        st.caption(
            f"Chain {best_chain} colored by Relative Solvent Accessibility: "
            f"blue = buried, red = exposed. Other core chains "
            f"({', '.join(c for c in profile['core_chain_ids'] if c != best_chain)}) "
            f"shown in grey -- SASA is only cached for one representative chain per "
            f"structure, not verified per-chain."
            + (" Black spheres mark predicted PK cleavage sites." if cleavage_sites else "")
        )
    else:
        st.caption(
            f"Colored chains ({', '.join(profile['core_chain_ids'])}) are the "
            f"core-shielded region SG-ATLAS actually computed a SASA profile for. "
            f"Grey chains are part of the deposited assembly but weren't included "
            f"in this analysis."
            + (" Black spheres mark predicted PK cleavage sites." if cleavage_sites else "")
        )
else:
    st.caption(f"No cached SASA profile for {selected_pdb} -- showing the raw deposited structure.")

st.write("")

# ---------------------------------------------------------------------------
# Info cards, underneath the viewer, two per row
# ---------------------------------------------------------------------------
info_col1, info_col2 = st.columns(2, gap="large")

with info_col1:
    with st.expander("About this Structure", expanded=True):
        if not curated_row.empty:
            row = curated_row.iloc[0]
            st.write(f"**{selected_pdb}** -- {row['title']}")
            if isinstance(row.get("citation_title"), str) and row["citation_title"]:
                st.caption(f"{row['citation_title']} ({row.get('journal', '')}, {row.get('year', '')})")
        else:
            st.write(f"**{selected_pdb}** has no curated summary in known_structures.csv yet.")
        st.markdown(f"[View full entry on RCSB]({rcsb_url})")

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

with info_col2:
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

st.write("")

# ---------------------------------------------------------------------------
# Candidates table, full width, underneath everything
# ---------------------------------------------------------------------------
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
    st.info("Enter your observed data above and click Match Profile to populate this table.")

st.markdown(
    '<div class="footer-disclaimer">SG-ATLAS is a hypothesis-generation aid for choosing '
    'which structural strain to investigate further -- not a diagnostic tool.</div>',
    unsafe_allow_html=True,
)
