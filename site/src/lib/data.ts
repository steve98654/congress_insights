import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// The site is built from site/, so the repo's data/ folder is one level up.
const DATA = resolve(process.cwd(), '..', 'data');
const read = <T>(name: string): T => JSON.parse(readFileSync(resolve(DATA, name), 'utf8')) as T;

export interface Seat {
  code: string;
  name: string;
  rank?: number;
  side?: string;
  title?: string;
  parent?: string;
}

export interface Member {
  bioguide: string;
  slug: string;
  name: string;
  last: string;
  chamber: 'house' | 'senate';
  state: string;
  district: number | null;
  seat: string;
  party: string;
  caucus: string;
  label: string;
  title: string;
  voting: boolean;
  years_in_chamber: number;
  term_end: string;
  leadership: string[];
  floor_leader: boolean;
  psc: string | null;
  committees: Seat[];
  subcommittees: Seat[];
  contact: { url?: string; phone?: string; office?: string; x?: string };
}

export interface Action {
  goal: string;
  bill: string | null;
  priority: number;
  kind: string;
  text: string;
  why: string;
  partners: string[];
}

export interface Insight {
  bioguide: string;
  slug: string;
  score: number;
  tier: 'A' | 'B' | 'C';
  rank: number;
  rank_of: number;
  support: { count: number; total: number };
  actions: Action[];
  action_count: number;
  goals: Record<string, { position: string; leverage: number }>;
  partners: string[];
}

export interface Bill {
  id: string;
  label: string;
  short: string;
  what: string;
  url: string;
  chamber: 'house' | 'senate';
  stage: string;
  status_note?: string;
  companion?: string;
  sponsor_name: string | null;
  sponsor_id: string | null;
  supporters: string[];
  stats: { supporters: number; R: number; D: number; psc: number; bipartisan: boolean };
  house_committees: string[];
  senate_committees: string[];
  senate_committees_inferred?: boolean;
  committee_vote: string;
  house_vote: string;
  senate_result: string;
  senate_votes: Record<string, string>;
  senate_votes_short: number | null;
  cosponsors_complete: boolean;
  latest: { date?: string; text?: string };
  data_source: string;
  data_fetched?: string;
}

export interface Goal {
  id: string;
  title: string;
  area: string;
  summary: string;
  psc_ask: string;
  endorsed: string;
  sources: string[];
  committees: string[];
  unnumbered: { title: string; what: string; committees?: string[] }[];
  bills: Bill[];
}

interface InsightsFile {
  generated: string;
  goals: Goal[];
  members: Insight[];
}

const insightsFile = read<InsightsFile>('insights.json');
export const generated = insightsFile.generated;
export const goals = insightsFile.goals;
export const members = read<Member[]>('members.json');
export const insights = insightsFile.members;

export const memberBySlug = new Map(members.map((m) => [m.slug, m]));
export const memberById = new Map(members.map((m) => [m.bioguide, m]));
export const insightBySlug = new Map(insights.map((i) => [i.slug, i]));
export const goalById = new Map(goals.map((g) => [g.id, g]));
export const billById = new Map(goals.flatMap((g) => g.bills.map((b) => [b.id, b] as const)));

export const STAGES: Record<string, string> = {
  in_committee: 'In committee',
  reported: 'Reported, awaiting floor',
  passed_house: 'Passed House',
  passed_senate: 'Passed Senate',
  enacted: 'Law',
};
export const STAGE_ORDER = ['in_committee', 'reported', 'passed_house', 'passed_senate', 'enacted'];

export const committeeName = (name: string) =>
  name.replace(/^(House|Senate) (Permanent Select |Select |Special )?Committee on (the )?/, '');

const codeNames = new Map<string, string>();
for (const m of members) for (const c of [...m.committees, ...m.subcommittees]) codeNames.set(c.code, committeeName(c.name));
export const committeeByCode = (code: string) => codeNames.get(code) ?? code;

export const url = (path = '') => `${import.meta.env.BASE_URL.replace(/\/$/, '')}/${path}`;
export const memberUrl = (slug: string) => url(`members/${slug}/`);
export const goalUrl = (id: string) => url(`goals/${id}/`);

export const partyName = (p: string) => ({ R: 'Republican', D: 'Democrat', I: 'Independent' })[p] ?? p;

export function formatDate(iso?: string) {
  if (!iso) return '';
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
}

export interface Who {
  slug: string;
  name: string;
  label: string;
  party: string;
  psc: boolean;
}
type BillRef = { goal: string; bill: string; label: string; short: string };

export interface Analysis {
  generated: string;
  whip: (BillRef & { yeas: number; needed: number; short_by: number; result: string; nays: (Who & { score: number; reasons: string[] })[] })[];
  floor_math: (BillRef & {
    stage: string;
    supporters: number;
    to_majority: number;
    to_suspension: number;
    bipartisan: boolean;
    days_since_intro: number | null;
    discharge_ready: boolean;
    complete: boolean;
  })[];
  delegations: {
    state: string;
    members: number;
    house: number;
    senate: number;
    psc: Who[];
    tier_a: number;
    goal_support: Record<string, number>;
    closest_bill: { bill: string; label: string; short: string; share: number; on: number; of: number; missing: Who[] } | null;
  }[];
  committees: {
    code: string;
    name: string;
    chamber: string;
    size: number;
    chair: Who | null;
    ranking: Who | null;
    bills: (BillRef & { stage: string; supporters: number; committee_supporters: number; committee_share: number })[];
    waiting: number;
    bottleneck: number;
  }[];
  bridges: Record<'house' | 'senate', (Who & { cross_party: number; total: number })[]>;
  companions: (BillRef & { stage: string; supporters: number; committees: string[]; inferred: boolean; pair: (Who & { reasons: string[] })[] })[];
  psc_gaps: (BillRef & { psc_on: number; psc_total: number; missing: Who[]; complete: boolean })[];
  targets: (BillRef & { sponsor: Who | null; targets: (Who & { score: number; reasons: string[] })[] })[];
  momentum: (BillRef & { dated: boolean; recent: number | null; recent_members: (Who & { date: string })[]; last_added: string | null })[];
}

export const analysis = read<Analysis>('analysis.json');
