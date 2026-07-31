"""
sg_atlas_app.py — self-contained SG-ATLAS frontend, no separate server.

This calls sg_atlas_fragments.py's functions directly, in-process. No
FastAPI, no uvicorn, no second terminal, no localhost networking between
two services. One file, one command to run it locally, and -- unlike the
previous two-service version -- this is actually deployable to a real,
free, public URL (see bottom of this docstring).

Run locally:
    pip install -r requirements.txt
    streamlit run sg_atlas_app.py

Deploy to a real public URL (free):
    1. Create a GitHub repo, push these files to it:
       sg_atlas_app.py, sg_atlas_fragments.py, known_structures.csv,
       sg_atlas_cache.db, requirements.txt
    2. Go to https://share.streamlit.io, sign in with GitHub
    3. Click "New app", pick your repo, set main file to sg_atlas_app.py
    4. Deploy -- you get a real URL like https://your-app.streamlit.app
       that anyone can open, no local setup required on their end.

Important: sg_atlas_cache.db must be committed to the repo for the
deployed version to have any data -- Streamlit Cloud runs a fresh copy
of your repo, it doesn't have access to your local machine's files.
"""
import pandas as pd
import streamlit as st

from sg_atlas_fragments import score_all_candidates
CACHE_DB = "sg_atlas_cache.db"
KNOWN_STRUCTURES_CSV = "known_structures.csv"


@st.cache_data
def load_known_metadata():
    """Merge two metadata sources: known_structures.csv (richer,
    disease/polymorph-specific classification, ~90 structures) and the
    curated_atlas table inside the cache database itself (real deposited
    title/journal/citation for all 201 structures, no disease
    classification). known_structures.csv wins when both exist; every
    structure without a CSV entry still gets a REAL citation from
    curated_atlas instead of showing as fully uncategorized."""
    import csv
    import os
    import sqlite3

    meta = {}
    # base layer: real bibliographic data for every cached structure
    try:
        conn = sqlite3.connect(CACHE_DB)
        cur = conn.execute("SELECT pdb_id, title, journal, year, resolution FROM curated_atlas")
        for pdb_id, title, journal, year, resolution in cur.fetchall():
            citation = f"{journal or 'Journal not recorded'}" + (f", {year}" if year else "") + f" (PDB {pdb_id})"
            meta[pdb_id.upper()] = {
                "polymorph_name": "", "disease_association": "",
                "citation": citation, "protofilament_count": "",
                "notes": f"Resolution {resolution} A." if resolution else "",
                "_source": "curated_atlas", "_title": title or "",
            }
    except Exception:
        pass  # curated_atlas may not exist in older cache files -- degrade gracefully

    # override layer: richer disease/polymorph classification where available
    if os.path.exists(KNOWN_STRUCTURES_CSV):
        with open(KNOWN_STRUCTURES_CSV, newline="") as f:
            for row in csv.DictReader(f):
                pid = row["pdb_id"].upper()
                existing = meta.get(pid, {})
                existing.update({k: v for k, v in row.items() if v})
                existing["_source"] = "known_structures.csv"
                meta[pid] = existing
    return meta


def format_mass_results_table(results):
    rows = []
    for r in results:
        exceeded = [d["observed"] for d in r["details"] if d.get("exceeds_max")]
        rows.append({
            "Structure": r["pdb_id"],
            "Match score": f"{r['matched_count']}/{r['evaluable_count']} matched",
            "Coverage": f"{r['evaluable_count']}/{r['total_observed']} testable",
            "Too large for this structure": ", ".join(f"{m:.0f} Da" for m in exceeded) if exceeded else "—",
            "_sort_score": r["score"],
        })
    return pd.DataFrame(rows)


def format_precision_results_table(results, known_labels):
    rows = []
    for r in results:
        meta = known_labels.get(r["pdb_id"], {})
        polymorph = meta.get("polymorph_name") or meta.get("_title") or "Unclassified"
        if len(polymorph) > 55:
            polymorph = polymorph[:52] + "..."
        disease = meta.get("disease_association") or "Not disease-categorized (see title)"
        rows.append({
            "Structure": r["pdb_id"],
            "Polymorph": polymorph,
            "Associated disease": disease,
            "Confidence": f"{r['confidence'] * 100:.1f}%",
            "Boundary matches": f"{r['matches']}/{r['trials']}",
            "_sort_confidence": r["confidence"],
        })
    return pd.DataFrame(rows)


st.set_page_config(page_title="SG-ATLAS", page_icon="\U0001F9EC", layout="wide")
st.title("SG-ATLAS: Fragment Pattern Strain Matcher")

st.warning(
    "**Research tool, not a diagnostic.** This compares a fragment pattern against "
    "computational predictions from published cryo-EM structures. It has not been "
    "clinically validated. Treat results as a structural hypothesis to weigh alongside "
    "other evidence, not a standalone answer.",
    icon="\u26A0\uFE0F",
)

try:
    known_labels = load_known_metadata()
except Exception:
    known_labels = {}

mode = st.radio(
    "Input type",
    ["Precision (sequence-identified fragments — recommended)", "Mass-only (gel or simple MS)"],
    help="Precision mode uses real cut positions from MS/MS sequencing, which is a direct, "
         "unambiguous structural check. Mass-only mode compares intact fragment weights, which "
         "different structures can coincidentally produce even when the real cut pattern differs — "
         "use precision mode whenever sequence data is available.",
)

results_col, detail_col = st.columns([3, 2])

if mode.startswith("Precision"):
    st.subheader("Enter sequence-identified fragments")
    st.caption("Add a row per fragment identified from your MS/MS run — residue start/end positions, "
               "not intact mass.")
    default_df = pd.DataFrame({"start": [38], "end": [60]})
    edited_df = st.data_editor(default_df, num_rows="dynamic", width="stretch")
    tolerance_window = st.slider("Boundary tolerance (residues)", min_value=0, max_value=5, value=2)
    run = st.button("Run precision match", type="primary")

    if run:
        fragments = [(int(r["start"]), int(r["end"])) for _, r in edited_df.dropna().iterrows()]
        if not fragments:
            st.error("Add at least one fragment first.")
        else:
            with st.spinner("Matching against cached structures..."):
                try:
                    results = score_all_candidates_by_position(
                        fragments, tolerance_window=tolerance_window, db_path=CACHE_DB,
                    )
                except Exception as e:
                    st.error(f"Couldn't run the match — is {CACHE_DB} present? ({e})")
                    results = []

            if results:
                df = format_precision_results_table(results, known_labels)
                top = results[0]
                top_meta = known_labels.get(top["pdb_id"], {})

                with results_col:
                    top_label = top_meta.get('polymorph_name') or top_meta.get('_title') or 'Unclassified'
                    st.metric(
                        label=f"Top match: {top['pdb_id']} ({top_label})",
                        value=f"{top['confidence'] * 100:.1f}% confidence",
                        help="Statistical confidence this match pattern is real structural signal, not "
                             "coincidence — a binomial enrichment test, not a raw match fraction.",
                    )
                    st.caption(
                        f"This means: if cleavage sites were randomly distributed, there'd be roughly a "
                        f"{(1 - top['confidence']) * 100:.1f}% chance of seeing this good a match by pure luck."
                    )
                    st.subheader("All candidates, ranked by confidence")
                    st.dataframe(df.drop(columns=["_sort_confidence"]), hide_index=True, width="stretch")
                    st.bar_chart(df.set_index("Structure")["_sort_confidence"].head(10), y_label="Confidence")

                with detail_col:
                    st.subheader(f"About {top['pdb_id']}")
                    if top_meta:
                        source = top_meta.get("_source", "unknown")
                        if source == "known_structures.csv":
                            st.success("Disease/polymorph-classified entry")
                        else:
                            st.info("Real cited structure — not yet manually classified by disease/polymorph")
                        st.markdown(f"**Title:** {top_meta.get('_title') or '—'}")
                        if top_meta.get("polymorph_name"):
                            st.markdown(f"**Polymorph:** {top_meta['polymorph_name']}")
                        if top_meta.get("disease_association"):
                            st.markdown(f"**Disease association:** {top_meta['disease_association']}")
                        st.markdown(f"**Source:** {top_meta.get('citation', '—')}")
                        if top_meta.get("protofilament_count"):
                            st.markdown(f"**Protofilament count:** {top_meta['protofilament_count']}")
                        if top_meta.get("notes"):
                            st.info(top_meta["notes"])
                    else:
                        st.warning("No metadata found for this structure at all — not even a citation. "
                                   "This shouldn't happen if curated_atlas is populated; worth checking.")
            else:
                st.warning("No structures in the cache could be evaluated against these fragments.")

else:
    st.subheader("Enter observed fragment masses")
    masses_input = st.text_input("Comma-separated masses in Da", placeholder="e.g. 6200.5, 4100.2, 2300.8")
    tolerance_pct = st.slider("Match tolerance (%)", min_value=1.0, max_value=15.0, value=5.0, step=0.5)
    run = st.button("Run mass match", type="primary")

    if run:
        try:
            observed = [float(x.strip()) for x in masses_input.split(",") if x.strip()]
        except ValueError:
            st.error("Use plain numbers separated by commas.")
            observed = []
        if observed:
            with st.spinner("Matching..."):
                try:
                    results = match_observed_fragments(observed, tolerance_pct=tolerance_pct, db_path=CACHE_DB)
                except Exception as e:
                    st.error(f"Couldn't run the match — is {CACHE_DB} present? ({e})")
                    results = []

            if results:
                st.caption("Mass-only matching is weaker evidence than precision mode — different cut "
                           "patterns can coincidentally produce similar fragment weights.")
                df = format_mass_results_table(results)
                st.dataframe(df.drop(columns=["_sort_score"]), hide_index=True, width="stretch")
            else:
                st.warning("No structures in the cache could be evaluated against these masses.")
                st.markdown("""
<style>
    /* Metric Cards */
    .metric-card {
        background-color: #1E222A;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #4CAF50;
        margin-bottom: 12px;
    }
    .warning-card {
        background-color: #2A2118;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #FF9800;
        margin-bottom: 12px;
    }
    /* Confidence Badges */
    .badge-high { background-color: #1b4332; color: #74c69d; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-medium { background-color: #4a3b00; color: #ffd166; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-low { background-color: #3d0000; color: #ff758f; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)
                
