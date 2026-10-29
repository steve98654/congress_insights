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
| `data/analysis.json` | The ten cross-member insights below |
| `scripts/` | `refresh_data.py` (fetch), `build_members.py`, `plays.py` (rules), `analysis.py`, `build_insights.py` |
| `site/` | Astro site: overview, member pages, goal pages, insights, CSV call sheets |
| `docs/` | [Hosting and refresh](docs/hosting.md), [weekly caucus research task](docs/weekly-research.md) |

## Insights

Ten views across all of Congress, on the site under Insights:

1. **Senate whip count**: no votes on caucus bills, ranked by persuadability (home-state split, committee seat, other caucus support).
2. **Floor math**: backers against 218 and 290 for each House bill, and which bills could be discharged.
3. **Next cosponsors**: the ten best cosponsor asks for each House bill, with reasons.
4. **Caucus gaps**: PSC members not yet on bills the caucus endorsed. Co-chairs also get these as actions.
5. **Missing Senate companions**: House bills with no Senate version and the bipartisan pair best placed to introduce one.
6. **Committee bottlenecks**: committees holding caucus bills, ranked by the support waiting on them.
7. **State delegations**: support per goal by state, and the bill most of each delegation already backs.
8. **Bridge builders**: members backing the most caucus bills led by the other party.
9. **Momentum**: cosponsors added in the last 90 days.
10. **Call sheets**: `actions.csv` and `members.csv` downloads with phones and offices.

Sponsors of bills with 150+ backers stuck in committee also get a discharge petition action.

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
without network access. The committed bill data comes from a live govinfo refresh.

## Caveats

- The PSC roster is the caucus's public list (43 members). Members who have not been listed publicly are
  not flagged.
- Senate committees of jurisdiction for House-only bills are inferred and labeled "likely".
- Priorities rank options for one member. They are not predictions of what the member will do.
