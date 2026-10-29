# Seed snapshots

Text snapshots of govinfo BILLSTATUS records and one Senate roll call, captured on 2026-10-29 while the
environment that built the first version could not reach govinfo.gov or senate.gov directly.
`python scripts/refresh_data.py seed` turns them into `data/bills/*.json` and `data/votes/*.json`.

Running `python scripts/refresh_data.py bills` (done weekly by the Data refresh workflow) replaces them with
data parsed straight from the XML. Two snapshots (`hr3514`, `hr2048`) were cut short at about 190 and 200
cosponsors and are flagged `COSPONSORS_PARTIAL`, so members missing from those lists may already be
cosponsors. The briefs say so until the live refresh runs.
