import type { APIRoute } from 'astro';
import { ELECTION_STATUS, committeeName, insights, memberById } from '../../lib/data';
import { csv } from '../../lib/csv';

export const GET: APIRoute = () => {
  const rows: unknown[][] = [['member', 'label', 'chamber', 'state', 'party', 'tier', 'score', 'psc', 'leadership', 'committees', 'supports', 'top_action', 'election_2026', 'phone', 'website']];
  for (const i of insights) {
    const m = memberById.get(i.bioguide)!;
    rows.push([
      m.name, m.label, m.chamber, m.state, m.party, i.tier, i.score, m.psc ?? '', m.leadership.join('; '),
      m.committees.map((c) => committeeName(c.name) + (c.title ? ` (${c.title})` : '')).join('; '),
      `${i.support.count}/${i.support.total}`, i.actions[0]?.text ?? '', ELECTION_STATUS[m.election.status], m.contact.phone, m.contact.url,
    ]);
  }
  return new Response(csv(rows), { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
};
