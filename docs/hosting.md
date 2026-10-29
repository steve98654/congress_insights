# Hosting and data refresh

## Hosting the site

`.github/workflows/deploy.yml` builds `site/` and publishes it on every push to `main`. It does nothing
until the repository variable `DEPLOY_TARGET` is set (Settings > Secrets and variables > Actions > Variables).

### Option A: GitHub Pages (simplest)

1. Settings > Pages > Build and deployment > Source: **GitHub Actions**.
2. Set the variable `DEPLOY_TARGET` = `github-pages` and run the **Deploy site** workflow.
3. The site is at `https://steve98654.github.io/congress_insights/`, readable by anyone with the link.
   On a private repo, Pages needs a paid GitHub plan.

### Option B: Cloudflare Pages with an email login

Free for up to 50 users; people sign in with a one-time code sent to an allowed email address.

1. Create a Cloudflare account and copy the **Account ID**.
2. Create an API token with *Account > Cloudflare Pages > Edit*.
3. Add the secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`, then the variable
   `DEPLOY_TARGET` = `cloudflare`. Optionally set `CF_PAGES_PROJECT` (default `congress-insights`).
4. Run **Deploy site**. The site appears at `https://congress-insights.pages.dev`.
5. Cloudflare dashboard > Workers & Pages > congress-insights > Settings > **Enable access policy**, and
   list the emails allowed in.

Both options add a `robots.txt` asking search engines not to index the site.

## Weekly data refresh

`.github/workflows/refresh.yml` runs every Monday at 09:23 UTC and on demand from the Actions tab:

| Step | Source | Updates |
|---|---|---|
| `refresh_data.py legislators` | [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) | `data/sources/*.yaml`: members, committees, seats, leadership |
| `refresh_data.py bills` | govinfo BILLSTATUS XML | `data/bills/<id>.json`: sponsor, cosponsors, committees, actions, votes for each goal bill |
| `refresh_data.py votes` | senate.gov and clerk.house.gov roll call XML | `data/votes/<key>.json` for votes named in `goals/*.yaml` |
| `build_members.py` | the above plus `data/psc_roster.yaml` | `data/members.json` |
| `build_insights.py` | everything | `data/insights.json`, `briefs/*.md` |

It then checks that the site builds and opens a pull request. One-time setup: Settings > Actions >
General > Workflow permissions > tick **Allow GitHub Actions to create and approve pull requests**.

The first refresh (2026-10-29) replaced the seed snapshots with parsed govinfo XML. The Senate roll call
still comes from the seed snapshot, which matches the official tally (57-43).

## Updating goals

The weekly Claude task in [weekly-research.md](weekly-research.md) reads new caucus press releases and
proposes goal and roster changes. To add a goal by hand, copy a file in `goals/`, list its bills, run
`python scripts/refresh_data.py bills votes` and then the two build scripts.
