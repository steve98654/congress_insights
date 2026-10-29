"""Build data/members.json: every current member of Congress with committees, leadership roles and PSC membership.

Sources: data/sources/*.yaml from unitedstates/congress-legislators and data/psc_roster.yaml.
"""

import datetime
import re

from common import DATA, SOURCES, load_yaml, write_json

PARTY = {"Republican": "R", "Democrat": "D", "Independent": "I"}
# Floor leaders and whips; other leadership titles are kept but carry less weight.
FLOOR_LEADERSHIP = {
    "Speaker of the House", "House Majority Leader", "House Minority Leader", "House Majority Whip",
    "House Minority Whip", "Senate Majority Leader", "Senate Minority Leader", "Senate Majority Whip",
    "Senate Minority Whip",
}


def slugify(text):
    text = text.lower().replace("ñ", "n").replace("é", "e").replace("á", "a").replace("ó", "o").replace("í", "i")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def district_key(state, district):
    return f"{state}-{int(district or 0):02d}"


def main():
    legislators = load_yaml(SOURCES / "legislators-current.yaml")
    committees = load_yaml(SOURCES / "committees-current.yaml")
    membership = load_yaml(SOURCES / "committee-membership-current.yaml")
    social = {s["id"]["bioguide"]: s.get("social", {}) for s in load_yaml(SOURCES / "legislators-social-media.yaml")}
    roster = load_yaml(DATA / "psc_roster.yaml")

    committee_names, parent_of = {}, {}
    for c in committees:
        committee_names[c["thomas_id"]] = c["name"]
        for sub in c.get("subcommittees", []):
            code = c["thomas_id"] + sub["thomas_id"]
            committee_names[code] = f"{c['name']}: {sub['name']}"
            parent_of[code] = c["thomas_id"]

    assignments = {}
    for code, seats in membership.items():
        for seat in seats:
            entry = {
                "code": code,
                "name": committee_names.get(code, code),
                "rank": seat.get("rank"),
                "side": seat.get("party"),
            }
            if seat.get("title"):
                entry["title"] = seat["title"]
            assignments.setdefault(seat["bioguide"], []).append(entry)

    by_district = {}
    for p in legislators:
        t = p["terms"][-1]
        if t["type"] == "rep":
            by_district[district_key(t["state"], t.get("district"))] = p["id"]["bioguide"]
    psc = {}
    for m in roster["members"]:
        state, dist = m["district"].split("-")
        bio = by_district.get(district_key(state, dist))
        if bio:
            psc[bio] = m.get("role", "Member")
        else:
            print(f"PSC roster: no current member for {m['district']} ({m['name']})")

    members, seen = [], set()
    today = datetime.date.today()
    for p in legislators:
        bio = p["id"]["bioguide"]
        t = p["terms"][-1]
        chamber = "senate" if t["type"] == "sen" else "house"
        party = PARTY.get(t["party"], t["party"][:1])
        name = p["name"].get("official_full") or f"{p['name']['first']} {p['name']['last']}"
        district = t.get("district") if chamber == "house" else None
        seat = f"{t['state']}-{int(district):02d}" if chamber == "house" else t["state"]
        slug = slugify(f"{p['name']['last']}-{seat}")
        if slug in seen:
            slug = f"{slug}-{bio.lower()}"
        seen.add(slug)

        own = assignments.get(bio, [])
        full = [c for c in own if c["code"] not in parent_of]
        subs = [dict(c, parent=parent_of[c["code"]]) for c in own if c["code"] in parent_of]
        # Party side in the chamber, for independents who caucus with a party.
        side = next((c["side"] for c in full if c.get("side")), None)
        caucus = party
        if party == "I":
            majority = "R"
            caucus = majority if side == "majority" else "D"

        leadership = [r["title"] for r in p.get("leadership_roles", [])
                      if not r.get("end") and r.get("chamber") == chamber]
        first_start = min(term["start"] for term in p["terms"] if term["type"] == t["type"])
        years = round((today - datetime.date.fromisoformat(first_start)).days / 365.25, 1)

        members.append({
            "bioguide": bio,
            "slug": slug,
            "name": name,
            "first": p["name"].get("first"),
            "last": p["name"]["last"],
            "chamber": chamber,
            "state": t["state"],
            "district": district,
            "seat": seat,
            "party": party,
            "caucus": caucus,
            "label": f"{party}-{seat}",
            "title": "Sen." if chamber == "senate" else ("Del." if t["state"] in {"DC", "GU", "VI", "AS", "MP"} else
                                                         "Res. Comm." if t["state"] == "PR" else "Rep."),
            "voting": not (chamber == "house" and t["state"] in {"DC", "GU", "VI", "AS", "MP", "PR"}),
            "first_served": first_start,
            "years_in_chamber": years,
            "term_end": t["end"],
            "senate_class": t.get("class"),
            "leadership": leadership,
            "floor_leader": any(r in FLOOR_LEADERSHIP for r in leadership),
            "psc": psc.get(bio),
            "committees": sorted(full, key=lambda c: c["name"]),
            "subcommittees": sorted(subs, key=lambda c: c["name"]),
            "ids": {"lis": p["id"].get("lis"), "govtrack": p["id"].get("govtrack"),
                    "opensecrets": p["id"].get("opensecrets")},
            "contact": {"url": t.get("url"), "phone": t.get("phone"), "office": t.get("address"),
                        "x": social.get(bio, {}).get("twitter")},
        })
    members.sort(key=lambda m: (m["chamber"] != "senate", m["state"], m["district"] or 0, m["last"]))
    write_json(DATA / "members.json", members)
    print(f"members: {len(members)} ({sum(m['chamber'] == 'senate' for m in members)} senators), "
          f"{len(psc)} PSC members matched")


if __name__ == "__main__":
    main()
