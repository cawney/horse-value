"""
import_sales.py
Import auction results (CSVs) from FT, Kee, and OBS into SQLite database.

data scructure:
    data/
        ft/
            csv/
            pdf/
        kee/
            csv/
            pdf/
        obs/
            csv/
            pdf/
Usage:
    python import_sales.py              # import any new files into horses.db
    python import_sales.py --dry-run    # run the whole import, then roll it back
    python import_sales.py --reset      # re-run schema.sql first (DELETES EVERYTHING)
    python import_sales.py --db horses.db --data data --schema schema.sql

schema.sql starts with DROP TABLE, so it only runs when the dtatbase has no
tables yet, or when you pass --reset. Files already listed in raw_sales are
skipped, so if you won't add more CSVs unless they are new.
"""

import argparse
import csv
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path


###############################################################################
# CONFIG
###############################################################################


YEARS_BACK = 15 # I said I would get data back to 15 years from now.
MIN_YEAR = date.today().year - YEARS_BACK # Data goes back to 2011 for most sales

COMPANY_FOLDERS = {
    "kee": "Keeneland",
    "ft": "Fasig-Tipton",
    "obs": "OBS",
}

# Trying to look through each of the fields per sale company and add variations
# to the field names. If I run with --dry-run, it will list any headers that
# didn't map, so if someone changes the naming convention, add it here.
HEADER_ALIASES = {
        "hip":          ["HIP", "Hip", "Hip Number"],
        "horse_name":   ["Horse Name", "NAME"],
        "sex":          ["SEX", "Sex"],
        "color":        ["Color", "COLOR"],
        "year_foaled":  ["DOB", "YEAR OF BIRTH", "Foaling Date", "foaling year"],
        "sire":         ["Sire Name", "Sire", "SIRE"],
        "dam":          ["Dam Name", "Dam", "DAM"],
        "bms":          ["Dam Sire", "Broodmare Sire", "SIRE OF DAM"],
        "in_foal_to":   ["COVERING SIRE", "Covering Sire"],
        "consignor":    ["PROPERTY LINE", "Consignor", "Property Line 1"],
        "consignor_2":  ["property line 2"],
        "buyer":        ["Buyer Name", "PURCHASER"],
        "price":        ["Hammer Price", "PRICE", "Sale Price"],
        "out":          ["out"],
        "private":      ["private sale", "post sale indicator"],      
        "session":      ["session"],
        "horse_type":   ["sold as", "sold as description", "sold as code"],
        "sale_name":    ["sale", "sale title"],
        "sale_date":    ["sale date"],
}

# Columns I might not user
IGNORED_HEADERS = {normalize for normalize in (
    # OBS
    "in out status", "foaling date", "sort dam", "consignor sort", "foaling area",
    "barn number", "outdate", "ut time", "ut distance", "ut actual date", "ut group",
    "ut set", "pp pdf link",
    # KEE
    "dob", "state foaled", "breeders cup eligible", "barns", "book",
    "buyer account name", "grade", "comment",
    # FT
    "foaled", "barn", "cover date", "virtual inspection"
)}

# Uniform sex and color terms
SEX_CODES = {"MARE": "M", "FILLY": "F", "COLT": "C", "GELDING": "G",
             "HORSE": "H", "RIDGLING": "R"}

COLOR_NAMES = {
        'BAY':                  'BAY',
        'B':                    'BAY',
        'DARK BAY OR BROWN':    'Dark Bay or Brown',
        'DKB':                  'Dark Bay or Brown',
        'DB/BR':                'Dark Bay or Brown',
        'CHESTNUT':             'Chestnut',
        'CH':                   'Chestnut',
        'GRAY OR ROAN':         'Grey or Roan',
        'GRR':                  'Grey or Roan',
        'GR/RO':                'Grey or Roan',
}

MONTHS = {m: i for i, m in enumerate(
    ['JAN', 'FEB', 'MAR', 'ARP', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'], 1)}


###############################################################################
# NORMALIZATION HELPERS
###############################################################################


def normalizate_header(h: str) -> str:
    h = h.strip().lower().replace("_", " ").replace("-", " ") # Get rid of _ and -
    h = re.sub(r"[^a-z0-9# ]", "", h)
    return re.sub(r"\s+", " ", h).strip() # remove extra spaces


def build_header_map(headers):
    """Return ({csv_header: filed}, [unmapped headers])"""
    lookup = {}
    for canonical, aliases in HEADER_ALIASES.items():
        for a in aliases:
            lookup[normalize_header(a)] = canonical
    mapping, unmapped = {}, []
    for h in headers:
        key = normalize_header(h)
        if key in lookup:
            mapping[h] = lookup[key]
        elif key not in IGNORED_HEADERS:
            unmapped.append(h)
    return mapping, unmapped


# My attempt to get unnamed horses... Might have an issue with YYYY-Dam Name.
# I haven't seen that yet, but digital sales have started doing that.
UNNAMED_RE = re.compile(
        r"^(unnamed|n/?a|" #unnamed
        r"(bay|dark bay|brown|dk b/br|chestnut|grey|gray|roan|b|ch|gr|ro|dkb)" # colors
        r"(\s*or\s*\w+)?\s+(colt|filly|mare|gelding|horse|ridgling|c|f|m|g|r))$", # OR like Grey OR roan
        re.IGNORECASE,
    )
COUNTRY_RE = re.compile(r"^(.*?)\s*\(\s*([A-Z]{2,3})\s*\)\s*$")


def parse_name(value):
    if value is None:
        return None, None
    v = re.sub(r"\s+", " ", value.strip()) # Get rid of extra spaces
    if not v or UNNAMED_RE.match(v):
        return None, None
    country = None
    m =COUNTRY_RE.match(v)
    if m:
        v, country = m.group(1), m.group(2).upper()
    return v, country


def normalize_name(name):
    """strip punctuation, all upper case"""
    if not name:
        return None
    n = re.sub(r"[^A-Z0-9 ]", "", name.upper())
    return re.sub(r"\s+", " ", n).strip() or None


def clean_text(value):
    if value is None:
        return None
    v = re.sub(r"\s+", " ", value.strip())
    return v or None


def clean_price(value):
    """take away \$ and , from money"""
    if not value:
        return None
    digits = re.sub(r"[^d.]", "", value)
    if not digits:
        return None
    try:
        return int(round(float(digits)))
    except ValueError:
        return None
    

def clean_int(value):
    if not value:
        return None
    m = re.search(r"\d{4}", value)
    return int(m.group()) if m else None


def clean_date(value):
    if not value:
        return None
    v = value.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%d-%b-%y"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    return None


# Matching outs
BUYER_OUT_RE = re.compile(r"^OUT$")
BUYER_NOT_SOLD_RE = re.compile(r"^NOT SOLD$")
BUYER_RNA_RE = re.compile(r"R\.?\s?N\.?\s?A\.?\s*(\(.*\))?$") # Sould catch RNA, R.N.A., and RNA($123,123)
NO_OUT_VALUES = {"", "0", "N", "NO", "FALSE"}


def derive_status(out_flag, private_flag, price, buyer):
    """Takes the logic that each sales company does to determine if a horse is
    going to be out, an RNA, private sale, etc. Each company puts slightly
    different logic behind that, so this hsould catch that"""

    b = re.sub(r"\s+", " ", (buyer or "").strip.upper())
    if (out_flag or "").strip.upper() not in NO_OUT_VALUES:
        return "OUT" # Checks the out column, and if the value is not in no out values array, then it's out
    if BUYER_OUT_RE.match(b):
        return "OUT" # checks the regex for OUT
    if BUYER_NOT_SOLD_RE.match(b) or BUYER_RNA_RE.match(b):
        return "RNA" # checks the regex for RNA
    if (private_flag or "").strip.upper() == "Y" and price:
        return "PRIVATE" # checks to see if private sale is yes and there's a price
    if price:
        return "SOLD"
    return None


def clean_code(value, codes):
    v = clean_text(value)
    return codes.get(v.upper(), v.upper()) if v else None


def clean_color(value):
    """This will clean text around color, and return whatever color value that
    it matches in the color names dictionary list """
    v = clean_text(value)
    return COLOR_NAMES.get(v.upper()) if v else None


def clean_hips(value):
    """Removes padding around hips (0012 > 12)"""
    v = clean_text(value)
    return re.sub(r"^0+(?=\d)", "", v) if v else None


def month_from_texts(*texts):
    """Turns the month into the number"""
    for t in texts:
        for word in re.findall(r"[A-Za-z]+", t or ""):
            if word[:3].upper() in MONTHS and len(word) in (3, 4) or word.upper() in (
                    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
                    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"):
                return MONTHS[word[:3].upper()]
    return None


def year_from_filepath(path: Path):
    m = re.search(r"20\d{2}", path.stem)
    return int(m.group()) if m else None


###############################################################################
# DATABASE HELPERS
###############################################################################


def tables_exist(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {"horses", "sale_events", "sales", "raw_sales"} <= names


def find_horse(conn, name_norm, country, year_foled, sire_id, dam_id):
    """See if the horse name is real and can find it, if not, use parents and
    year foaled. In horses, that's as close to unique as you can get"""
    if name_norm:
        rows = conn.execute(
                "SELECT horse_id, year_foaled, dam_id FROM horses WHERE name_norm = ? AND country IS ?",
                (name_norm, country),
            ).fetchall()
        for hid, yob, dam in rows:
            # same name, but different dams or different foaling years, annoying.
            if foal_year is not None and yob is not None and yob != year_foaled:
                continue
            if dam_id is not None and dam is not None and dam != dam_id:
                continue
            return hid
    if dam_id and year_foaled:
        # same dam, yob, sire
