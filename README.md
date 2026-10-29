# Congress Insights

Action items for every member of Congress, House and Senate, toward the bipartisan goals of the
[Problem Solvers Caucus](https://problemsolverscaucus.house.gov/). It follows the
[cal_insights](https://github.com/steve98654/cal_insights) pattern: a brief per member, a library of
goals that act as plays, a weekly data refresh and a static site.

For each member and goal, `scripts/plays.py` looks at where each bill is (in committee, reported, passed
one chamber) and at the member's leverage at that stage: sponsorship, the chair or ranking seat on the
committee holding it, other committee seats, floor leadership, recorded votes, PSC membership and the
state delegation. It writes concrete next steps such as "Schedule a markup of H.R. 3289 in Budget" or
"Help find the 3 votes H.R. 9340 still needs: start with ...", each with a reason and a priority.

## What's here

| Path | What |
|---|---|
| `goals/` | 10 goals from caucus endorsements and its affordability agenda, with the bills, committees and sources ([README](goals/README.md)) |
| `briefs/` | One markdown brief per member ([index](briefs/README.md)) |
| `data/members.json` | 539 members with committees, leadership and PSC membership |
| `data/bills/`, `data/votes/` | Sponsor, cosponsors, status and roll calls for the 23 goal bills |
| `data/insights.json` | Everything the site reads: actions, scores, tiers, partners |
| `scripts/` | `refresh_data.py` (fetch), `build_members.py`, `plays.py` (rules), `build_insights.py` |
| `site/` | Astro site: overview, member pages, goal pages |
| `docs/` | [Hosting and refresh](docs/hosting.md), [weekly caucus research task](docs/weekly-research.md) |

## Tiers

- **A, the pilot group**: PSC members, floor leaders, and chairs and ranking members of the committees
  that hold caucus bills.
- **B**: at least one action with priority 60 or more, usually a committee seat on a caucus bill.
- **C**: little leverage today. Their briefs still show cosponsor asks when home-state colleagues are on a bill.

## Build

```sh
pip install pyyaml requests
python scripts/refresh_data.py all      # needs network access to GitHub, govinfo.gov and senate.gov
python scripts/build_members.py
python scripts/build_insights.py
cd site && npm ci && npm run build      # or npm run dev
```

`python scripts/refresh_data.py seed` rebuilds bill and vote data from the snapshots in `data/seed/`
without network access.

## Caveats

- The PSC roster is the caucus's public list (43 members). Members who have not been listed publicly are
  not flagged.
- Senate committees of jurisdiction for House-only bills are inferred and labeled "likely".
- Priorities rank options for one member. They are not predictions of what the member will do.
