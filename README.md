# SG ATLAS — Homepage

Static homepage for SG-ATLAS, matching the approved design (navy wordmark,
wireframe crystal background, ball-and-stick molecule graphic) plus a
scrollable gallery for protein structure animations.

## Files

- `index.html` — page structure (hero + scroller section)
- `style.css` — all styling and theme (colors, type, layout, responsive rules)
- `script.js` — powers the protein animation scroller
- `assets/` — put your animation files (mp4 / gif) here

## Adding your protein animations

Open `script.js` and add entries to the `PROTEIN_ANIMATIONS` array near the top:

```js
const PROTEIN_ANIMATIONS = [
  { src: "assets/tau-fibril.mp4", type: "video", label: "Tau fibril, cross-beta core", pdbId: "6QJH" },
  { src: "assets/asyn-rod.gif",   type: "image", label: "Alpha-synuclein rod polymorph", pdbId: "6CU7" },
];
```

- `type: "video"` — mp4/webm, autoplays muted + looped
- `type: "image"` — gif or static image
- `pdbId` is optional — leave `""` if not applicable

Drop the actual files into `assets/`. Nothing else needs to change — slides,
dots, and arrow navigation are generated automatically from the array.

## Using it with Streamlit

This is plain HTML/CSS/JS, so the cleanest path is to keep it as a **static
landing page** served separately from your Streamlit app (e.g. GitHub Pages),
with your "Use Tool" button linking to your Streamlit app's URL.

If you'd rather embed it directly inside Streamlit as the app's landing view,
you can render it with:

```python
import streamlit as st
import pathlib

st.set_page_config(page_title="SG ATLAS", layout="wide")

html = pathlib.Path("index.html").read_text()
css = pathlib.Path("style.css").read_text()
js = pathlib.Path("script.js").read_text()

# Inline the CSS/JS into the HTML since st.components serves in an isolated iframe
html = html.replace('<link rel="stylesheet" href="style.css">', f"<style>{css}</style>")
html = html.replace('<script src="script.js"></script>', f"<script>{js}</script>")

st.components.v1.html(html, height=1400, scrolling=True)
```

Note: fonts are loaded from Google Fonts via `<link>` tags in `index.html`,
which will still work inside the iframe as long as the deployed app has
outbound internet access (Streamlit Community Cloud does).

## Fixes made from the original mockup

- "Cyro-EM" → "Cryo-EM"
- "intrepretive" → "interpretive"

If you actually want the typos kept for some reason, they're a one-line
change in `index.html` and `script.js`'s slide captions.
