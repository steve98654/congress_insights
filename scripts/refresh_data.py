"""Refresh the data behind the briefs.

  python scripts/refresh_data.py legislators   members, committees and assignments (unitedstates/congress-legislators)
  python scripts/refresh_data.py bills         sponsor, cosponsors, committees, actions and votes for every goal bill (govinfo BILLSTATUS)
  python scripts/refresh_data.py votes         member-level roll calls named by goals (senate.gov / clerk.house.gov)
  python scripts/refresh_data.py seed          rebuild data/bills and data/votes from the text snapshots in data/seed
  python scripts/refresh_data.py all           legislators, bills and votes

None of these sources needs an API key. A source that can't be reached is reported and its existing
data is kept, so a partial refresh never wipes good data.
"""

import argparse
import datetime
import re
import sys
import xml.etree.ElementTree as ET

import requests

from common import (BILLS, SEED, SOURCES, VOTES, bill_chamber, govinfo_url, load_goals, load_json,
                    write_json)

LEGISLATOR_FILES = [
    "legislators-current.yaml",
    "committees-current.yaml",
    "committee-membership-current.yaml",
    "legislators-social-media.yaml",
]
LEGISLATOR_BASE = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
HEADERS = {"User-Agent": "congress-insights/1.0 (research; github.com/steve98654/congress_insights)"}
TODAY = datetime.date.today().isoformat()


def fetch(url, timeout=60):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


# ---------------------------------------------------------------- legislators

def refresh_legislators():
    ok = True
    for name in LEGISLATOR_FILES:
        try:
            body = fetch(LEGISLATOR_BASE + name).content
        except requests.RequestException as e:
            print(f"legislators: could not fetch {name}: {e}", file=sys.stderr)
            ok = False
            continue
        (SOURCES / name).write_bytes(body)
        print(f"legislators: {name} ({len(body):,} bytes)")
    return ok


# ---------------------------------------------------------------- bills

def derive_status(texts, bill_id):
    """Best-effort stage from action and vote texts, strongest first."""
    blob = " | ".join(t for t in texts if t).lower()
    if "became public law" in blob or "signed by president" in blob:
        return "enacted"
    own = bill_chamber(bill_id)
    passed_house = bool(re.search(r"(passed|agreed to) in (the )?house|on passage.*house.*(passed|agreed)|"
                                  r"house roll \d+.*(pass).*agreed|motion to suspend the rules and pass.*agreed", blob))
    passed_senate = bool(re.search(r"passed (the )?senate|passed senate|senate.*passed with|"
                                   r"received in the house|held at the desk", blob)) and own == "senate"
    if own == "house" and passed_house:
        return "passed_house"
    if own == "senate" and passed_senate:
        return "passed_senate"
    if "ordered to be reported" in blob or "reported by" in blob or "placed on the union calendar" in blob:
        return "reported"
    return "in_committee"


def _text(el, path, default=""):
    found = el.find(path)
    return (found.text or "").strip() if found is not None and found.text else default


def parse_billstatus(xml_bytes, bill_id):
    root = ET.fromstring(xml_bytes)
    bill = root.find("bill")
    sponsor_el = bill.find("sponsors/item")
    sponsor = None
    if sponsor_el is not None:
        sponsor = {
            "bioguide": _text(sponsor_el, "bioguideId"),
            "name": _text(sponsor_el, "fullName"),
            "party": _text(sponsor_el, "party"),
            "state": _text(sponsor_el, "state"),
        }
    cosponsors = []
    for item in bill.findall("cosponsors/item"):
        if _text(item, "sponsorshipWithdrawnDate"):
            continue
        cosponsors.append({
            "bioguide": _text(item, "bioguideId"),
            "party": _text(item, "party"),
            "state": _text(item, "state"),
            "date": _text(item, "sponsorshipDate"),
        })
    committees = sorted({_text(c, "systemCode")[:4].upper() for c in bill.findall("committees/item")
                         if _text(c, "systemCode")})
    actions, votes = [], []
    for a in bill.findall("actions/item"):
        actions.append({"date": _text(a, "actionDate"), "text": _text(a, "text")})
        for rv in a.findall("recordedVotes/recordedVote"):
            votes.append({
                "chamber": _text(rv, "chamber"),
                "roll": _text(rv, "rollNumber"),
                "date": _text(rv, "date")[:10],
                "url": _text(rv, "url"),
                "text": _text(a, "text"),
            })
    latest = {"date": _text(bill, "latestAction/actionDate"), "text": _text(bill, "latestAction/text")}
    texts = [latest["text"]] + [a["text"] for a in actions]
    return {
        "id": bill_id,
        "title": _text(bill, "title"),
        "sponsor": sponsor,
        "introduced": _text(bill, "introducedDate"),
        "committees": committees,
        "latest": latest,
        "votes": votes,
        "actions": actions[:40],
        "cosponsors": cosponsors,
        "cosponsors_complete": True,
        "status": derive_status(texts, bill_id),
        "source_url": govinfo_url(bill_id),
        "fetched": TODAY,
        "fetched_via": "govinfo BILLSTATUS XML",
    }


def goal_bill_ids():
    ids = []
    for g in load_goals():
        for b in g["bills"]:
            if b["id"] not in ids:
                ids.append(b["id"])
    return ids


def refresh_bills():
    ok = True
    for bill_id in goal_bill_ids():
        try:
            parsed = parse_billstatus(fetch(govinfo_url(bill_id)).content, bill_id)
        except (requests.RequestException, ET.ParseError, AttributeError) as e:
            print(f"bills: kept existing data for {bill_id}: {e}", file=sys.stderr)
            ok = False
            continue
        write_json(BILLS / f"{bill_id}.json", parsed)
        print(f"bills: {bill_id} {parsed['status']} with {len(parsed['cosponsors'])} cosponsors")
    return ok


# ---------------------------------------------------------------- votes

def vote_url(key):
    """senate_vote_119_2_254 -> senate.gov XML; house_vote_2026_312 -> clerk.house.gov XML."""
    m = re.fullmatch(r"senate_vote_(\d+)_(\d)_(\d+)", key)
    if m:
        congress, session, roll = m.groups()
        return (f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/"
                f"vote_{congress}_{session}_{int(roll):05d}.xml")
    m = re.fullmatch(r"house_vote_(\d{4})_(\d+)", key)
    if m:
        year, roll = m.groups()
        return f"https://clerk.house.gov/evs/{year}/roll{int(roll):03d}.xml"
    raise ValueError(f"unrecognized vote key {key!r}")


def parse_senate_vote(xml_bytes, key):
    root = ET.fromstring(xml_bytes)
    members = [{
        "lis": _text(m, "lis_member_id"),
        "last": _text(m, "last_name"),
        "party": _text(m, "party"),
        "state": _text(m, "state"),
        "vote": _text(m, "vote_cast"),
    } for m in root.findall("members/member")]
    return {
        "key": key,
        "chamber": "senate",
        "question": _text(root, "vote_question_text") or _text(root, "question"),
        "date": _text(root, "vote_date"),
        "result": _text(root, "vote_result_text"),
        "members": members,
        "source_url": vote_url(key),
        "fetched": TODAY,
    }


def parse_house_vote(xml_bytes, key):
    root = ET.fromstring(xml_bytes)
    meta = root.find("vote-metadata")
    members = []
    for rec in root.findall("vote-data/recorded-vote"):
        leg = rec.find("legislator")
        members.append({
            "bioguide": leg.get("name-id"),
            "last": (leg.text or "").strip(),
            "party": leg.get("party"),
            "state": leg.get("state"),
            "vote": _text(rec, "vote"),
        })
    return {
        "key": key,
        "chamber": "house",
        "question": _text(meta, "vote-question"),
        "date": _text(meta, "action-date"),
        "result": _text(meta, "vote-result"),
        "members": members,
        "source_url": vote_url(key),
        "fetched": TODAY,
    }


def goal_vote_keys():
    keys = []
    for g in load_goals():
        for b in g["bills"]:
            for k in ("senate_vote", "house_vote"):
                if b.get(k) and b[k] not in keys:
                    keys.append(b[k])
    return keys


def refresh_votes():
    ok = True
    for key in goal_vote_keys():
        try:
            body = fetch(vote_url(key)).content
            parsed = parse_senate_vote(body, key) if key.startswith("senate") else parse_house_vote(body, key)
        except (requests.RequestException, ET.ParseError, AttributeError) as e:
            print(f"votes: kept existing data for {key}: {e}", file=sys.stderr)
            ok = False
            continue
        write_json(VOTES / f"{key}.json", parsed)
        print(f"votes: {key} {parsed['result']}")
    return ok


# ---------------------------------------------------------------- seed snapshots

def parse_seed_bill(path):
    """Text snapshots written when the bulk sources were not reachable (see data/seed/README.md)."""
    bill_id = path.stem
    head, cosponsors, partial = {}, [], False
    in_list = False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if in_list:
            parts = line.split("|")
            cosponsors.append({"bioguide": parts[0], "party": parts[1] if len(parts) > 1 else "",
                               "state": parts[2] if len(parts) > 2 else "",
                               "date": parts[3] if len(parts) > 3 else ""})
            continue
        if line.startswith("COSPONSORS_PARTIAL"):
            partial = True
        elif line.startswith("COSPONSORS"):
            in_list = True
        else:
            key, _, value = line.partition(":")
            head[key.strip()] = value.strip()
    sp = head["SPONSOR"].split("|")
    latest_date, _, latest_text = head.get("LATEST", "").partition("|")
    votes_text = head.get("VOTES", "none")
    committees = sorted({c.upper() for c in re.findall(r"\b([hsj][a-z]{3})\d{2}\b", head.get("COMMITTEES", ""))})
    return {
        "id": bill_id,
        "title": head.get("TITLE", ""),
        "sponsor": {"bioguide": sp[0], "name": sp[1], "party": sp[2], "state": sp[3]},
        "introduced": head.get("INTRODUCED", ""),
        "committees": committees,
        "latest": {"date": latest_date, "text": latest_text},
        "votes": [] if votes_text.lower() == "none" else [{"text": v.strip()} for v in votes_text.split(";")],
        "actions": [],
        "cosponsors": cosponsors,
        "cosponsors_complete": not partial,
        "status": derive_status([latest_text, votes_text], bill_id),
        "source_url": govinfo_url(bill_id),
        "fetched": "2026-10-29",
        "fetched_via": "snapshot of govinfo BILLSTATUS (data/seed)",
    }


def parse_seed_vote(path):
    head, members, in_list = {}, [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if in_list:
            lis, last, party, state, vote = line.split("|")
            members.append({"lis": lis, "last": last, "party": party, "state": state, "vote": vote})
        elif line.startswith("VOTES"):
            in_list = True
        else:
            key, _, value = line.partition(":")
            head[key.strip()] = value.strip()
    return {
        "key": path.stem,
        "chamber": "senate" if path.stem.startswith("senate") else "house",
        "question": head.get("QUESTION", ""),
        "date": head.get("DATE", ""),
        "result": head.get("RESULT", ""),
        "members": members,
        "source_url": head.get("SOURCE", ""),
        "fetched": "2026-10-29",
    }


def rebuild_from_seed():
    for path in sorted(SEED.glob("*.txt")):
        if "_vote_" in path.stem:
            write_json(VOTES / f"{path.stem}.json", parse_seed_vote(path))
        elif load_json(BILLS / f"{path.stem}.json", {}).get("fetched_via", "").startswith("govinfo"):
            print(f"seed: {path.stem} already has live data, skipped")
        else:
            write_json(BILLS / f"{path.stem}.json", parse_seed_bill(path))
    print("seed: done")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["legislators", "bills", "votes", "seed", "all"])
    args = ap.parse_args()
    steps = {"legislators": [refresh_legislators], "bills": [refresh_bills], "votes": [refresh_votes],
             "seed": [rebuild_from_seed], "all": [refresh_legislators, refresh_bills, refresh_votes]}[args.what]
    results = [step() for step in steps]
    if not all(results):
        print("Some sources could not be refreshed; existing data was kept for those.", file=sys.stderr)


if __name__ == "__main__":
    main()
