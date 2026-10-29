"""Shared paths and loaders for the Congress Insights scripts."""

import json
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCES = DATA / "sources"
BILLS = DATA / "bills"
VOTES = DATA / "votes"
SEED = DATA / "seed"
GOALS = ROOT / "goals"
BRIEFS = ROOT / "briefs"
CONGRESS = 119

BILL_TYPES = {
    # id prefix: (govinfo/congress.gov type, congress.gov url segment, chamber)
    "hconres": ("hconres", "house-concurrent-resolution", "house"),
    "hjres": ("hjres", "house-joint-resolution", "house"),
    "hres": ("hres", "house-resolution", "house"),
    "hr": ("hr", "house-bill", "house"),
    "sconres": ("sconres", "senate-concurrent-resolution", "senate"),
    "sjres": ("sjres", "senate-joint-resolution", "senate"),
    "sres": ("sres", "senate-resolution", "senate"),
    "s": ("s", "senate-bill", "senate"),
}

LABELS = {"hr": "H.R.", "hjres": "H.J.Res.", "hres": "H.Res.", "hconres": "H.Con.Res.",
          "s": "S.", "sjres": "S.J.Res.", "sres": "S.Res.", "sconres": "S.Con.Res."}


def split_bill_id(bill_id):
    """'hr9340' -> ('hr', '9340'). Longest prefix wins so 'hjres4' is not read as 'h' + 'jres4'."""
    for prefix in sorted(BILL_TYPES, key=len, reverse=True):
        rest = bill_id[len(prefix):]
        if bill_id.startswith(prefix) and rest.isdigit():
            return prefix, rest
    raise ValueError(f"unrecognized bill id {bill_id!r}")


def bill_label(bill_id):
    prefix, num = split_bill_id(bill_id)
    return f"{LABELS[prefix]} {num}"


def bill_chamber(bill_id):
    return BILL_TYPES[split_bill_id(bill_id)[0]][2]


def bill_url(bill_id, congress=CONGRESS):
    prefix, num = split_bill_id(bill_id)
    return f"https://www.congress.gov/bill/{congress}th-congress/{BILL_TYPES[prefix][1]}/{num}"


def govinfo_url(bill_id, congress=CONGRESS):
    prefix, _ = split_bill_id(bill_id)
    return f"https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{prefix}/BILLSTATUS-{congress}{bill_id}.xml"


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path, default=None):
    path = pathlib.Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


def load_goals():
    goals = []
    for path in sorted(GOALS.glob("*.yaml")):
        g = load_yaml(path)
        g.setdefault("bills", [])
        g.setdefault("unnumbered", [])
        g.setdefault("committees", [])
        goals.append(g)
    return goals
