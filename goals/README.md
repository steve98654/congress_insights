# Goal library

One file per legislative goal taken from the House Problem Solvers Caucus (PSC) agenda. Each goal is the
"play" that member briefs turn into action items.

Keys:

- `id`, `title`, `area`, `summary`: what the goal is.
- `psc_ask`: what the caucus is asking Congress to do, in its own framing.
- `endorsed`: date the caucus endorsed or introduced it (latest one if several).
- `sources`: links the goal was built from. Every goal needs at least one.
- `bills`: bills that advance the goal. `id` is the congress.gov style id (`hr9340`, `s1837`, `hjres4`).
  `house_committees` and `senate_committees` are committee codes from `data/sources/committees-current.yaml`;
  the House side comes from the bill's referral, the Senate side is the likely committee of jurisdiction
  and is marked `senate_committees_inferred: true` until a Senate bill is referred. `companion` links a
  House bill and its Senate twin. `status` overrides the status derived from the bill data, with
  `status_note` saying why.
- `unnumbered`: proposals in the agenda without a bill number yet.
- `committees`: for goals with no bill (appropriations), the committees where the work happens.

Bill data (sponsor, cosponsors, committees, actions, votes) lives in `data/bills/` and is refreshed by
`scripts/refresh_data.py bills`.
