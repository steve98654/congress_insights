# Member sign-in

The site has two halves:

| Path | Who sees it | Layout |
|---|---|---|
| `/`, `/sign-in/` | Everyone. The public purple.nexus pages. | `site/src/layouts/Public.astro` |
| `/caucus/*` | Signed-in caucus members and their staff. The workspace: members, goals, insights, outreach, call sheets. | `site/src/layouts/Base.astro` |

Keeping every private page under one prefix means one access rule covers all of it, and new private pages are
protected by default as long as they live in `site/src/pages/caucus/`.

## Recommended: Cloudflare Access in front of `/caucus/`

The site stays a static Astro build. Cloudflare Access does the login, so there are no passwords, sessions or
user tables in this repo.

- **User names are email addresses.** A member (or a staffer they name) enters the address on the allow list
  and gets a one-time code by email. Access can later add Google or Microsoft sign-in, or a hardware key
  requirement, without code changes.
- **Free for up to 50 users**, which covers the caucus. Beyond that it is a per-user fee.
- **Per-member pages.** Access attaches a signed token (`Cf-Access-Jwt-Assertion`) to every request. The Worker in
  `site/worker/index.ts` verifies it against the team's public keys, looks the email
  up in the `MEMBER_ACCOUNTS` secret and redirects to `/caucus/members/<slug>/`. The **Sign in** button on the
  public site points at `/caucus/me/`, so signing in lands each member on their own page.
- **No member data in the repo.** The email to member mapping is a Cloudflare secret, not a committed file.

### Setup (one time, about 20 minutes)

1. Follow docs/hosting.md to deploy the `purple-nexus` Worker and attach the `purple.nexus` domain.
2. Zero Trust > Settings: pick a team name (for example `purple-nexus`). The team domain is
   `https://purple-nexus.cloudflareaccess.com`.
3. Zero Trust > Access > Applications > Add > Self-hosted:
   - Domains: `purple.nexus/caucus` and `purple-nexus.<account>.workers.dev/caucus` (protect the workers.dev
     address too, or set `workers_dev: false` in `site/wrangler.jsonc`, or it becomes a back door).
   - Identity provider: One-time PIN.
   - Policy "Caucus": Allow, Include > Emails > the member and staff addresses.
   - Copy the **Application Audience (AUD) tag**.
4. Workers & Pages > purple-nexus > Settings > Variables and secrets:
   - `ACCESS_TEAM_DOMAIN` = the team domain from step 2
   - `ACCESS_AUD` = the AUD tag from step 3
   - `MEMBER_ACCOUNTS` (secret) = `{"jane@mail.house.gov": "jane-doe-ny", "staffer@mail.house.gov": "jane-doe-ny"}`
     where the slug is the member's page under `/caucus/members/`.
5. Redeploy. Visit `/sign-in/` and press **Continue with your email**.

To add or remove someone, edit the Access policy (who may sign in) and `MEMBER_ACCOUNTS` (which page they land on).

## What this does not do yet

Every signed-in person can still open every member's page. That is fine while the workspace holds only public
record data (committees, bills, votes, election results). Before it holds anything private to one member, such
as notes on their background, expertise and connections, those insights should move out of the static build:

- store each member's private insights in Cloudflare KV or D1, keyed by member slug;
- serve them from the Worker (for example `/caucus/api/me`, added to `run_worker_first`) that reads the verified email, as `me/` does,
  and returns only that member's record;
- render them on the member page with a small client-side fetch.

That keeps the static site, adds per-member authorization in about one more function, and keeps private data out
of git.

## Alternatives considered

- **Auth.js, Clerk or Lucia with Astro server output.** Full control over accounts and roles, but the site would
  need a server runtime, a user database, password resets and session security that we would own. Worth it only
  if members need features Access cannot give, such as editing data on the site.
- **GitHub Pages with no login.** Simplest, but `/caucus/` would be public. Fine for previews only.
