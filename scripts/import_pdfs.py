# My goal is to import the PDFs and build out the database with the three cross
# information from this. It will add to the size of database file, but worth it.
#

import re
import sqlite3
from pathlib import Path
import pymupdf  # pyright: ignore[reportMissingImports]
from import_sales import normalize_name, parse_name # use same normalization from import_sales

KEE_PDF_PATH   = Path("../data/kee/pdf/")
PDF_FILE       = "../data/kee/pdf/jan-2011.pdf"
THREE_CROSS    = "texttest.txt"
LABELED_FILE   = "regextest.txt"
DB_FILE        = "../docs/horses.db"
PEDIGREE_LINES = 16


###############################################################################
# Regex
# #############################################################################


sire_line = re.compile(r"^By [A-Z .’'()-]+ \(\d{4}\)", re.MULTILINE)
name_line = re.compile(r"^(?:One Share in )?[A-Z][A-Z().' -]+$")
unnamed = re.compile(r"^(BAY|DARK BAY OR BROWN|GRAY OR ROAN|BLACK|GRAY|ROAN|WHITE|CHESTNUT)\s+"
                     r"(COLT|FILLY|GELDING|RIDGLING|HORSE|MARE)")
# country_re = re.compile(r"(.*?)\s*\(([A-Z]{2,3})\)$")
page_line = re.compile(r"^--- PAGE (\d+) ---$")
leaders = re.compile(r"\s*\.{2,}\s*$")
any_year = re.compile(r"\d{4}")
year_only = re.compile(r"^\((\d{4})\)\s*$")

###############################################################################
# Text Extraction and labeling
# #############################################################################


# PDF to text
def extract_3cross(pdf_path, out_path):
    with pymupdf.open(pdf_path) as pdf, open(out_path, "w", encoding="utf-8") as out:
        for i, page in enumerate(pdf, start=1):
            text = page.get_text()
            match = sire_line.search(text)
            if match:
                out.write(f"--- PAGE {i} ---\n")
                out.write(text[:match.start()].rstrip() + "\n")


# One dict per horse pedigree
# Text to labeled text
def parse_horse(in_path):
    with open(in_path, "r", encoding="utf-8") as text:
       lines = [l.strip() for l in text if l.strip()]

    page = None
    found_name = False

    for i, line in enumerate(lines):
        m = page_line.match(line)
        if m:
            if page is not None and not found_name:
                print(f"PAGE {page}: no name line found\n\n")
            page = int(m[1])
            found_name = False
            continue

        if found_name:
            continue

        # if name line doesn't match and i + 15 is less than length of lines
        # if not name_line.match(line) and i + 16 < len(lines):
        #     continue
        if not name_line.match(line):
            continue

        found_name = True

        # FIXING SHORT PEDIGREE BLOCKS. This would mess up horse's ancestors
        block = lines[i + 1:i + 1 + PEDIGREE_LINES]
        if len(block) < PEDIGREE_LINES or any(m for l in block):
            print(f"PAGE {page}: pedigree block too short, skipping\n "
                + "\n ".join(lines[i:i + 1 + PEDIGREE_LINES]))
            continue

        def at(offset):
            return leaders.sub("", lines[i + offset])

        y = any_year.search(at(1))
        if y:
            yob = int(y[0])
        else:
            yob = None
        # name = line
        description = at(1)


        sire_sire_sire = at(2)
        sire_sire_dam  = at(3)
        sire_dam_sire  = at(4)
        sire_dam_dam   = at(5)
        dam_sire_sire  = at(6)
        dam_sire_dam   = at(7)
        dam_dam_sire   = at(8)
        dam_dam_dam    = at(9)

        sire_sire      = at(10)
        sire_dam       = at(11)
        dam_sire       = at(12)
        dam_dam        = at(13)

        sire           = at(14)
        dam            = at(15)
        m = year_only.match(at(16))
        dam_yob        = int(m[1]) if m else None

        # FIX: NO YEAR MEANS NO DESCRIPTION LINE AND THE ANCESTORS ARE SHIFTING
        def norm(n):
            return normalize_name(parse_name(n)[0])
        pairs = [(sire_sire, sire_sire_sire), (sire_sire, sire_sire_dam),
            (sire_dam, sire_dam_sire), (sire_dam, sire_dam_dam),
            (dam_sire, dam_sire_sire), (dam_sire, dam_sire_dam),
            (dam_dam, dam_dam_sire), (dam_dam, dam_dam_dam),
            (sire, sire_sire), (sire, sire_dam), (dam, dam_sire), (dam, dam_dam)]
        if yob is None or any(norm(c) and norm(c) == norm(p) for c, p in pairs):
            print(f"PAGE {page}: layout looks wrong, skipping\n\n".join(lines[i:i + 1 + PEDIGREE_LINES]))
            continue

        horse = {
            "page":           page,
            "name":           line,
            "description":    description,
            "yob":            yob,
            "sire_sire_sire": sire_sire_sire,
            "sire_sire_dam":  sire_sire_dam,
            "sire_dam_sire":  sire_dam_sire,
            "sire_dam_dam":   sire_dam_dam,
            "dam_sire_sire":  dam_sire_sire,
            "dam_sire_dam":   dam_sire_dam,
            "dam_dam_sire":   dam_dam_sire,
            "dam_dam_dam":    dam_dam_dam,
            "sire_sire":      sire_sire,
            "sire_dam":       sire_dam,
            "dam_sire":       dam_sire,
            "dam_dam":        dam_dam,
            "sire":           sire,
            "dam":            dam,
            "dam_yob":        dam_yob,
        }
        yield horse


# Write Labeled horses
def write_review(horses, out_path):
    labels = [
        ("Page", "page"), ("Name", "name"), ("Description", "description"),
        ("YOB", "yob"), ("Sire sire sire", "sire_sire_sire"),
        ("Sire sire dam", "sire_sire_dam"), ("Sire dam sire", "sire_dam_sire"),
        ("Sire dam dam", "sire_dam_dam"), ("Dam sire sire", "dam_sire_sire"),
        ("Dam sire dam", "dam_sire_dam"), ("Dam dam sire", "dam_dam_sire"),
        ("Dam dam dam", "dam_dam_dam"), ("Sire sire", "sire_sire"),
        ("Sire dam", "sire_dam"), ("Dam sire", "dam_sire"), ("Dam dam", "dam_dam"),
        ("Sire", "sire"), ("Dam", "dam"), ("Dam YOB", "dam_yob"),
    ]

    with open(out_path, "w", encoding="utf-8") as out:
        for h in horses:
            for label, key in labels:
                out.write(f"{label}: {h[key]}\n")
            out.write("\n")


# Dicts to database..
# NAME_MATCH = "UPPER(RTRIM(name, '.'))"

# def match_form(name):
    # return name.rstrip(".").upper()
# def name_key(name):
    # if not name:
        # return None
    # n = name.upper()
    # return " ".join(n.split())

def split_name(name):
    """returns name and country split"""
    core, country = parse_name(name)
    return core, normalize_name(core), country

def horse_label(cur, horse_id):
    return cur.execute("SELECT name, name_norm, country FROM horses WHERE horse_id = ?",
        (horse_id,)).fetchone()


# YOB and dam are as close to unique as you can get. Sometimes dam names
# repeat, but it usually isn't an issue.
def find_or_create_by_dam(cur, name, sire_id, dam_id, yob, page=None):
    core, norm, country =split_name(name)

    row = None
    if dam_id is not None and yob is not None:
        row = cur.execute("SELECT horse_id, sire_id FROM horses WHERE dam_id = ? AND year_foaled = ?",
            (dam_id, yob)).fetchone()

    # FIX name fallback. with no year_foaled
    if row is None and norm:
        rows = cur.execute(
            "SELECT horse_id, sire_id, dam_id, year_foaled FROM horses "
            "WHERE name_norm = ? AND country IS ?", (norm, country)).fetchall()
        rows = [r for r in rows if r[3] is None or yob is None or r[3] == yob]
        if rows:
            def score(r):
                _, s, d, y = r
                return ((yob is not None and y == yob) * 4 +
                        (dam_id is not None and d == dam_id) * 2 +
                        (sire_id is not None and s == sire_id))
            best = max(rows, key=lambda r: (score(r), -r[0]))
            row = (best[0], best[1])


    if row:
        horse_id, existing_sire = row
        # FIX: never make a horse its own parent
        if horse_id in (sire_id, dam_id):
            print(f"PAGE {page}: self-parent on {name} (horse_id {horse_id}), not updated")
            return horse_id
        if existing_sire is not None and sire_id is not None and existing_sire != sire_id:
            print(f"PAGE {page}: {name or 'unnamed'} ({yob})\n"
                  f"  DB sire:  {existing_sire} {horse_label(cur, existing_sire)}\n"
                  f"  PDF sire: {sire_id} {horse_label(cur, sire_id)}")
        # Update horses if rows are empty
        cur.execute("""
                    UPDATE horses SET
                        name        = COALESCE(name, ?),
                        name_norm   = COALESCE(name_norm, ?),
                        country     = COALESCE(country, ?),
                        sire_id     = COALESCE(sire_id, ?),
                        dam_id      = COALESCE(dam_id, ?),
                        year_foaled = COALESCE(year_foaled, ?)
                    WHERE horse_id = ?""",
                    (core, norm, country, sire_id, dam_id, yob, horse_id))
        return horse_id
 
    if not norm and dam_id is None:
        return None  # nothing to identify this horse by
 
    cur.execute("INSERT INTO horses (name, name_norm, country, sire_id, dam_id, year_foaled) VALUES (?, ?, ?, ?, ?, ?)",
                (core, norm, country, sire_id, dam_id, yob))
    return cur.lastrowid
 
 
# FIX: parents are used to CHOOSE between horses with the same name, not to
# REJECT the only one. The old filter caused the duplicate cascade
# (one duplicated Majesty's Crown -> a second Smoke Glacken -> ...).
def find_or_create_ancestor(cur, name, sire_id=None, dam_id=None, stallion=False, page=None):
    core, norm, country = split_name(name)
    if not norm:
        return None
 
    rows = cur.execute(
        "SELECT horse_id, sire_id, dam_id, is_stallion FROM horses "
        "WHERE name_norm = ? AND country IS ?", (norm, country)).fetchall()
 
    if rows:
        def score(r):
            _, s, d, st = r
            return ((sire_id is not None and s == sire_id) * 2 +
                    (dam_id is not None and d == dam_id) * 2 +
                    (stallion and st == 1))
        hid, s, d, _ = max(rows, key=lambda r: (score(r), -r[0]))
 
        if hid in (sire_id, dam_id):
            print(f"PAGE {page}: self-parent on {name} (horse_id {hid}), not updated")
            return hid
        if (s and sire_id and s != sire_id) or (d and dam_id and d != dam_id):
            print(f"PAGE {page}: parent mismatch on {name} (horse_id {hid}), kept existing parents")
 
        cur.execute("""
                    UPDATE horses SET
                        sire_id     = COALESCE(sire_id, ?),
                        dam_id      = COALESCE(dam_id, ?),
                        is_stallion = MAX(COALESCE(is_stallion, 0), ?)
                    WHERE horse_id = ?""", (sire_id, dam_id, int(stallion), hid))
        return hid
 
    cur.execute("INSERT INTO horses (name, name_norm, country, sire_id, dam_id, is_stallion) VALUES (?, ?, ?, ?, ?, ?)",
                (core, norm, country, sire_id, dam_id, int(stallion)))
    return cur.lastrowid
 
 
def insert_threecross(cur, h):
    page = h["page"]
 
    def a(name, sire_id=None, dam_id=None, stallion=False):
        return find_or_create_ancestor(cur, name, sire_id, dam_id, stallion, page)
 
    def s(name, sire_id=None, dam_id=None):  # sire positions
        return a(name, sire_id, dam_id, stallion=True)
 
    sire_sire = s(h["sire_sire"], s(h["sire_sire_sire"]), a(h["sire_sire_dam"]))
    sire_dam  = a(h["sire_dam"],  s(h["sire_dam_sire"]),  a(h["sire_dam_dam"]))
    dam_sire  = s(h["dam_sire"],  s(h["dam_sire_sire"]),  a(h["dam_sire_dam"]))
    dam_dam   = a(h["dam_dam"],   s(h["dam_dam_sire"]),   a(h["dam_dam_dam"]))
 
    sire = s(h["sire"], sire_sire, sire_dam)
 
    if h["dam_yob"]:
        dam = find_or_create_by_dam(cur, h["dam"], dam_sire, dam_dam, h["dam_yob"], page)
    else:
        dam = a(h["dam"], dam_sire, dam_dam)
 
    name = None if unnamed.match(h["name"]) else h["name"]
    return find_or_create_by_dam(cur, name, sire, dam, h["yob"], page)
 
 
def load_into_db(horses, db_path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    # FIX: index the columns the lookups actually use
    cur.execute("CREATE INDEX IF NOT EXISTS inx_horses_norm_country ON horses(name_norm, country)")
    cur.execute("CREATE INDEX IF NOT EXISTS inx_horses_dam_yob ON horses(dam_id, year_foaled)")
    count = 0
    for h in horses:
        insert_threecross(cur, h)
        count += 1
    con.commit()
    con.close()
    print(f"Loaded {count} horses")
 
 
 
if __name__ == "__main__":
    for pdf_path in sorted(KEE_PDF_PATH.glob("*.pdf")):
        print(f"---{pdf_path.name}---")
        extract_3cross(pdf_path, THREE_CROSS)
        horses = list(parse_horse(THREE_CROSS))
        write_review(horses, LABELED_FILE)
        load_into_db(horses, DB_FILE)