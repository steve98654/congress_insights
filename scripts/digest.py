"""Weekly digest: what changed since the last snapshot.

Run after build_insights.py. Compares data/insights.json and data/members.json with the newest snapshot in
data/history/ older than today's build, writes data/digest.json (read by the site) and briefs/DIGEST.md,
then saves today's snapshot. Snapshots are small: per bill supporters, stage and latest action, per member
tier, score and top action.

    python scripts/digest.py                  # compare with the last snapshot and save a new one
    python scripts/digest.py --snapshot-only  # just save today's snapshot (used to seed history)
"""

import sys

from common import BRIEFS, DATA, load_json, write_json

HISTORY = DATA / "history"


def snapshot(insights, members):
    by_bio = {m["bioguide"]: m for m in members}
    bills = {}
    for g in insights["goals"]:
        for b in g["bills"]:
            bills[b["id"]] = {
                "goal": g["id"], "label": b["label"], "short": b["short"], "stage": b["stage"],
                "supporters": sorted(b["supporters"]), "latest": b.get("latest") or {},
                "house_vote": b.get("house_vote", ""), "senate_result": b.get("senate_result", ""),
                "cbo": len(b.get("cbo") or []),
            }
    return {
        "generated": insights["generated"],
        "bills": bills,
        "members": {i["bioguide"]: {"tier": i["tier"], "score": i["score"],
                                    "top": i["actions"][0]["text"] if i["actions"] else "",
                                    "election": (by_bio.get(i["bioguide"], {}).get("election") or {}).get("status")}
                    for i in insights["members"]},
    }


def who(by_bio, ids):
    out = []
    for x in ids:
        m = by_bio.get(x)
        out.append({"slug": m["slug"], "name": m["name"], "label": m["label"], "party": m["party"],
                    "psc": bool(m["psc"])} if m else {"slug": None, "name": x, "label": "", "party": "", "psc": False})
    return sorted(out, key=lambda w: w["name"])


def compare(old, new, members):
    by_bio = {m["bioguide"]: m for m in members}
    bills = []
    for bid, b in new["bills"].items():
        o = old["bills"].get(bid)
        if not o:
            bills.append({"bill": bid, "label": b["label"], "short": b["short"], "goal": b["goal"], "new_goal_bill": True,
                          "added": [], "dropped": [], "notes": ["Added to the caucus goals."]})
            continue
        added = sorted(set(b["supporters"]) - set(o["supporters"]))
        dropped = sorted(set(o["supporters"]) - set(b["supporters"]))
        notes = []
        if b["stage"] != o["stage"]:
            notes.append(f"Moved from {o['stage'].replace('_', ' ')} to {b['stage'].replace('_', ' ')}.")
        if b["latest"].get("date") and b["latest"] != o["latest"]:
            notes.append(f"{b['latest']['date']}: {b['latest'].get('text', '')}")
        if b["house_vote"] and b["house_vote"] != o["house_vote"]:
            notes.append(f"House vote recorded: {b['house_vote']}.")
        if b["senate_result"] and b["senate_result"] != o["senate_result"]:
            notes.append(f"Senate: {b['senate_result']}")
        if b["cbo"] > o["cbo"]:
            notes.append("New CBO cost estimate.")
        if added or dropped or notes:
            bills.append({"bill": bid, "label": b["label"], "short": b["short"], "goal": b["goal"],
                          "added": who(by_bio, added), "dropped": who(by_bio, dropped), "notes": notes,
                          "supporters": len(b["supporters"]), "was": len(o["supporters"])})
    bills.sort(key=lambda r: -(len(r["added"]) + len(r["dropped"]) + 5 * len(r["notes"])))

    tiers, elections = [], []
    for bio, m in new["members"].items():
        o = old["members"].get(bio)
        if not o or bio not in by_bio:
            continue
        base = who(by_bio, [bio])[0]
        if m["tier"] != o["tier"]:
            tiers.append(dict(base, was=o["tier"], now=m["tier"], top=m["top"]))
        if m.get("election") != o.get("election") and o.get("election") is not None:
            elections.append(dict(base, was=o["election"], now=m["election"]))
    joined = [bio for bio in new["members"] if bio not in old["members"]]
    left = [bio for bio in old["members"] if bio not in new["members"]]
    return {
        "since": old["generated"], "generated": new["generated"],
        "bills": bills, "tiers": sorted(tiers, key=lambda r: (r["now"], r["name"])),
        "elections": elections, "joined": who(by_bio, joined), "left": [{"name": x} for x in left],
        "totals": {"cosponsors_added": sum(len(b["added"]) for b in bills),
                   "cosponsors_dropped": sum(len(b["dropped"]) for b in bills),
                   "bills_changed": len(bills), "tier_changes": len(tiers)},
    }


def people(ws):
    return ", ".join(f"{w['name']} ({w['label']})" for w in ws)


def render(d):
    t = d["totals"]
    lines = [f"# Weekly digest: {d['since']} to {d['generated']}", "",
             f"{t['bills_changed']} caucus bills changed, {t['cosponsors_added']} cosponsors added, "
             f"{t['cosponsors_dropped']} dropped, {t['tier_changes']} members changed tier.", ""]
    if d["bills"]:
        lines += ["## Bills", ""]
        for b in d["bills"]:
            head = f"**{b['label']}** ({b['short']})"
            if "was" in b and b["was"] != b["supporters"]:
                head += f": {b['was']} to {b['supporters']} backers"
            lines.append(f"- {head}")
            for n in b["notes"]:
                lines.append(f"  - {n}")
            if b["added"]:
                lines.append(f"  - Added: {people(b['added'][:15])}"
                             + (f" and {len(b['added']) - 15} more" if len(b["added"]) > 15 else ""))
            if b["dropped"]:
                lines.append(f"  - Dropped: {people(b['dropped'])}")
        lines.append("")
    if d["elections"]:
        lines += ["## Election status", ""]
        lines += [f"- {e['name']} ({e['label']}): {e['was'].replace('_', ' ')} to {e['now'].replace('_', ' ')}"
                  for e in d["elections"]]
        lines.append("")
    if d["tiers"]:
        lines += ["## Tier changes", ""]
        lines += [f"- [{r['name']} ({r['label']})]({r['slug']}.md): {r['was']} to {r['now']}. Top action: {r['top']}"
                  for r in d["tiers"]]
        lines.append("")
    if d["joined"] or d["left"]:
        lines += ["## Membership", ""]
        lines += [f"- Joined: {w['name']} ({w['label']})" for w in d["joined"]]
        lines += [f"- Left: {w['name']}" for w in d["left"]]
        lines.append("")
    return "\n".join(lines)


def main():
    insights = load_json(DATA / "insights.json")
    members = load_json(DATA / "members.json")
    new = snapshot(insights, members)
    HISTORY.mkdir(parents=True, exist_ok=True)
    if "--snapshot-only" not in sys.argv:
        older = sorted(p for p in HISTORY.glob("*.json") if p.stem < new["generated"])
        if older:
            d = compare(load_json(older[-1]), new, members)
            write_json(DATA / "digest.json", d)
            (BRIEFS / "DIGEST.md").write_text(render(d), encoding="utf-8")
            print(f"digest: since {d['since']}: {d['totals']}")
        else:
            print("digest: no earlier snapshot; saving the first one")
    write_json(HISTORY / f"{new['generated']}.json", new)


if __name__ == "__main__":
    main()
