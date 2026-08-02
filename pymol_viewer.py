"""
pymol_viewer.py -- interactive 3D structure viewer for the SG-ATLAS
Streamlit app, built directly on py3Dmol + Streamlit's own st.iframe.

NOTE: this used to go through the `stmol` package as a wrapper around
py3Dmol. stmol's last PyPI release was August 2022 (confirmed on PyPI) --
it's unmaintained, and importing it against a current Streamlit version can
fail outright. stmol itself is just a thin wrapper around py3Dmol's
generated HTML embedded in an iframe, so this calls Streamlit's own
st.iframe() directly and drops the unmaintained dependency.

Two color modes, both tied to real cached data (never decorative):
  - "chain": highlights the core-shielded chains SG-ATLAS's contact-graph
    filtering actually kept (structures.chain_ids), dims everything else.
  - "rsa": colors the profiled chain by actual cached Relative Solvent
    Accessibility (blue = buried, red = exposed), the same RSA values that
    drive the PK cleavage-site predictions elsewhere in the app.

Optional overlays:
  - cleavage_sites: marks specific residues (e.g. predicted PK cleavage
    sites) with small black spheres directly on the 3D structure.
  - spin: slow auto-rotation.
"""

import re

import py3Dmol
import streamlit as st

CHAIN_PALETTE = ["0xE63946", "0x1D3557", "0x2A9D8F", "0xF4A261", "0x6A4C93", "0xE9C46A"]

# RSA bucket -> color, buried (blue) to exposed (red). The 0.45 boundary
# lines up with sg_atlas_fragments.py's default PK cleavage-site threshold.
RSA_BUCKETS = [
    (0.10, "0x08306B"),
    (0.25, "0x4292C6"),
    (0.45, "0xC6DBEF"),
    (0.65, "0xFDBB84"),
    (999.0, "0xE31A1C"),
]


def _rsa_color(rsa):
    for cutoff, color in RSA_BUCKETS:
        if rsa < cutoff:
            return color
    return RSA_BUCKETS[-1][1]


def render_pdb_3d(
    pdb_id,
    core_chains=None,
    color_mode="chain",
    profile_chain=None,
    residue_profile=None,
    cleavage_sites=None,
    spin=False,
    height=560,
    width=1080,
):
    """
    Render `pdb_id`. Behavior depends on what's supplied:

    core_chains: chain letters SG-ATLAS classified as core for this
        structure. None/[] falls back to a plain full-structure cartoon.
    color_mode: "chain" (default) or "rsa". "rsa" requires profile_chain +
        residue_profile; silently falls back to "chain" if they're missing.
    profile_chain: the single chain residue_profile/cleavage_sites apply to
        (the "best_chain" from get_structure_profile) -- SASA is only cached
        for one representative chain per structure, not all core chains.
    residue_profile: {resseq: {"aa": ..., "sasa": ...}} for profile_chain.
    cleavage_sites: list of residue numbers to mark with black spheres
        (e.g. predicted PK cleavage sites), applied on profile_chain.
    spin: slow auto-rotation.
    """
    view = py3Dmol.view(query=f"pdb:{pdb_id.lower()}", width=width, height=height)

    use_rsa = color_mode == "rsa" and profile_chain and residue_profile

    if core_chains:
        view.setStyle({}, {"cartoon": {"color": "0xD9D9D9", "opacity": 0.35}})

        if use_rsa:
            # Non-profiled core chains: a single neutral "known core, but no
            # per-residue data for this exact chain" color -- distinct from
            # both the dimmed-out non-core chains and the RSA gradient.
            for chain in core_chains:
                if chain != profile_chain:
                    view.setStyle({"chain": chain}, {"cartoon": {"color": "0x999999"}})

            # The profiled chain: real RSA heatmap, bucketed for speed.
            from sg_atlas_fragments import compute_rsa
            buckets = {}
            for resseq, d in residue_profile.items():
                rsa = compute_rsa(d["sasa"], d["aa"])
                if rsa is None:
                    continue
                buckets.setdefault(_rsa_color(rsa), []).append(resseq)
            for color, resi_list in buckets.items():
                view.setStyle(
                    {"chain": profile_chain, "resi": resi_list},
                    {"cartoon": {"color": color}},
                )
        else:
            for i, chain in enumerate(core_chains):
                view.setStyle(
                    {"chain": chain},
                    {"cartoon": {"color": CHAIN_PALETTE[i % len(CHAIN_PALETTE)]}},
                )

        if cleavage_sites and profile_chain:
            view.addStyle(
                {"chain": profile_chain, "resi": list(cleavage_sites)},
                {"sphere": {"scale": 0.35, "color": "0x000000"}},
            )

        view.zoomTo({"chain": core_chains})
    else:
        view.setStyle({"cartoon": {"color": "spectrum"}})
        view.zoomTo()

    if spin:
        view.spin(True)

    html = view._make_html()
    # py3Dmol bakes a fixed "width: NNNpx; height: NNNpx;" into the div style.
    # If that doesn't exactly match the actual rendered iframe box (which
    # varies with the browser/column width), the browser adds scrollbars
    # inside the box. Make the div fill its container instead, and let the
    # outer iframe stretch to the real column width -- no more mismatch,
    # no more scrollbars.
    html = re.sub(r"width:\s*\d+px", "width: 100%", html)
    html = re.sub(r"height:\s*\d+px", "height: 100%", html)
    html = (
        "<html><head><style>"
        "html, body { margin:0; padding:0; height:100%; width:100%; overflow:hidden; }"
        "</style></head><body>" + html + "</body></html>"
    )
    st.iframe(html, height=height, width="stretch")
