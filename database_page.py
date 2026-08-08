# -*- coding: utf-8 -*-
"""
database_page.py -- "Discover Database" page.

A browsable, searchable view of every structure in known_structures.csv
(the curated reference table described in SG_ATLAS_Overview.md) -- the
201-structure landscape SG-ATLAS's batch pipeline discovered and profiled,
not just the handful with hand-written polymorph/disease notes.

Same honesty rule as the rest of the project: a structure with no curated
disease/polymorph note is labeled "Uncategorized", never guessed at. If the
populated SASA cache (sg_atlas_cache.db) isn't present in this deployment,
the "cached profile" column degrades to an explicit note rather than
silently disappearing or showing a wrong count.
"""

import os
import sqlite3

import pandas as pd
import streamlit as st

from nav_config import TOP_NAV_PAGES
from shared_ui import render_top_nav

CSV_PATH = "known_structures.csv"
DB_PATH = "sg_atlas_cache.db"
MODE = "full-core"

st.markdown(
    """
    <style>
    .sg-db-count {
        font-family: var(--font-mono);
        letter-spacing: 0.12em;
        color: var(--sg-charcoal);
        opacity: 0.7;
        font-size: 0.85rem;
        margin: 0.2rem 0 1rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

render_top_nav(TOP_NAV_PAGES, active="Discover Database")

st.markdown('<p class="sg-page-title">Discover the Database</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sg-page-subtitle">Every deposited \u03b1-synuclein cryo-EM structure '
    "SG-ATLAS has profiled \u2014 search, filter, and jump straight to RCSB.</p>",
    unsafe_allow_html=True,
)


@st.cache_data
def load_known_structures():
    df = pd.read_csv(CSV_PATH)
    df["pdb_id"] = df["pdb_id"].str.upper()
    df["disease_association"] = df["disease_association"].apply(
        lambda v: v if isinstance(v, str) and v.strip() else "Uncategorized"
    )
    df["polymorph_name"] = df["polymorph_name"].apply(
        lambda v: v if isinstance(v, str) and v.strip() else "Uncategorized"
    )
    return df


@st.cache_data
def load_cached_pdb_ids():
    """Which structures have an actual computed SASA profile in the local
    cache, if that database has been deployed alongside this page. Returns
    None (not an empty set) when the cache simply isn't there, so the UI
    can tell 'nothing cached' apart from 'cache not deployed here'."""
    if not os.path.exists(DB_PATH):
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT DISTINCT pdb_id FROM structures WHERE mode=?", conn, params=(MODE,)
        )
        conn.close()
        return set(df["pdb_id"].str.upper())
    except Exception:
        return None


known_df = load_known_structures()
cached_ids = load_cached_pdb_ids()

if cached_ids is not None:
    known_df = known_df.copy()
    known_df["Cached profile"] = known_df["pdb_id"].isin(cached_ids).map({True: "Yes", False: "No"})

# ---------------------------------------------------------------------------
# Search + filters
# ---------------------------------------------------------------------------
search_col, disease_col, source_col = st.columns([2, 1.3, 1.3])

with search_col:
    query = st.text_input(
        "Search",
        placeholder="Search by PDB ID, polymorph, disease, citation, or note\u2026",
        label_visibility="collapsed",
    )

with disease_col:
    disease_options = sorted(known_df["disease_association"].unique())
    picked_diseases = st.multiselect("Disease association", disease_options, label_visibility="collapsed",
                                      placeholder="Filter by disease")

with source_col:
    source_options = sorted(known_df["source_type"].unique())
    picked_sources = st.multiselect("Source type", source_options, label_visibility="collapsed",
                                     placeholder="Filter by source type")

filtered = known_df

if query.strip():
    q = query.strip().lower()
    searchable_cols = ["pdb_id", "polymorph_name", "disease_association", "source_type", "citation", "notes"]
    mask = filtered[searchable_cols].apply(
        lambda col: col.astype(str).str.lower().str.contains(q, regex=False)
    ).any(axis=1)
    filtered = filtered[mask]

if picked_diseases:
    filtered = filtered[filtered["disease_association"].isin(picked_diseases)]

if picked_sources:
    filtered = filtered[filtered["source_type"].isin(picked_sources)]

st.markdown(
    f'<p class="sg-db-count">{len(filtered)} of {len(known_df)} structures</p>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------
display_df = filtered.copy()
display_df["RCSB"] = "https://www.rcsb.org/structure/" + display_df["pdb_id"]

display_cols = ["pdb_id", "polymorph_name", "disease_association", "source_type", "citation", "notes", "RCSB"]
column_labels = {
    "pdb_id": "PDB ID",
    "polymorph_name": "Polymorph",
    "disease_association": "Disease association",
    "source_type": "Source type",
    "citation": "Citation",
    "notes": "Notes",
}
if "Cached profile" in display_df.columns:
    display_cols.insert(-1, "Cached profile")
    column_labels["Cached profile"] = "Cached profile"

column_config = {
    "RCSB": st.column_config.LinkColumn("RCSB", display_text="View \u2192"),
}
for col, label in column_labels.items():
    column_config[col] = st.column_config.TextColumn(label)

st.dataframe(
    display_df[display_cols],
    column_config=column_config,
    hide_index=True,
    width="stretch",
    height=560,
)

if cached_ids is None:
    st.caption(
        "\u26a0 The populated structural cache (sg_atlas_cache.db) isn't present in this "
        "deployment, so a 'Cached profile' column can't be shown honestly right now -- "
        "every row above is still the real curated reference data from known_structures.csv. "
        "Once the populated cache database is committed alongside this app (as described in "
        "the project overview), this page will also show which structures have a computed "
        "SASA/cleavage profile ready to match against on the SG Atlas tool page."
    )
else:
    st.caption(
        "'Cached profile' reflects whether SG-ATLAS has actually computed a SASA/cleavage "
        "profile for that structure -- only cached structures can be matched against on the "
        "SG Atlas tool page. Disease association and polymorph are shown as 'Uncategorized' "
        "rather than guessed when known_structures.csv has no curated entry."
    )
