# Congress Insights

- Python scripts in `scripts/` (run from the repo root); Astro site in `site/` (Node 22, `npm ci`).
- The site is purple.nexus: public pages at `/` (`layouts/Public.astro`), caucus workspace under
  `site/src/pages/caucus/` (`layouts/Base.astro`), which sign-in protects. Private pages go under `caucus/`. See `docs/auth.md`.
- After changing `goals/`, `data/psc_roster.yaml`, `data/sources/`, `data/outreach.yaml` or any script, run
  `python scripts/build_members.py && python scripts/build_insights.py && python scripts/digest.py` and commit `data/` and `briefs/`.
- Every goal and every bill needs a source link. Senate committees for House-only bills are inferred and
  must keep `senate_committees_inferred: true`.
- Check the site with `cd site && npm run check && npm run build`.
- The weekly research task is in `docs/weekly-research.md`.
