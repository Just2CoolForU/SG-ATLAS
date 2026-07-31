import py3Dmol
from stmol import showmol

def render_pdb_3d(pdb_id):
    """Render interactive 3D structure inside Streamlit sidebar/panel."""
    view = py3Dmol.view(query=f'pdb:{pdb_id.lower()}')
    view.setStyle({'cartoon': {'color': 'spectrum'}})
    view.addSurface(py3Dmol.VDW, {'opacity': 0.7, 'color': 'white'}) # Show SASA envelope
    view.zoomTo()
    showmol(view, height=350, width=400)