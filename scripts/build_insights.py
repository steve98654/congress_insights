"""Build member insights: action items toward each PSC goal for every member of Congress.

Reads data/members.json, goals/*.yaml, data/bills/*.json and data/votes/*.json.
Writes data/insights.json (used by the site), briefs/<slug>.md and briefs/README.md.
"""

import datetime
import re
from collections import Counter

import analysis
import plays
from common import (BILLS, BRIEFS, DATA, VOTES, load_yaml, bill_chamber, bill_label, bill_url, load_goals, load_json,
                    vote_key, write_json)

TOP_ACTIONS = 8
OUTREACH_STAGES = ["to_contact", "contacted", "meeting", "committed", "done", "declined"]


def load_outreach(members, goals):
    """data/outreach.yaml: our asks of each office and where they stand."""
    path = DATA / "outreach.yaml"
    entries = ((load_yaml(path) or {}).get("entries") or []) if path.exists() else []
    by_key = {m["slug"]: m for m in members} | {m["bioguide"]: m for m in members}
    goal_ids = {g["id"] for g in goals}
    bill_ids = {b["id"] for g in goals for b in g["bills"]}
    out = []
    for n, e in enumerate(entries, 1):
        m = by_key.get(str(e.get("member", "")))
        problems = [] if m else [f"unknown member {e.get('member')!r}"]
        if e.get("stage") not in OUTREACH_STAGES:
            problems.append(f"stage must be one of {', '.join(OUTREACH_STAGES)}")
        if e.get("goal") and e["goal"] not in goal_ids:
            problems.append(f"unknown goal {e['goal']!r}")
        if e.get("bill") and e["bill"] not in bill_ids:
            problems.append(f"unknown bill {e['bill']!r}")
        if problems:
            raise SystemExit(f"data/outreach.yaml entry {n}: " + "; ".join(problems))
        out.append({"bioguide": m["bioguide"], "slug": m["slug"], "goal": e.get("goal"), "bill": e.get("bill"),
                    "stage": e["stage"], "date": str(e.get("date") or ""), "owner": e.get("owner") or "",
                    "notes": e.get("notes") or ""})
    return sorted(out, key=lambda e: e["date"], reverse=True)



def short_committee(name):
    name = re.sub(r"^(House|Senate) (Permanent Select |Select |Special )?Committee on (the )?", "", name)
    return name.replace("House Permanent Select Committee on ", "").strip()


class Context:
    def __init__(self, members, goals):
        self.members = {m["bioguide"]: m for m in members}
        self.by_lis = {m["ids"]["lis"]: m for m in members if m["ids"].get("lis")}
        self.chairs, self.rankings, self.cnames = {}, {}, {}
        for m in members:
            for c in m["committees"] + m["subcommittees"]:
                self.cnames[c["code"]] = c["name"]
                title = c.get("title", "").lower()
                if title.startswith("chair"):
                    self.chairs[c["code"]] = m
                elif "ranking" in title:
                    self.rankings[c["code"]] = m
        speaker = next((m for m in members if "Speaker of the House" in m["leadership"]), None)
        self.house_majority = speaker["caucus"] if speaker else "R"
        self.goals = goals
        self.support_count = Counter()
        self.supports = {}

    @staticmethod
    def days_since(iso):
        return (datetime.date.today() - datetime.date.fromisoformat(iso)).days if iso else None

    def committee_chair(self, code):
        return self.chairs.get(code)

    def committee_ranking(self, code):
        return self.rankings.get(code)

    def committee_name(self, code):
        return short_committee(self.cnames.get(code, code))

    def leaders(self, chamber, majority=True):
        out = []
        for m in self.members.values():
            if m["chamber"] == chamber and m["floor_leader"]:
                if not majority or m["caucus"] == self.house_majority:
                    out.append(m)
        return out

    def senate_nays(self, bill):
        return sorted((self.members[b] for b, v in bill["senate_votes"].items() if v == "Nay" and b in self.members),
                      key=lambda m: (m["state"], m["last"]))

    def partners(self, m, pool, k=3):
        """Other-caucus colleagues most likely to team up: shared state, committees, caucus bills and PSC."""
        mine = {c["code"] for c in m["committees"]}
        my_support = self.supports.get(m["bioguide"], set())
        scored = []
        for x in pool:
            if x["bioguide"] == m["bioguide"] or x["caucus"] == m["caucus"] or x["chamber"] != m["chamber"]:
                continue
            shared = mine & {c["code"] for c in x["committees"]}
            score = 3 * (x["state"] == m["state"]) + 2 * len(shared) + 2 * bool(x["psc"]) \
                + 0.5 * len(my_support & self.supports.get(x["bioguide"], set())) \
                + 0.1 * self.support_count[x["bioguide"]]
            scored.append((score, x["name"], x))
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [x for _, _, x in scored[:k]]


def tally(vote_text):
    text = re.sub(r"\d{4}-\d{2}-\d{2}", "", vote_text or "")
    m = re.search(r"\b(\d{1,3})\s*-\s*(\d{1,3})\b", text)
    return f"{m.group(1)}-{m.group(2)}" if m else ""


def resolve_bill(ctx, goal, entry):
    data = load_json(BILLS / f"{entry['id']}.json", {}) or {}
    b = dict(entry)
    b["label"] = bill_label(entry["id"])
    b["chamber"] = bill_chamber(entry["id"])
    b["url"] = bill_url(entry["id"])
    b["title"] = data.get("title") or entry.get("short")
    b["committees"] = data.get("committees", [])
    b.setdefault("house_committees", [c for c in b["committees"] if c.startswith("HS")])
    b.setdefault("senate_committees", [c for c in b["committees"] if c.startswith("SS")])
    sponsor = data.get("sponsor") or {}
    b["sponsor_id"] = sponsor.get("bioguide")
    b["sponsor"] = sponsor
    b["cosponsor_ids"] = [c["bioguide"] for c in data.get("cosponsors", [])]
    b["supporter_ids"] = set(b["cosponsor_ids"]) | ({b["sponsor_id"]} if b["sponsor_id"] else set())
    b["cosponsors_complete"] = data.get("cosponsors_complete", False)
    b["stage"] = entry.get("status") or data.get("status") or "in_committee"
    b["latest"] = data.get("latest", {})
    b["introduced"] = data.get("introduced")
    b["summary"] = data.get("summary")
    b["cbo"] = data.get("cbo", [])
    b["policy_area"] = data.get("policy_area")
    b["data_source"] = data.get("fetched_via", "missing")
    b["data_fetched"] = data.get("fetched")
    vote_texts = [v.get("text", "") for v in data.get("votes", [])]
    committee_votes = [t for t in vote_texts + [b["latest"].get("text", "")] if "report" in t.lower() and tally(t)]
    b["committee_vote"] = f"committee vote {tally(committee_votes[0])}" if committee_votes else ""
    house_pass = [t for t in vote_texts if re.search(r"house", t, re.I) and re.search(r"pass", t, re.I)]
    b["house_vote"] = tally(house_pass[0]) if house_pass else ""

    # Roll calls: the goal can name one; otherwise use the latest recorded vote we have data for.
    keys = {"senate": [], "house": []}
    for v in sorted(data.get("votes", []), key=lambda v: v.get("date", ""), reverse=True):
        k = vote_key(v.get("url"))
        if k and k not in keys[k.split("_")[0]]:
            keys[k.split("_")[0]].append(k)
    for chamber in ("senate", "house"):
        named = entry.get(f"{chamber}_vote")
        chosen = next((k for k in ([named] if named else []) + keys[chamber] if (VOTES / f"{k}.json").exists()), None)
        by_member, result, url = {}, "", None
        if chosen:
            v = load_json(VOTES / f"{chosen}.json", {}) or {}
            for row in v.get("members", []):
                m = ctx.by_lis.get(row.get("lis")) if chamber == "senate" else ctx.members.get(row.get("bioguide"))
                if m:
                    by_member[m["bioguide"]] = row["vote"]
            result = f"{v.get('result', chamber.title() + ' vote')} ({v.get('question', '')}, {v.get('date', '')[:10]})."
            url = v.get("source_url")
        b[f"{chamber}_votes"], b[f"{chamber}_vote_url"] = by_member, url
        b["senate_result" if chamber == "senate" else "house_result"] = result
    yeas = sum(1 for x in b["senate_votes"].values() if x == "Yea")
    b["senate_votes_short"] = max(0, 60 - yeas) if b["senate_votes"] else None
    if b["house_votes"] and not b["house_vote"]:
        c = Counter(b["house_votes"].values())
        b["house_vote"] = f"{c.get('Yea', 0) + c.get('Aye', 0)}-{c.get('Nay', 0) + c.get('No', 0)}"

    parties = Counter(ctx.members[x]["caucus"] for x in b["supporter_ids"] if x in ctx.members)
    b["stats"] = {
        "supporters": len(b["supporter_ids"]),
        "R": parties.get("R", 0),
        "D": parties.get("D", 0),
        "psc": sum(1 for x in b["supporter_ids"] if x in ctx.members and ctx.members[x]["psc"]),
        "bipartisan": parties.get("R", 0) >= 2 and parties.get("D", 0) >= 2,
    }
    return b


def public_bill(b):
    out = {k: v for k, v in b.items() if k not in ("supporter_ids", "senate_votes", "house_votes", "cosponsor_ids")}
    out["sponsor_name"] = b["sponsor"].get("name") if b["sponsor"] else None
    out["supporters"] = sorted(b["supporter_ids"])
    out["senate_votes"] = b["senate_votes"]
    out["house_votes"] = b["house_votes"]
    return out


def member_role_on_bill(b, m):
    if m["bioguide"] == b["sponsor_id"]:
        return "sponsor"
    if m["bioguide"] in b["supporter_ids"]:
        return "cosponsor"
    vote = b["senate_votes"].get(m["bioguide"]) or b["house_votes"].get(m["bioguide"])
    if vote:
        return f"voted {vote.lower()}"
    return None


def first_sentences(text, limit=320):
    text = re.sub(r"\s+", " ", text or "").strip()
    out = ""
    for sent in re.split(r"(?<=[.;])\s+", text):
        if out and len(out) + len(sent) > limit:
            break
        out = f"{out} {sent}".strip()
    return out[:limit + 80]


def talking_points(ctx, m, actions, goals_by_id, k=3):
    """Short, sourced points a member or staffer can use on the bills behind their top actions."""
    out, seen = [], set()
    for a in actions:
        if not a["bill"] or a["bill"] in seen:
            continue
        seen.add(a["bill"])
        g = goals_by_id[a["goal"]]
        b = next(x for x in g["resolved_bills"] if x["id"] == a["bill"])
        pts = []
        what = b.get("what") or (first_sentences(b["summary"]["text"]) if b.get("summary") else "")
        if what:
            pts.append(what)
        s = b["stats"]
        if s["supporters"]:
            line = f"{s['supporters']} members back it: {s['R']} Republicans and {s['D']} Democrats"
            if s["psc"]:
                line += f", including {s['psc']} Problem Solvers"
            pts.append(line + ".")
        home = [ctx.members[x] for x in b["supporter_ids"] if x in ctx.members and x != m["bioguide"]
                and ctx.members[x]["state"] == m["state"]]
        if home:
            pts.append(f"{len(home)} of your {m['state']} colleagues {'is' if len(home) == 1 else 'are'} on it: {', '.join(x['name'] for x in home[:3])}"
                       + (" and others." if len(home) > 3 else "."))
        if b["house_vote"] and b["stage"] != "in_committee":
            pts.append(f"It passed the House {b['house_vote']}.")
        if b["senate_votes_short"]:
            pts.append(f"It is {b['senate_votes_short']} votes short of 60 in the Senate.")
        if b.get("cbo"):
            c = b["cbo"][-1]
            pts.append(f"CBO ({c['date']}): {first_sentences(c.get('description') or c['title'], 220)}")
        role = member_role_on_bill(b, m)
        if role:
            pts.append(f"Your record: {role}.")
        out.append({"goal": g["id"], "bill": b["id"], "label": b["label"], "short": b["short"],
                    "headline": f"{b['label']}, {b['short']}: {g['title']}", "points": pts,
                    "cbo_url": b["cbo"][-1]["url"] if b.get("cbo") else None})
        if len(out) >= k:
            break
    return out


def render_brief(m, ins, goals_by_id, ctx, generated):
    lines = [f"# {m['title']} {m['name']} ({m['label']})", ""]
    facts = [f"{'Senator' if m['chamber'] == 'senate' else 'Representative'} for {m['seat']}",
             f"{m['years_in_chamber']:g} years in the {m['chamber'].title()}"]
    if m["psc"]:
        facts.append(f"Problem Solvers Caucus {m['psc'].lower() if m['psc'] == 'Member' else m['psc']}")
    if m["leadership"]:
        facts.append(", ".join(m["leadership"]))
    e = m.get("election") or {}
    if e.get("departing"):
        facts.append(f"Leaving Congress in January ({e['status'].replace('_', ' ')}{': ' + e['detail'] if e.get('detail') else ''})")
    lines += [" · ".join(facts), ""]
    lines += [f"**Priority tier {ins['tier']}** · leverage score {ins['score']} "
              f"(rank {ins['rank']} of {ins['rank_of']} in the {m['chamber'].title()}) · "
              f"supports {ins['support']['count']} of {ins['support']['total']} caucus bills in their chamber", ""]
    if m["committees"]:
        lines.append("**Committees:** " + "; ".join(
            short_committee(c["name"]) + (f" ({c['title']})" if c.get("title") else "") for c in m["committees"]))
        lines.append("")

    lines += ["## Top actions", ""]
    if not ins["actions"]:
        lines += ["No specific action stands out for this member yet: they hold no committee seat or leadership role on the caucus goals, and their home-state colleagues are not cosponsors.", ""]
    for i, a in enumerate(ins["actions"], 1):
        g = goals_by_id[a["goal"]]
        bill = next((b for b in g["resolved_bills"] if b["id"] == a["bill"]), None)
        ref = f" [{bill['label']}]({bill['url']})" if bill else ""
        lines.append(f"{i}. **{a['text']}** _{g['title']}{(' ·' + ref) if ref else ''} · priority {a['priority']}_  ")
        lines.append(f"   {a['why']}")
    lines.append("")

    if ins.get("talking_points"):
        lines += ["## Talking points", ""]
        for tp in ins["talking_points"]:
            lines.append(f"**{tp['headline']}**")
            lines += [f"- {p}" for p in tp["points"]]
            if tp.get("cbo_url"):
                lines.append(f"- [CBO cost estimate]({tp['cbo_url']})")
            lines.append("")

    if ins.get("outreach"):
        lines += ["## Outreach", "", "| Date | Stage | Ask | Owner | Notes |", "|---|---|---|---|---|"]
        for e in ins["outreach"]:
            ask = e["bill"] or e["goal"] or ""
            lines.append(f"| {e['date']} | {e['stage'].replace('_', ' ')} | {ask} | {e['owner']} | {e['notes'].replace('|', '/')} |")
        lines.append("")

    lines += ["## Position on each goal", "", "| Goal | Bills | Position | Leverage |", "|---|---|---|---|"]
    for gid, pos in ins["goals"].items():
        g = goals_by_id[gid]
        bills = ", ".join(f"[{b['label']}]({b['url']})" for b in g["resolved_bills"]) or "committee work"
        lines.append(f"| {g['title']} | {bills} | {pos['position'] or '-'} | {pos['leverage']} |")
    lines.append("")

    if ins["partners"]:
        lines += ["## Cross-party partners", ""]
        for slug in ins["partners"]:
            p = next(x for x in ctx.members.values() if x["slug"] == slug)
            shared = {c["code"] for c in m["committees"]} & {c["code"] for c in p["committees"]}
            why = []
            if p["state"] == m["state"]:
                why.append("same state")
            if shared:
                why.append("shared committees: " + ", ".join(ctx.committee_name(c) for c in sorted(shared)))
            if p["psc"]:
                why.append("PSC member")
            lines.append(f"- [{p['title']} {p['name']} ({p['label']})]({slug}.md): {'; '.join(why) or 'backs the same caucus bills'}")
        lines.append("")

    partial = [b["label"] for g in ctx.goals for b in g["resolved_bills"] if not b["cosponsors_complete"]]
    lines += ["## Sources", "",
              "- Member, committee and leadership data: [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators)",
              "- Bill sponsors, cosponsors and status: govinfo BILLSTATUS (links on each bill above)",
              "- Caucus goals and roster: [problemsolverscaucus.house.gov](https://problemsolverscaucus.house.gov/)", ""]
    if partial:
        lines += [f"Cosponsor lists for {', '.join(partial)} are incomplete until the next data refresh, so a member shown as not cosponsoring them may already be on.", ""]
    lines += [f"_Generated {generated} by `scripts/build_insights.py`. Priorities rank the options; they are not predictions._", ""]
    return "\n".join(lines)


def main():
    members = load_json(DATA / "members.json")
    goals = load_goals()
    ctx = Context(members, goals)
    for g in goals:
        g["resolved_bills"] = [resolve_bill(ctx, g, b) for b in g["bills"]]
    for g in goals:
        for b in g["resolved_bills"]:
            for x in b["supporter_ids"]:
                ctx.support_count[x] += 1
                ctx.supports.setdefault(x, set()).add(b["id"])
    goals_by_id = {g["id"]: g for g in goals}
    outreach = load_outreach(members, goals)
    # Senators are also scored on House bills they have voted on.
    chamber_bills = {ch: [b for g in goals for b in g["resolved_bills"]
                          if b["chamber"] == ch or (ch == "senate" and b["senate_votes"])] for ch in ("house", "senate")}

    insights = []
    for m in members:
        actions, per_goal = [], {}
        for g in goals:
            acts = plays.actions_for(ctx, g, m)
            actions += acts
            roles = [r for r in (member_role_on_bill(b, m) for b in g["resolved_bills"]) if r]
            per_goal[g["id"]] = {
                "position": ", ".join(sorted(set(roles))),
                "leverage": max((a["priority"] for a in acts), default=0),
            }
        actions.sort(key=lambda a: -a["priority"])
        top = actions[:TOP_ACTIONS]
        # Weighted toward the single best move: one strong lever matters more than many weak ones.
        score = round(sum(w * a["priority"] for w, a in zip((0.5, 0.25, 0.15, 0.1), actions)))
        lead_seat = any(c.get("title") for c in m["committees"]
                        if any(c["code"] in (b["house_committees"] + b["senate_committees"]) for g in goals for b in g["resolved_bills"])
                        or any(c["code"] in g["committees"] for g in goals))
        tier = "A" if (m["psc"] or m["floor_leader"] or lead_seat) else "B" if actions and actions[0]["priority"] >= 60 else "C"
        support_total = len(chamber_bills[m["chamber"]])
        support_count = sum(1 for b in chamber_bills[m["chamber"]]
                            if m["bioguide"] in b["supporter_ids"] or b["senate_votes"].get(m["bioguide"]) == "Yea")
        pool = [x for x in members if x["chamber"] == m["chamber"] and x["voting"]]
        insights.append({
            "bioguide": m["bioguide"],
            "slug": m["slug"],
            "score": score,
            "tier": tier,
            "support": {"count": support_count, "total": support_total},
            "actions": top,
            "action_count": len(actions),
            "goals": per_goal,
            "partners": [p["slug"] for p in ctx.partners(m, pool, 3)],
            "talking_points": talking_points(ctx, m, actions, goals_by_id),
            "outreach": [e for e in outreach if e["bioguide"] == m["bioguide"]],
        })

    for chamber in ("house", "senate"):
        ranked = sorted((i for i in insights if ctx.members[i["bioguide"]]["chamber"] == chamber), key=lambda i: -i["score"])
        for n, i in enumerate(ranked, 1):
            i["rank"], i["rank_of"] = n, len(ranked)

    generated = datetime.date.today().isoformat()
    goal_out = []
    for g in goals:
        go = {k: v for k, v in g.items() if k not in ("bills", "resolved_bills")}
        go["bills"] = [public_bill(b) for b in g["resolved_bills"]]
        goal_out.append(go)
    write_json(DATA / "insights.json", {"generated": generated, "goals": goal_out, "members": insights,
                                        "outreach": outreach, "outreach_stages": OUTREACH_STAGES})

    data_by_bill = {b["id"]: load_json(BILLS / f"{b['id']}.json", {}) or {} for g in goals for b in g["bills"]}
    write_json(DATA / "analysis.json", dict(generated=generated, **analysis.build(ctx, goals, insights, data_by_bill)))

    BRIEFS.mkdir(exist_ok=True)
    for old in BRIEFS.glob("*.md"):
        if old.name not in ("README.md", "DIGEST.md"):
            old.unlink()
    by_bio = {i["bioguide"]: i for i in insights}
    for m in members:
        (BRIEFS / f"{m['slug']}.md").write_text(render_brief(m, by_bio[m["bioguide"]], goals_by_id, ctx, generated), encoding="utf-8")

    index = ["# Member briefs", "",
             f"One brief per member of Congress ({len(members)}), with action items toward the Problem Solvers Caucus goals in "
             "[goals/](../goals). Tier A is PSC members, floor leaders, and chairs and ranking members of the committees "
             "holding caucus bills: the pilot group. Tier B has at least one strong action. Tier C has little leverage today.", ""]
    for chamber in ("senate", "house"):
        index += [f"## {chamber.title()}", "", "| Member | Tier | Score | Supports | Top action |", "|---|---|---|---|---|"]
        rows = sorted((m for m in members if m["chamber"] == chamber), key=lambda m: (-by_bio[m["bioguide"]]["score"], m["last"]))
        for m in rows:
            i = by_bio[m["bioguide"]]
            top = i["actions"][0]["text"].replace("|", "/") if i["actions"] else ""
            index.append(f"| [{m['name']} ({m['label']})]({m['slug']}.md) | {i['tier']} | {i['score']} | "
                         f"{i['support']['count']}/{i['support']['total']} | {top} |")
        index.append("")
    (BRIEFS / "README.md").write_text("\n".join(index), encoding="utf-8")
    tiers = Counter(i["tier"] for i in insights)
    print(f"insights: {len(insights)} members, tiers {dict(sorted(tiers.items()))}, "
          f"{sum(i['action_count'] for i in insights)} actions")


if __name__ == "__main__":
    main()
