"""
pymol_viewer.py -- interactive 3D structure viewer for the SG-ATLAS
Streamlit app, built on py3Dmol/stmol (3Dmol.js under the hood).

This isn't just "load whatever PDB ID is on screen" -- the whole point is
that what you SEE has to match what SG-ATLAS actually computed for that
structure:

  - The full deposited assembly loads and renders (so you still see the
    real fibril/filament architecture, protofilaments included).
  - The specific chains SG-ATLAS classified as "core" (the ones the
    contact-graph filtering in the analysis pipeline kept, stored in
    structures.chain_ids) are highlighted in color.
  - Every other deposited chain is shown dim/grey, so it's visually obvious
    which part of the structure the SASA profile, fragment predictions, and
    confidence scores on screen actually correspond to -- not the whole
    assembly, just the highlighted subset.

If core_chains isn't supplied (e.g. viewing a structure with no cached
profile), it falls back to a plain full-structure cartoon so the viewer
still works, it just has nothing to highlight.
"""

import py3Dmol
from stmol import showmol


def render_pdb_3d(pdb_id, core_chains=None, height=440, width=760):
    """
    Render `pdb_id` with its core-shielded chains (if provided) highlighted
    against the rest of the deposited assembly.

    pdb_id: 4-character PDB ID, e.g. "6OSJ"
    core_chains: list of chain letters SG-ATLAS classified as core for this
        structure (structures.chain_ids from the cache), or None/[] to fall
        back to a plain full-structure view.
    """
    view = py3Dmol.view(query=f"pdb:{pdb_id.lower()}")

    if core_chains:
        # Dim every chain first...
        view.setStyle({}, {"cartoon": {"color": "0xD9D9D9", "opacity": 0.35}})
        # ...then bring the actual core-shielded chains to the front in color.
        # One consistent color per chain so it's readable at a glance, not a
        # meaningless rainbow across the whole assembly.
        palette = ["0xE63946", "0x1D3557", "0x2A9D8F", "0xF4A261", "0x6A4C93", "0xE9C46A"]
        for i, chain in enumerate(core_chains):
            view.setStyle(
                {"chain": chain},
                {"cartoon": {"color": palette[i % len(palette)]}},
            )
        view.zoomTo({"chain": core_chains})
    else:
        view.setStyle({"cartoon": {"color": "spectrum"}})
        view.zoomTo()

    showmol(view, height=height, width=width)
