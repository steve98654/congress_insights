# Hosting and data refresh

## Hosting the site

### Recommended: Cloudflare Workers with an email login

The public pages stay open; the caucus workspace under `/caucus/` needs a sign-in. `site/wrangler.jsonc` serves
the Astro build (`dist/`) as static assets, and `site/worker/index.ts` runs only for `/caucus/me` (it sends a
signed-in member to their own page). Cloudflare builds and deploys on every push to `main` (Workers Builds).

1. Cloudflare dashboard > Workers & Pages > Create > Import a repository > `steve98654/congress_insights`.
2. Fill in:

   | Field | Value |
   |---|---|
   | Project name | `purple-nexus` (must match `name` in `wrangler.jsonc`) |
   | Build command | `npm ci && npm run build` |
   | Deploy command | `npx wrangler deploy` |
   | Non-production branch deploy command | leave the default |
   | Path (root directory) | `/site` |

   The build reads `../data/`, so the whole repo is needed, not just `site/`. Node 22 comes from `site/.node-version`.
3. Deploy. The site appears at `https://purple-nexus.<account>.workers.dev`.
4. Settings > Domains & Routes > add the custom domain `purple.nexus`.
5. Put Cloudflare Access in front of `/caucus/` and set the sign-in variables: [auth.md](auth.md).

`site/public/robots.txt` keeps search engines out of `/caucus/`, and `site/public/_headers` marks it noindex.

### Alternative: GitHub Pages (no login)

1. Settings > Pages > Build and deployment > Source: **GitHub Actions**.
2. Set the repository variable `DEPLOY_TARGET` = `github-pages` and run the **Deploy site** workflow.
3. The site is at `https://steve98654.github.io/congress_insights/`, readable by anyone with the link,
   including `/caucus/`. On a private repo, Pages needs a paid GitHub plan.

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
