# SG-ATLAS site -- what changed and how to deploy it

## What this is
Your existing app, restructured into a real 4-page Streamlit site with the
approved homepage design as the landing page:

- `sg_atlas_app.py` -- **entry point**. Same filename Streamlit Cloud is
  already configured to run, so you shouldn't need to change any deployment
  settings. Its only job is page config + routing.
- `home_page.py` -- the new homepage (hero, nav, floating crystal background).
- `sg_atlas_tool.py` -- your original matching dashboard, moved here
  unchanged in behavior (was previously the entire `sg_atlas_app.py`).
- `database_page.py` -- new "Discover Database" page: searchable/filterable
  table of all 201 structures in `known_structures.csv`.
- `about_page.py` -- placeholder ("Coming soon"), per your answer.
- `shared_ui.py` -- fonts, colors, the top nav bar, the floating crystal
  background, and the 6XYO placeholder -- one shared source of truth.
- `nav_config.py` -- the four pages, defined once, imported everywhere so
  navigation is never pointing at two different copies of the "same" page.
- `assets/crystal_1-4.svg` -- your four original background exports, used
  as-is (see note below).

Everything else (`sg_atlas_fragments.py`, `pymol_viewer.py`,
`known_structures.csv`, `requirements.txt`) is carried over unchanged.

## Deploying
1. Push this whole folder's contents to the repo root (same repo Streamlit
   Cloud already points at).
2. Make sure `sg_atlas_cache.db` (your populated cache) is committed
   alongside these files, same as before -- the tool and database pages
   both read it.
3. No Streamlit Cloud settings need to change: the main file is still
   `sg_atlas_app.py`.

## Notes on things I decided without asking (all small, all easy to change)
- **Left/right chevrons** around the molecule showcase: made decorative
  (no click behavior), since none was specified. Easy to wire to
  `st.switch_page` or a carousel later if you want them functional.
- **Nav active-state**: `render_top_nav()` takes an `active=` argument but
  doesn't visually style it yet -- your reference image shows all three nav
  items in the same weight regardless of page, so I matched that. Say the
  word and I'll add an underline/weight change for the current page.
- **Mobile**: the two-column hero stacks vertically under ~640px width, and
  the crystal background crops (not squishes) to keep proportions correct
  at any width, per the accessibility/responsive rules in your own
  UI-Pro-Max skill (mobile-first, no fixed widths, `prefers-reduced-motion`
  respected on the float animation).

## Wiring in the real 6XYO animation later
Everything lives behind one function: `render_protein_showcase()` in
`shared_ui.py`. Replace its body with the real animation's render call,
keep the same `height` footprint, and nothing around it (chevrons, layout,
spacing) needs to change.

## On the crystal SVGs
All four of your uploaded SVGs turned out to embed the exact same 1536x1024
source sprite, just cropped/transformed differently onto a shared 1440x810
canvas -- i.e. they're already the real background layers from the original
site. I used them as-is (only switching `preserveAspectRatio` from `meet`
to `slice` so they crop-to-fill instead of letterboxing at odd aspect
ratios) and layered independent slow float/rotate CSS animations on top, so
the reproduction is pixel-accurate to your reference image, not an
approximation.
