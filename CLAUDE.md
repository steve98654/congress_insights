# Congress Insights

- Python scripts in `scripts/` (run from the repo root); Astro site in `site/` (Node 22, `npm ci`).
- After changing `goals/`, `data/psc_roster.yaml`, `data/sources/` or any script, run
  `python scripts/build_members.py && python scripts/build_insights.py` and commit `data/` and `briefs/`.
- Every goal and every bill needs a source link. Senate committees for House-only bills are inferred and
  must keep `senate_committees_inferred: true`.
- Check the site with `cd site && npm run check && npm run build`.
- The weekly research task is in `docs/weekly-research.md`.
