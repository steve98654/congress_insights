"""Cross-member analyses built on the same context as the briefs.

Each function returns plain data for data/analysis.json; the site renders one page per analysis.

  whip          Senate no votes on caucus bills, ranked by how persuadable they look
  floor_math    House bills: votes short of a majority (218) and of suspension (290), discharge readiness
  delegations   per state: support for each goal and the bill most of the delegation already backs
  committees    the committees holding caucus bills, ranked as bottlenecks
  bridges       members who back caucus bills led by the other party
  companions    House bills with no Senate version, and the bipartisan Senate pair best placed to introduce one
  psc_gaps      PSC members not yet on bills their own caucus endorsed
  targets       the next cosponsors to ask for each House bill
  momentum      cosponsors added in the last 90 days
"""

import datetime
from collections import Counter, defaultdict

HOUSE_MAJORITY = 218
SUSPENSION = 290
DISCHARGE_DAYS = 60  # bills must sit in committee 30 legislative days; about two calendar months


def _brief(m):
    return {"slug": m["slug"], "name": m["name"], "label": m["label"], "party": m["party"], "psc": bool(m["psc"])}


def house_bills(goals):
    return [(g, b) for g in goals for b in g["resolved_bills"] if b["chamber"] == "house"]


def bridge_scores(ctx, goals):
    """Count of caucus bills a member backs whose sponsor is from the other party."""
    scores = Counter()
    for g in goals:
        for b in g["resolved_bills"]:
            sponsor = ctx.members.get(b["sponsor_id"])
            if not sponsor:
                continue
            for x in b["supporter_ids"]:
                m = ctx.members.get(x)
                if m and x != sponsor["bioguide"] and m["caucus"] != sponsor["caucus"]:
                    scores[x] += 1
    return scores


def whip(ctx, goals):
    out = []
    for g in goals:
        for b in g["resolved_bills"]:
            if not b["senate_votes"]:
                continue
            yeas = {x for x, v in b["senate_votes"].items() if v == "Yea"}
            rows = []
            for x, v in b["senate_votes"].items():
                if v != "Nay" or x not in ctx.members:
                    continue
                m = ctx.members[x]
                home_yea = [ctx.members[y] for y in yeas if ctx.members[y]["state"] == m["state"]]
                on_committee = [c for c in m["committees"] if c["code"] in b["senate_committees"]]
                caucus_bills = len(ctx.supports.get(x, set()))
                reasons = []
                if home_yea:
                    reasons.append(f"home-state colleague {home_yea[0]['name']} voted yes")
                if on_committee:
                    reasons.append("sits on the committee of jurisdiction")
                if caucus_bills:
                    reasons.append(f"backs {caucus_bills} other caucus bill{'s' if caucus_bills > 1 else ''}")
                score = 3 * bool(home_yea) + 2 * bool(on_committee) + caucus_bills
                rows.append(dict(_brief(m), score=score, reasons=reasons))
            rows.sort(key=lambda r: (-r["score"], r["name"]))
            out.append({
                "goal": g["id"], "bill": b["id"], "label": b["label"], "short": b["short"],
                "yeas": len(yeas), "needed": 60, "short_by": max(0, 60 - len(yeas)),
                "result": b["senate_result"], "nays": rows,
            })
    return out


def floor_math(ctx, goals):
    today = datetime.date.today()
    out = []
    for g, b in house_bills(goals):
        voting = [x for x in b["supporter_ids"] if x in ctx.members and ctx.members[x]["voting"]]
        intro = b.get("introduced")
        days = (today - datetime.date.fromisoformat(intro)).days if intro else None
        out.append({
            "goal": g["id"], "bill": b["id"], "label": b["label"], "short": b["short"], "stage": b["stage"],
            "supporters": len(voting),
            "to_majority": max(0, HOUSE_MAJORITY - len(voting)),
            "to_suspension": max(0, SUSPENSION - len(voting)),
            "bipartisan": b["stats"]["bipartisan"],
            "days_since_intro": days,
            "discharge_ready": b["stage"] == "in_committee" and days is not None and days >= DISCHARGE_DAYS,
            "complete": b["cosponsors_complete"],
        })
    out.sort(key=lambda r: r["to_majority"])
    return out


def delegations(ctx, goals, insights):
    by_state = defaultdict(list)
    for m in ctx.members.values():
        by_state[m["state"]].append(m)
    tier = {i["bioguide"]: i["tier"] for i in insights}
    out = []
    for state, ms in sorted(by_state.items()):
        ids = {m["bioguide"] for m in ms}
        goal_support = {}
        best = None
        for g in goals:
            backers = set()
            for b in g["resolved_bills"]:
                backers |= b["supporter_ids"] & ids
                if b["chamber"] != "house":
                    continue
                house = [m for m in ms if m["chamber"] == "house" and m["voting"]]
                on = [m for m in house if m["bioguide"] in b["supporter_ids"]]
                if not house or not on or len(on) == len(house):
                    continue
                share = len(on) / len(house)
                if best is None or share > best["share"]:
                    best = {"bill": b["id"], "label": b["label"], "short": b["short"], "share": round(share, 2),
                            "on": len(on), "of": len(house),
                            "missing": [_brief(m) for m in house if m["bioguide"] not in b["supporter_ids"]][:6]}
            goal_support[g["id"]] = len(backers)
        out.append({
            "state": state,
            "members": len(ms),
            "house": sum(m["chamber"] == "house" for m in ms),
            "senate": sum(m["chamber"] == "senate" for m in ms),
            "psc": [_brief(m) for m in ms if m["psc"]],
            "tier_a": sum(tier[m["bioguide"]] == "A" for m in ms),
            "goal_support": goal_support,
            "closest_bill": best,
        })
    return out


def committees(ctx, goals):
    held = defaultdict(list)
    for g in goals:
        for b in g["resolved_bills"]:
            if b["stage"] not in ("in_committee", "reported"):
                continue
            codes = b["house_committees"] if b["chamber"] == "house" else b["senate_committees"]
            for code in codes:
                held[code].append((g, b))
    out = []
    for code, items in held.items():
        seated = [m for m in ctx.members.values() if any(c["code"] == code for c in m["committees"])]
        seated_ids = {m["bioguide"] for m in seated}
        bills = []
        for g, b in items:
            on = len(b["supporter_ids"] & seated_ids)
            bills.append({"goal": g["id"], "bill": b["id"], "label": b["label"], "short": b["short"], "stage": b["stage"],
                          "supporters": b["stats"]["supporters"], "committee_supporters": on,
                          "committee_share": round(on / len(seated), 2) if seated else 0})
        chair, ranking = ctx.committee_chair(code), ctx.committee_ranking(code)
        waiting = [x for x in bills if x["stage"] == "in_committee"]
        out.append({
            "code": code, "name": ctx.committee_name(code), "chamber": "senate" if code.startswith("S") else "house",
            "size": len(seated),
            "chair": _brief(chair) if chair else None, "ranking": _brief(ranking) if ranking else None,
            "bills": sorted(bills, key=lambda x: -x["supporters"]),
            "waiting": len(waiting),
            # Bottleneck: bills stuck there, weighted by how much support is waiting on them.
            "bottleneck": round(sum(1 + x["supporters"] / 100 for x in waiting), 2),
        })
    out.sort(key=lambda c: -c["bottleneck"])
    return out


def bridges(ctx, goals, scores):
    out = {}
    for chamber in ("house", "senate"):
        rows = []
        for x, n in scores.items():
            m = ctx.members.get(x)
            if m and m["chamber"] == chamber:
                rows.append(dict(_brief(m), cross_party=n, total=len(ctx.supports.get(x, set()))))
        rows.sort(key=lambda r: (-r["cross_party"], -r["total"], r["name"]))
        out[chamber] = rows[:40]
    return out


def companions(ctx, goals, scores):
    senate = [m for m in ctx.members.values() if m["chamber"] == "senate"]
    out = []
    for g, b in house_bills(goals):
        if b.get("companion") or b["stage"] == "enacted" or not b["senate_committees"]:
            continue
        house_backers = Counter(ctx.members[x]["state"] for x in b["supporter_ids"] if x in ctx.members)
        cands = []
        for s in senate:
            seats = [c for c in s["committees"] if c["code"] in b["senate_committees"]]
            if not seats or s["floor_leader"]:
                continue
            lead = any("chair" in c.get("title", "").lower() or "ranking" in c.get("title", "").lower() for c in seats)
            score = 3 * lead + 0.3 * house_backers[s["state"]] + 0.5 * scores[s["bioguide"]] + 0.2 * len(ctx.supports.get(s["bioguide"], set()))
            reasons = [f"{house_backers[s['state']]} House members from {s['state']} back it"] if house_backers[s["state"]] else []
            if lead:
                reasons.insert(0, "chair or ranking member of the committee")
            cands.append((score, s, reasons))
        cands.sort(key=lambda c: (-c[0], c[1]["name"]))
        pair = []
        for caucus in ("R", "D"):
            pick = next((c for c in cands if c[1]["caucus"] == caucus), None)
            if pick:
                pair.append(dict(_brief(pick[1]), reasons=pick[2]))
        out.append({"goal": g["id"], "bill": b["id"], "label": b["label"], "short": b["short"], "stage": b["stage"],
                    "supporters": b["stats"]["supporters"], "committees": [ctx.committee_name(c) for c in b["senate_committees"]],
                    "inferred": bool(b.get("senate_committees_inferred")), "pair": pair})
    out.sort(key=lambda r: -r["supporters"])
    return out


def psc_gaps(ctx, goals):
    psc = [m for m in ctx.members.values() if m["psc"]]
    out = []
    for g, b in house_bills(goals):
        missing = [_brief(m) for m in psc if m["bioguide"] not in b["supporter_ids"]]
        out.append({"goal": g["id"], "bill": b["id"], "label": b["label"], "short": b["short"],
                    "psc_on": len(psc) - len(missing), "psc_total": len(psc), "missing": missing,
                    "complete": b["cosponsors_complete"]})
    out.sort(key=lambda r: -len(r["missing"]))
    return out


def targets(ctx, goals, scores, k=10):
    out = []
    for g, b in house_bills(goals):
        if b["stage"] in ("passed_house", "enacted"):
            continue
        state_backers = Counter(ctx.members[x]["state"] for x in b["supporter_ids"] if x in ctx.members)
        sponsor = ctx.members.get(b["sponsor_id"])
        rows = []
        for m in ctx.members.values():
            if m["chamber"] != "house" or not m["voting"] or m["bioguide"] in b["supporter_ids"]:
                continue
            on_committee = any(c["code"] in b["house_committees"] for c in m["committees"])
            same_goal = len(ctx.supports.get(m["bioguide"], set()) & {x["id"] for x in g["resolved_bills"]})
            score = 3 * bool(m["psc"]) + 2 * on_committee + 0.5 * min(state_backers[m["state"]], 6) \
                + 0.4 * scores[m["bioguide"]] + 1.5 * same_goal
            if score <= 0:
                continue
            reasons = []
            if m["psc"]:
                reasons.append("PSC member")
            if on_committee:
                reasons.append("on the committee")
            if state_backers[m["state"]]:
                reasons.append(f"{state_backers[m['state']]} state colleagues on it")
            if same_goal:
                reasons.append("backs a related caucus bill")
            if scores[m["bioguide"]]:
                reasons.append(f"backs {scores[m['bioguide']]} other-party caucus bills")
            rows.append((score, m, reasons))
        rows.sort(key=lambda r: (-r[0], r[1]["name"]))
        out.append({"goal": g["id"], "bill": b["id"], "label": b["label"], "short": b["short"],
                    "sponsor": _brief(sponsor) if sponsor else None,
                    "targets": [dict(_brief(m), score=round(s, 1), reasons=r) for s, m, r in rows[:k]]})
    return out


def momentum(ctx, goals, data_by_bill, days=90):
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    out = []
    for g in goals:
        for b in g["resolved_bills"]:
            cos = data_by_bill.get(b["id"], {}).get("cosponsors", [])
            dated = [c for c in cos if c.get("date")]
            if not dated:
                out.append({"goal": g["id"], "bill": b["id"], "label": b["label"], "short": b["short"], "dated": False,
                            "recent": None, "recent_members": [], "last_added": None})
                continue
            recent = sorted((c for c in dated if c["date"] >= cutoff), key=lambda c: c["date"], reverse=True)
            out.append({"goal": g["id"], "bill": b["id"], "label": b["label"], "short": b["short"], "dated": True,
                        "recent": len(recent),
                        "recent_members": [dict(_brief(ctx.members[c["bioguide"]]), date=c["date"]) for c in recent
                                           if c["bioguide"] in ctx.members][:8],
                        "last_added": max(c["date"] for c in dated)})
    out.sort(key=lambda r: (r["recent"] is None, -(r["recent"] or 0)))
    return out


def build(ctx, goals, insights, data_by_bill):
    scores = bridge_scores(ctx, goals)
    return {
        "whip": whip(ctx, goals),
        "floor_math": floor_math(ctx, goals),
        "delegations": delegations(ctx, goals, insights),
        "committees": committees(ctx, goals),
        "bridges": bridges(ctx, goals, scores),
        "companions": companions(ctx, goals, scores),
        "psc_gaps": psc_gaps(ctx, goals),
        "targets": targets(ctx, goals, scores),
        "momentum": momentum(ctx, goals, data_by_bill),
    }
