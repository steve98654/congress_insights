// The ten cross-member analyses, in the order the Insights page lists them.
export const INSIGHTS = [
  ['whip', 'Senate whip count', 'Senators who voted no on caucus bills, ranked by how persuadable they look.'],
  ['floor-math', 'Floor math', 'How many votes each House bill is short of a majority and of a two-thirds suspension vote, and which could be discharged.'],
  ['targets', 'Next cosponsors', 'For each House bill, the ten members most likely to sign on next and why.'],
  ['psc-gaps', 'Caucus gaps', 'PSC members not yet on bills their own caucus endorsed.'],
  ['companions', 'Missing Senate companions', 'House bills with no Senate version, and the bipartisan pair of senators best placed to introduce one.'],
  ['committees', 'Committee bottlenecks', 'The committees where caucus bills are stuck, with the chair and ranking member who control them.'],
  ['delegations', 'State delegations', 'Support for each goal by state, and the bill most of each delegation already backs.'],
  ['bridges', 'Bridge builders', 'Members who back the most caucus bills led by the other party.'],
  ['momentum', 'Momentum', 'Cosponsors added in the last 90 days.'],
  ['downloads', 'Call sheets', 'Every action item as a spreadsheet, with phone numbers and offices.'],
] as const;
