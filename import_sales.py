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


def normalize_header(h: str) -> str:
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
    """take away $ and , from money"""
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

    b = re.sub(r"\s+", " ", (buyer or "").strip().upper())
    if (out_flag or "").strip().upper() not in NO_OUT_VALUES:
        return "OUT" # Checks the out column, and if the value is not in no out values array, then it's out
    if BUYER_OUT_RE.match(b):
        return "OUT" # checks the regex for OUT
    if BUYER_NOT_SOLD_RE.match(b) or BUYER_RNA_RE.match(b):
        return "RNA" # checks the regex for RNA
    if (private_flag or "").strip().upper() == "Y" and price:
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


def clean_hip(value):
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


def find_horse(conn, name_norm, country, year_foaled, sire_id, dam_id):
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
        # same dam, yob, sire means same horse
        row = conn.execute(
            """
            SELECT horse_id FROM horses
            WHERE dam_id = ? AND year_foaled = ?
                AND (sire_id = ? OR side_id IS NULL OR ? IS NULL)
            ORDER BY (name_norm IS ?) DESC
            LIMIT 1
            """,
            (dam_id, year_foled, sire_id, name_norm),
        ).fetchone()
        if row:
            return row[0]
    return None


def upsert_horse(conn, stats, name, country, *, year_foaled=None, sex=None,
                 color=None, sire_id=None, dam_id=None, is_stallion=0):
    """Returns horse_id, and creates horse if needed. On match, fills any
    colums the stored record missing, never overwrites"""
    name_norm = normalize_name(name)
    if not name_norm and not dam_id:
        return None # Can't search horse w/o those
    
    hid = find_horse(conn, name_norm, country, year_foaled, sire_id, dam_id)
    if hid is None:
        cur = conn.execute(
            """INSERT INTO horses (name, name_norm, country, year_foaled, sex,
                                    color, is_stallion, sire_id, dam_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, name_norm, country, year_foaled, sex, color, is_stallion,
                 sire_id, dam_id)
        )
        stats["horses_new"] += 1
        return cur.lastrowid
    
    old = conn.execute("SELECT name, name_norm FROM horses WHERE horse_id = ?", (hid,)).fetchone()
    if name_norm and old[1] and old[1] != name_norm: # If there is a name_norm, and old[1] is not None, and old[1] is not name_norm
        stats["name_conflicts"].append(f"{old[0]} / {name} (horse_id {hid}) -- kept {old[0]}")

    conn.execute(
        # FT is in caps, don't want all caps
        """
        UPDATE horses SET
            name        = CASE WHEN name IS NULL OR (name = UPPER(name) AND ?1 <> UPPER(?1))
                                THEN COALESCE(?1, name) ELSE name END,
            name_norm   = COALESCE(name_norm, ?),
            country     = COALESCE(country, ?),
            year_foaled = COALESCE(year_foaled, ?),
            sex         = COALESCE(sex, ?),
            color       = COALESCE(color, ?),
            sire_id     = COALESCE(sire_id, ?),
            dam_id      = COALESCE(dam_id, ?),
            is_stallion = MAX(is_stallion, ?)
        WHERE horse_id = ?
        """,
        (name, name_norm, country, year_foaled, sex, color, sire_id, dam_id, is_stallion, hid),
    )
    return hid


def get_sale_event(conn, company, sale_name, start_date):
    row = conn.execute(
        "SELECT sale_id FROM sale_events WHERE company = ? AND sale_name = ? AND start_date IS ?",
        (company, sale_name, start_date),
    ).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO sale_events (company, sale_name, start_date) VALUES (?, ?, ?)",
        (company, sale_name, start_date),
    )
    return cur.lastrowid


###############################################################################
# IMPORT
###############################################################################


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)
    

def transform_row(raw, header_map, path):
    r = {}
    for k, v in raw.items():
        field = header_map.get(k)
        if field and not (r.get(field) or "").strip():
            r[field] = v

    price = clean_price(r.get("price"))
    status = derive_status(r.get("out"), r.get("private"), price, r.get("buyer"))
    buyer = clean_text(r.get("buyer"))
    if status not in ("SOLD", "PRIVATE"):
        price = None
        buyer = None

    consignor = " ".join(filter(None, (clean_text(r.get("consignor")),
                                       clean_text(r.get("consignor_2"))))) or None
    return {
        "sale_name":   clean_text(r.get("sale_name")) or path.stem,
        # FT uses SESSION for sale date...
        "sale_date":   clean_date(r.get("sale_date")) or clean_date(r.get("session")),
        "hip":         clean_hip(r.get("hip")),
        "horse":       parse_name(r.get("horse_name")),
        "sex":         clean_code(r.get("sex"), SEX_CODES),
        "color":       clean_color(r.get("color")),
        "color_raw":   clean_text(r.get("color")),
        "year_foaled": clean_int(r.get("year_foaled")),
        "sire":        parse_name(r.get("sire")),
        "dam":         parse_name(r.get("dam")),
        "damsire":     parse_name(r.get("damsire")),
        "in_foal_to":  parse_name(r.get("in_foal_to")),
        "session":     clean_text(r.get("session")),
        "horse_type":  clean_text(r.get("horse_type")),
        "consignor":   consignor,
        "buyer":       buyer,
        "price":       price,
        "status":      status,
    }


def validate(row):
    if not row["hip"]:
        return "missing hip"
    if not row["dam"][0]:
        return "missing dam"
    if not row["status"]:
        return "no price, now out, no RNA marker in buyer. Can't tell what happened"
    return None


def import_row(conn, row, sale_id, source_file, stats):
    """Write one sale: stallions, dam, the horse itself, then the sales row."""
    damsire_id = upsert_horse(conn, stats, *row["damsire"], is_stallion=1)
    sire_id = upsert_horse(conn, stats, *row["sire"], is_stallion=1)
    dam_id = upsert_horse(conn, stats, *row["dam"], sire_id=damsire_id)
    horse_id = upsert_horse(
        conn, stats, *row["horse"],
        year_foaled=row["year_foaled"], sex=row["sex"], color=row["color"],
        sire_id=sire_id, dam_id=dam_id,
    )
    in_foal_to_id = upsert_horse(conn, stats, *row["in_foal_to"], is_stallion=1)

    conn.execute(
        """INSERT INTO sales (sale_id, hip, horse_id, session, horse_type, status,
                            price, consignor, buyer, in_foal_to_id, source_file)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sale_id, row["hip"], horse_id, row["session"], row["horse_type"], row["status"],
        row["price"], row["consignor"], row["buyer"], in_foal_to_id, source_file),
    )

 
def import_file(conn, path, company):
    stats = {"read": 0, "inserted": 0, "duplicate": 0, "horses_new": 0, "skipped": {},
             "name_conflicts": [], "bad_colors": []}
    source_file = path.name  # schema: file name, not path
 
    def skip(reason, n=1):
        stats["skipped"][reason] = stats["skipped"].get(reason, 0) + n
 
    if conn.execute(
        "SELECT 1 FROM raw_sales WHERE source_file = ? AND company = ?", (source_file, company)
    ).fetchone():
        stats["already_imported"] = True
        return stats, []
 
    headers, raw_rows = read_csv(path)
    stats["read"] = len(raw_rows)
    header_map, unmapped = build_header_map(headers)
 
    missing = {"hip", "dam"} - set(header_map.values())
    if missing:
        print(f"  !! {path.name}: no column found for {sorted(missing)} -- file skipped")
        print(f"     headers were: {headers}")
        skip("missing required column", len(raw_rows))
        return stats, unmapped
 
    rows = [transform_row(r, header_map, path) for r in raw_rows]
 
    # One file can hold more than one sale; group by sale name.
    groups = {}
    for row in rows:
        groups.setdefault(row["sale_name"], []).append(row)
 
    file_year = year_from_filepath(path)
    for sale_name, group in groups.items():
        dates = [r["sale_date"] for r in group if r["sale_date"]]
        if dates:
            start_date = min(dates)
        elif file_year:
            # Kee "NOV 2021" -> 2021-11-01; no month anywhere (OBS) -> January 1
            month = month_from_texts(sale_name, path.stem) or 1
            start_date = f"{file_year}-{month:02d}-01"
            print(f"  ~~ {path.name}: no sale dates in the file, start_date estimated as "
                  f"{start_date} from the sale/file name")
        else:
            skip("no sale date (add a date column or put the year in the file name)", len(group))
            continue
 
        if int(start_date[:4]) < MIN_YEAR:
            skip(f"sale older than {MIN_YEAR}", len(group))
            continue
 
        sale_id = get_sale_event(conn, company, sale_name, start_date)
 
        for row in group:
            if row["color_raw"] and not row["color"]:
                who = row["horse"][0] or f"{row['dam'][0] or '?'} foal"
                stats["bad_colors"].append(
                    f"hip {row['hip']} ({who}): color {row['color_raw']!r} is not Bay, "
                    f"Dark Bay or Brown, Chestnut or Grey or Roan -- color left empty")
            reason = validate(row)
            if reason:
                skip(reason)
                continue
            if conn.execute(
                "SELECT 1 FROM sales WHERE sale_id = ? AND hip = ?", (sale_id, row["hip"])
            ).fetchone():
                stats["duplicate"] += 1
                continue
 
            conn.execute("SAVEPOINT row")
            try:
                import_row(conn, row, sale_id, source_file, stats)
            except sqlite3.IntegrityError as e:
                conn.execute("ROLLBACK TO row")
                skip(f"database rejected row: {e}")
            else:
                stats["inserted"] += 1
            conn.execute("RELEASE row")
 
    conn.execute("INSERT INTO raw_sales (source_file, company) VALUES (?, ?)",
                 (source_file, company))
    return stats, unmapped
 
 
def main():
    ap = argparse.ArgumentParser(description="Import horse sale CSVs into SQLite.")
    ap.add_argument("--db", default="horses.db")
    ap.add_argument("--data", default="data")
    ap.add_argument("--schema", default="schema.sql")
    ap.add_argument("--reset", action="store_true",
                    help="run schema.sql first; its DROP TABLEs delete all existing data")
    ap.add_argument("--dry-run", action="store_true",
                    help="run the full import, then roll everything back")
    args = ap.parse_args()
 
    data_dir = Path(args.data)
    if not data_dir.is_dir():
        sys.exit(f"Data folder not found: {data_dir}")
 
    conn = sqlite3.connect(args.db, isolation_level=None)  # transactions managed below
 
    if args.reset or not tables_exist(conn):
        schema_path = Path(args.schema)
        if not schema_path.is_file():
            sys.exit(f"Schema file not found: {schema_path}")
        print(f"Running {schema_path} ({'reset requested' if args.reset else 'new database'})")
        conn.executescript(schema_path.read_text())
 
    conn.execute("PRAGMA foreign_keys = ON")  # per connection; must be set here too
 
    all_unmapped = {}
    totals = {"read": 0, "inserted": 0, "duplicate": 0, "skipped": 0, "horses_new": 0}
 
    if args.dry_run:
        conn.execute("BEGIN")
 
    for folder, company in COMPANY_FOLDERS.items():
        for path in sorted((data_dir / folder).glob("*.csv")):
            conn.execute("SAVEPOINT file" if args.dry_run else "BEGIN")
            try:
                stats, unmapped = import_file(conn, path, company)
            except Exception as e:
                conn.execute("ROLLBACK TO file" if args.dry_run else "ROLLBACK")
                if args.dry_run:
                    conn.execute("RELEASE file")
                print(f"{company:4} {path.name:40} FAILED, nothing from this file kept: {e}")
                continue
            conn.execute("RELEASE file" if args.dry_run else "COMMIT")
 
            if stats.get("already_imported"):
                print(f"{company:4} {path.name:40} already imported, skipped")
                continue
 
            skipped = sum(stats["skipped"].values())
            print(f"{company:4} {path.name:40} read {stats['read']:>5}  "
                  f"in {stats['inserted']:>5}  dup {stats['duplicate']:>4}  "
                  f"skip {skipped:>4}  new horses {stats['horses_new']:>5}")
            for reason, n in stats["skipped"].items():
                print(f"    skipped {n:>4}: {reason}")
            for w in stats["bad_colors"]:
                print(f"    WARNING {w}")
            for c in stats["name_conflicts"]:
                print(f"    same parents + foal year, different name: {c}")
            for h in unmapped:
                all_unmapped.setdefault(h, set()).add(company)
            for k in ("read", "inserted", "duplicate", "horses_new"):
                totals[k] += stats[k]
            totals["skipped"] += skipped
 
    if args.dry_run:
        conn.execute("ROLLBACK")
    conn.close()
 
    print("\nTOTALS:", totals, "(dry run, nothing written)" if args.dry_run else "")
    if all_unmapped:
        print("\nUnmapped headers (add to HEADER_ALIASES if you need them):")
        for h, cos in sorted(all_unmapped.items()):
            print(f"  {h!r:30} seen in {', '.join(sorted(cos))}")
 
 
if __name__ == "__main__":
    main()   