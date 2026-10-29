# Weekly caucus research (Claude scheduled task)

Run this every Tuesday, the day after the automated **Data refresh** workflow. It covers what needs
reading and judgment rather than a feed. Work from the latest `main`.

Goal: keep `goals/*.yaml` and `data/psc_roster.yaml` in step with what the Problem Solvers Caucus is
actually pushing, then open one pull request.

1. Read the caucus press releases from the last 7 days at
   https://problemsolverscaucus.house.gov/media/press-releases-all (each release is a
   `news/documentsingle.aspx?DocumentID=` link). For each one:
   - A new bill endorsement: add it to the goal it fits, or start a new goal file if none fits. Give
     `id` (`hr1234`), `short`, `what`, `house_committees` from the bill's referral and the likely
     `senate_committees` with `senate_committees_inferred: true`. Add the release URL to `sources` and
     bump `endorsed`.
   - A letter or statement without a bill: add it to `psc_ask` or `summary` of the goal it belongs to,
     with the URL in `sources`.
   - A vote the caucus is whipping: add `senate_vote: senate_vote_<congress>_<session>_<roll>` or
     `house_vote: house_vote_<year>_<roll>` to the bill.
2. Check https://problemsolverscaucus.house.gov/caucus-members against `data/psc_roster.yaml` and add or
   remove members, with `checked:` set to today.
3. `pip install pyyaml requests`, then run `python scripts/refresh_data.py bills`,
   `python scripts/refresh_data.py votes`, `python scripts/build_members.py` and
   `python scripts/build_insights.py`. If govinfo or senate.gov is blocked, say so in the PR; the Monday
   workflow fetches them from GitHub Actions.
4. In `site/`: `npm ci && npm run check && npm run build`.
5. Commit to `claude/weekly-research-<YYYY-MM-DD>`, push and open a pull request titled
   "Weekly caucus research <date>" listing every change with its source link. Assign `steve98654`.
   Don't merge it.
