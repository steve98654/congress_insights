"""Action rules: turn a member's position on a goal into concrete next steps.

Each rule looks at where a bill is (in committee, reported, passed one chamber) and at the member's
leverage over that stage (sponsor, chair or ranking member of the committee holding it, committee seat,
floor leadership, PSC membership, their vote, their state delegation). It returns actions with a
priority from 0 to 100. Priorities are a ranking aid, not a measured probability.

The context object `ctx` is built by build_insights.py and gives:
  ctx.members[bioguide]          member records from data/members.json
  ctx.committee_chair(code)      member holding the chair (or None)
  ctx.committee_ranking(code)    ranking member (or None)
  ctx.committee_name(code)       short committee name
  ctx.partners(m, pool, k)       best cross-party partners for m among pool
"""

STAGE_TEXT = {
    "in_committee": "in committee",
    "reported": "reported by committee, waiting for a floor vote",
    "passed_house": "passed the House, waiting on the Senate",
    "passed_senate": "passed the Senate, waiting on the House",
    "enacted": "law",
}


def action(goal, bill, priority, kind, text, why, partners=()):
    return {
        "goal": goal["id"],
        "bill": bill["id"] if bill else None,
        "priority": max(0, min(100, round(priority))),
        "kind": kind,
        "text": text,
        "why": why,
        "partners": [p["slug"] for p in partners],
    }


def names(members, limit=3):
    shown = [f"{m['title']} {m['name']} ({m['label']})" for m in members[:limit]]
    extra = len(members) - limit
    if extra > 0:
        shown.append(f"{extra} more")
    return ", ".join(shown) if shown else ""


def support_line(bill):
    s = bill["stats"]
    return f"{s['supporters']} sponsors and cosponsors ({s['R']} R, {s['D']} D, {s['psc']} PSC)"


def committee_seats(m, codes):
    return [c for c in m["committees"] if c["code"] in codes]


def is_chair(seat):
    return seat.get("title", "").lower().startswith("chair")


def is_ranking(seat):
    return "ranking" in seat.get("title", "").lower()


def recruit_targets(ctx, bill, codes, chamber, prefer_caucus=None, k=3):
    """Committee members not yet on the bill, PSC members and the named caucus first."""
    pool = []
    for m in ctx.members.values():
        if m["chamber"] != chamber or m["bioguide"] in bill["supporter_ids"] or not m["voting"]:
            continue
        seats = committee_seats(m, codes)
        if not seats:
            continue
        score = 2 * bool(m["psc"]) + (prefer_caucus is not None and m["caucus"] == prefer_caucus) \
            + 0.1 * len(seats) - 0.01 * min(c.get("rank") or 99 for c in seats)
        pool.append((score, m))
    pool.sort(key=lambda x: -x[0])
    return [m for _, m in pool[:k]]


def house_bill_in_house(ctx, goal, bill, m):
    out = []
    stage = bill["stage"]
    codes = bill["house_committees"] or bill["committees"]
    label, short = bill["label"], bill["short"]
    supporter = m["bioguide"] in bill["supporter_ids"]
    sponsor = m["bioguide"] == bill["sponsor_id"]
    seats = committee_seats(m, codes)
    delegation = [ctx.members[b] for b in bill["supporter_ids"]
                  if b in ctx.members and ctx.members[b]["state"] == m["state"] and b != m["bioguide"]]
    psc_bonus = 15 if m["psc"] else 0

    if stage == "in_committee":
        main = codes[0] if codes else None
        chair = ctx.committee_chair(main) if main else None
        if sponsor:
            if chair and chair["bioguide"] != m["bioguide"]:
                out.append(action(goal, bill, 90, "markup",
                                  f"Ask {chair['title']} {chair['name']}, chair of {ctx.committee_name(main)}, to mark up {label} ({short}).",
                                  f"You lead the bill. It has {support_line(bill)} and has not had a committee vote.",
                                  [chair]))
            targets = recruit_targets(ctx, bill, codes, "house", prefer_caucus="D" if m["caucus"] == "R" else "R")
            if targets:
                out.append(action(goal, bill, 80, "recruit",
                                  f"Recruit cosponsors on the committee of jurisdiction for {label}: {names(targets)}.",
                                  "Committee members who cosponsor make a markup easier to get. These are the highest-ranked committee members not yet on the bill, other party and PSC first.",
                                  targets))
        for seat in seats:
            cname = ctx.committee_name(seat["code"])
            if is_chair(seat) and not sponsor:
                out.append(action(goal, bill, 95, "markup",
                                  f"Schedule a markup of {label} ({short}) in {cname}.",
                                  f"As chair you control the committee calendar. The bill is PSC-endorsed with {support_line(bill)}.",
                                  []))
            elif is_ranking(seat) and not sponsor:
                chair = ctx.committee_chair(seat["code"])
                out.append(action(goal, bill, 75 + (0 if supporter else 5), "markup",
                                  (f"Ask {chair['title']} {chair['name']} to schedule a markup of {label}" if chair else f"Press for a markup of {label}")
                                  + ("" if supporter else ", and cosponsor it") + ".",
                                  f"As ranking member you can offer minority votes to get it marked up. It has {support_line(bill)}.",
                                  [chair] if chair else []))
            elif not sponsor:
                if supporter:
                    out.append(action(goal, bill, 55 + psc_bonus / 3, "markup",
                                      f"Press for a markup of {label} ({short}) in {cname}, where you sit.",
                                      f"You already cosponsor it, and your committee is where it is stuck.", []))
                else:
                    out.append(action(goal, bill, 68 + psc_bonus / 3, "cosponsor",
                                      f"Cosponsor {label} ({short}). It is waiting in {cname}, where you sit.",
                                      f"Committee cosponsors decide whether a bill gets marked up. It has {support_line(bill)}.", []))
            break  # one committee action per bill is enough
    elif stage == "reported":
        if m["floor_leader"] and m["caucus"] == ctx.house_majority and any(
                r in m["leadership"] for r in ("Speaker of the House", "House Majority Leader")):
            out.append(action(goal, bill, 95, "floor",
                              f"Schedule a floor vote on {label} ({short}).",
                              f"It cleared committee ({bill['committee_vote'] or 'reported'}) with {support_line(bill)}.", []))
        rules = committee_seats(m, ["HSRU"])
        if rules and not sponsor:
            out.append(action(goal, bill, 85 if is_chair(rules[0]) else 60, "floor",
                              f"Move {label} through Rules, or back taking it up under suspension.",
                              f"It has been reported ({bill['committee_vote'] or 'committee vote'}) and needs a way to the floor.", []))
        if sponsor:
            out.append(action(goal, bill, 90, "floor",
                              f"Ask the Speaker and Majority Leader for floor time on {label}, or a suspension vote.",
                              f"It cleared committee ({bill['committee_vote'] or 'reported'}). Suspension needs two-thirds, and it has {support_line(bill)}.",
                              [p for p in ctx.leaders("house", majority=True)]))
        elif supporter:
            out.append(action(goal, bill, 45 + psc_bonus, "floor",
                              f"Press leadership to bring {label} ({short}) to the floor.",
                              f"You cosponsor it and it has cleared committee ({bill['committee_vote'] or 'reported'}).", []))
        elif m["voting"]:
            out.append(action(goal, bill, 35 + psc_bonus + 5 * min(len(delegation), 2), "cosponsor",
                              f"Cosponsor {label} ({short}) before it reaches the floor.",
                              f"It cleared committee ({bill['committee_vote'] or 'reported'})."
                              + (f" {len(delegation)} of your state colleagues are on it: {names(delegation)}." if delegation else ""),
                              delegation[:2]))
        return out
    elif stage in ("passed_house", "enacted"):
        if sponsor and stage == "passed_house":
            nays = ctx.senate_nays(bill)
            home = [s for s in nays if s["state"] == m["state"]]
            targets = home or nays[:3]
            if targets:
                out.append(action(goal, bill, 70, "senate",
                                  f"Work the Senate on {label}: {names(targets)} voted no on cloture.",
                                  f"It passed the House ({bill['house_vote'] or 'passed'}), but {bill['senate_result'] or 'the Senate has not acted'}.",
                                  targets))
        return out

    # Bills still in committee or reported: general cosponsor ask for non-supporters not covered above.
    if stage in ("in_committee",) and not supporter and not seats and m["voting"]:
        base = 25 + psc_bonus + 6 * min(len(delegation), 3) + (5 if bill["stats"]["bipartisan"] else 0)
        if m["psc"] or len(delegation) >= 2:
            out.append(action(goal, bill, base, "cosponsor",
                              f"Cosponsor {label} ({short}).",
                              ("It is PSC-endorsed and you are a caucus member. " if m["psc"] else "")
                              + (f"{len(delegation)} colleagues from your state already cosponsor: {names(delegation)}." if delegation
                                 else f"It has {support_line(bill)}."),
                              delegation[:2]))
    if stage == "in_committee" and supporter and not sponsor and not seats and m["psc"]:
        pool = [x for x in ctx.members.values() if x["chamber"] == "house"
                and x["bioguide"] not in bill["supporter_ids"] and x["voting"]]
        partners = ctx.partners(m, pool, 1)
        if partners:
            out.append(action(goal, bill, 30, "recruit",
                              f"Bring a cross-party colleague onto {label}: {names(partners)} is the closest fit.",
                              "You already cosponsor it. Partners are picked by shared state, committees and past support for caucus bills.",
                              partners))
    return out


def senate_side(ctx, goal, bill, m):
    """Actions for senators on a House bill (passed or pending) or a Senate bill."""
    out = []
    label, short = bill["label"], bill["short"]
    codes = bill["senate_committees"]
    seats = committee_seats(m, codes)
    supporter = m["bioguide"] in bill["supporter_ids"]
    vote = bill["senate_votes"].get(m["bioguide"])
    inferred = " (likely committee of jurisdiction)" if bill.get("senate_committees_inferred") else ""

    if bill["chamber"] == "house" and bill["stage"] == "passed_house":
        if m["floor_leader"] and "Senate Majority Leader" in m["leadership"]:
            out.append(action(goal, bill, 95, "floor",
                              f"Bring {label} ({short}) back to the floor.",
                              f"It passed the House ({bill['house_vote'] or 'passed'}). {bill['senate_result'] or ''}".strip(), []))
        if vote == "Nay":
            out.append(action(goal, bill, 80 + (5 if seats else 0), "vote",
                              f"Name the changes that would get your vote on {label} ({short}).",
                              f"You voted no on cloture. It passed the House {bill['house_vote'] or ''} and needs {bill['senate_votes_short']} more votes in the Senate.".replace("  ", " "),
                              []))
        elif vote == "Yea":
            nays = ctx.senate_nays(bill)
            close = [s for s in nays if s["state"] == m["state"]] or \
                    [s for s in nays if committee_seats(s, [c["code"] for c in m["committees"]])][:3]
            if close:
                out.append(action(goal, bill, 55 + (10 if seats else 0), "whip",
                                  f"Help find the {bill['senate_votes_short']} votes {label} still needs: start with {names(close)}.",
                                  "You voted yes on cloture. These no votes are your home-state or committee colleagues.",
                                  close))
        elif seats:
            out.append(action(goal, bill, 60, "committee",
                              f"Move {label} ({short}) through {ctx.committee_name(seats[0]['code'])}{inferred}.",
                              f"It passed the House ({bill['house_vote'] or 'passed'}).", []))
        return out

    if bill["chamber"] == "house" and bill.get("companion"):
        return out  # handled through the Senate companion
    if bill["chamber"] == "house" and bill["stage"] in ("in_committee", "reported"):
        if not seats or m["floor_leader"]:
            return out
        seat = seats[0]
        pool = [x for x in ctx.members.values() if x["chamber"] == "senate" and committee_seats(x, [seat["code"]])]
        partners = ctx.partners(m, pool, 1)
        lead = is_chair(seat) or is_ranking(seat)
        out.append(action(goal, bill, 40 + (15 if lead else 0) + (10 if bill["stage"] == "reported" else 0), "companion",
                          f"Introduce a Senate companion to {label} ({short})" + (f" with {names(partners)}" if partners else "") + ".",
                          f"There is no Senate version yet, and you sit on {ctx.committee_name(seat['code'])}{inferred}. The House bill is {STAGE_TEXT[bill['stage']]} with {support_line(bill)}.",
                          partners))
        return out

    if bill["chamber"] == "senate":
        if bill["stage"] in ("passed_senate", "enacted"):
            return out
        main = codes[0] if codes else None
        for seat in seats:
            if is_chair(seat):
                out.append(action(goal, bill, 90, "markup",
                                  f"Mark up {label} ({short}) in {ctx.committee_name(seat['code'])}.",
                                  f"You chair the committee holding it. It has {support_line(bill)}.", []))
            elif is_ranking(seat):
                chair = ctx.committee_chair(seat["code"])
                out.append(action(goal, bill, 72, "markup",
                                  (f"Ask {chair['title']} {chair['name']} to mark up {label}." if chair else f"Press for a markup of {label}."),
                                  f"As ranking member you can bring the minority votes. It has {support_line(bill)}.",
                                  [chair] if chair else []))
            elif not supporter:
                out.append(action(goal, bill, 60, "cosponsor",
                                  f"Cosponsor {label} ({short}). It is waiting in {ctx.committee_name(seat['code'])}, where you sit.",
                                  f"It has {support_line(bill)}.", []))
            else:
                out.append(action(goal, bill, 45, "markup",
                                  f"Press for a markup of {label} in {ctx.committee_name(seat['code'])}.",
                                  "You cosponsor it and sit on the committee holding it.", []))
            break
        if not seats and not supporter:
            delegation = [ctx.members[b] for b in bill["supporter_ids"]
                          if b in ctx.members and ctx.members[b]["state"] == m["state"]]
            if delegation:
                out.append(action(goal, bill, 35, "cosponsor",
                                  f"Cosponsor {label} ({short}); your home-state colleague {names(delegation)} already has.",
                                  f"It has {support_line(bill)}.", delegation))
    return out


def house_side_of_senate_passed(ctx, goal, bill, house_bill, m):
    """The Senate passed its version; the House can take it up directly."""
    out = []
    label = bill["label"]
    if m["floor_leader"] and any(r in m["leadership"] for r in ("Speaker of the House", "House Majority Leader")):
        out.append(action(goal, bill, 90, "floor",
                          f"Bring {label} ({bill['short']}), already passed by the Senate, to the House floor.",
                          f"Passing the Senate text sends it straight to the President. The House version {house_bill['label']} has {support_line(house_bill)}.",
                          []))
    for seat in committee_seats(m, house_bill["house_committees"]):
        if is_chair(seat):
            out.append(action(goal, bill, 92, "markup",
                              f"Mark up {house_bill['label']} or clear {label} for the floor in {ctx.committee_name(seat['code'])}.",
                              f"The Senate already passed it. {house_bill['label']} has {support_line(house_bill)}.", []))
        break
    return out


def goal_without_bills(ctx, goal, m):
    """Appropriations and similar goals where the work is in committee rather than on one bill."""
    out = []
    codes = goal.get("committees", [])
    if goal["id"] == "appropriations-on-time":
        for seat in committee_seats(m, codes):
            if is_chair(seat):
                out.append(action(goal, None, 90, "appropriations",
                                  "Move all 12 FY2027 appropriations bills on regular order and on time.",
                                  "As chair you set the schedule. The PSC is asking for no shutdown and no year-long stopgap.", []))
            elif is_ranking(seat):
                out.append(action(goal, None, 75, "appropriations",
                                  "Negotiate bipartisan toplines so all 12 bills can move on time.",
                                  "The PSC is pushing regular order, and the ranking member's agreement is needed to get there.", []))
            else:
                out.append(action(goal, None, 50 + (10 if m["psc"] else 0), "appropriations",
                                  "Back on-time passage of all 12 appropriations bills in committee.",
                                  "You sit on Appropriations, where this goal is decided.", []))
            break
        thud = [s for s in m["subcommittees"] if s["parent"] in codes and "Transportation" in s["name"]]
        if thud:
            out.append(action(goal, None, 80 if (is_chair(thud[0]) or is_ranking(thud[0])) else 65, "appropriations",
                              "Restore surface transportation funding to FY2026 levels in the FY2027 THUD bill (highways, airports, transit).",
                              "Your THUD subcommittee seat decides this. The PSC letter flags about $10B in highway cuts, $5B for airports and $4B for transit.",
                              []))
    elif goal["id"] == "online-safety-ai":
        seats = committee_seats(m, codes)
        if seats and (m["psc"] or is_chair(seats[0]) or is_ranking(seats[0])):
            out.append(action(goal, None, 45 if m["psc"] else 40, "oversight",
                              f"Use your {ctx.committee_name(seats[0]['code'])} seat to press for US-led AI safety standards and AI incident reporting.",
                              "The PSC asked the administration to lead on AI safety standards and US-China safety coordination, and it has started an AI working group.",
                              []))
    return out


def actions_for(ctx, goal, m):
    out = []
    bills = {b["id"]: b for b in goal["resolved_bills"]}
    for bill in goal["resolved_bills"]:
        if bill["chamber"] == "house" and m["chamber"] == "house":
            companion = bills.get(bill.get("companion"))
            if companion and companion["stage"] == "passed_senate":
                out += house_side_of_senate_passed(ctx, goal, companion, bill, m)
                if m["bioguide"] in bill["supporter_ids"] or committee_seats(m, bill["house_committees"]):
                    continue
            out += house_bill_in_house(ctx, goal, bill, m)
        elif m["chamber"] == "senate":
            out += senate_side(ctx, goal, bill, m)
    out += goal_without_bills(ctx, goal, m)
    # Keep the strongest action per bill and kind.
    best = {}
    for a in out:
        key = (a["bill"], a["kind"])
        if key not in best or a["priority"] > best[key]["priority"]:
            best[key] = a
    return sorted(best.values(), key=lambda a: -a["priority"])
