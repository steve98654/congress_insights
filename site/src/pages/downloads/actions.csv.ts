import type { APIRoute } from 'astro';
import { billById, goalById, insights, memberById } from '../../lib/data';
import { csv } from '../../lib/csv';

export const GET: APIRoute = () => {
  const rows: unknown[][] = [['member', 'label', 'chamber', 'tier', 'leaving', 'priority', 'goal', 'bill', 'action', 'why', 'outreach', 'phone', 'office']];
  for (const i of insights) {
    const m = memberById.get(i.bioguide)!;
    for (const a of i.actions) {
      const touch = i.outreach.find((e) => (e.bill && e.bill === a.bill) || (!e.bill && e.goal === a.goal));
      rows.push([m.name, m.label, m.chamber, i.tier, m.election.departing ? 'yes' : '', a.priority, goalById.get(a.goal)?.title,
        a.bill ? billById.get(a.bill)?.label : '', a.text, a.why, touch ? `${touch.stage} ${touch.date}` : '', m.contact.phone, m.contact.office]);
    }
  }
  return new Response(csv(rows), { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
};
