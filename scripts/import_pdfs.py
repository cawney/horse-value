# My goal is to import the PDFs and build out the database with the three cross
# information from this. It will add to the size of database file, but worth it.
#

import re
import sqlite3
import pymupdf  # pyright: ignore[reportMissingImports]

PDF_FILE     = "../data/kee/pdf/jan-2011.pdf"
THREE_CROSS  = "texttest.txt"
LABELED_FILE = "regextest.txt"
DB_FILE      = "../docs/horses.db"


###############################################################################
# Regex
# #############################################################################


sire_line = re.compile(r"^By [A-Z '()-]+ \(\d{4}\)", re.MULTILINE)
name_line = re.compile(r"^[A-Z][A-Z().' -]+$")
unnamed = re.compile(r"^(BAY|DARK BAY OR BROWN|GRAY OR ROAN|BLACK|GRAY|ROAN|WHITE)\s+"
                     r"(COLT|FILLY|GELDING|RIDGLING|HORSE|MARE)")
country_re = re.compile(r"(.*?)\s*\(([A-Z]{2,3})\)$")
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
                out.write(f"PAGE {page}: no name line found\n\n")
            page = int(m[1])
            found_name = False
            continue

        if found_name:
            continue

        # if name line doesn't match and i + 15 is less than length of lines
        if not name_line.match(line) and i + 16 < len(lines):
            continue

        found_name = True

        def at(offset):
            return leaders.sub("", lines[i + offset])
        
        y = any_year.search(at(1))
        if y:
            yob = int(y[0])
        else:
            yob = None
        name = line
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
        dam_yob        = at(16)

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
        ("Sire dam", "sire_dam"), ("Dam sire", "dam_sire"), ("Sire", "sire"),
        ("Dam dam", "dam_dam"), ("Dam YOB", "dam_yob"),
    ]

    with open(out_path, "w", encoding="utf-8") as out:
        for h in horses:
            for label, key in labels:
                out.write(f"{label}: {h[key]}\n")
            out.write("\n")


# Dicts to database..
NAME_MATCH = "UPPER(RTRIM(name, '.'))"

def match_form(name):
    return name.rstrip(".").upper()
def name_key(name):
    if not name:
        return None
    n = name.upper()
    return " ".join(n.split())

def split_name(name):
    """returns name and country split"""
    if not name:
        return None, None
    m = country_re.match(name)
    core, country = (m[1], m[2]) if m else (name, None)
    norm = " ".join(core.rstrip(".").upper().split())
    return norm, country
    

# YOB and dam are as close to unique as you can get. Sometimes dam names
# repeat, but it usually isn't an issue.
def find_or_create_by_dam(cur, name, sire_id, dam_id, yob, page=None):
    row = cur.execute(
        "SELECT horse_id, sire_id FROM horses WHERE dam_id = ? AND year_foaled = ?",
        (dam_id, yob)).fetchone()
    
    norm, country = split_name(name)

    if row:
        horse_id, existing_sire = row
        if existing_sire is not None and sire_id is not None and existing_sire != sire_id:
            print(f"PAGE {page}: Sire conflict for horse_id {horse_id} ({name or 'unnamed'}, {yob})")
        # Update horses if rows are emmpty
        cur.execute("""
                    UPDATE horses SET
                        name      = COALESCE(name, ?),
                        name_norm = COALESCE(name_norm, ?),
                        country   = COALESCE(country, ?),
                        sire_id   = COALESCE(sire_id, ?)
                    WHERE horse_id = ?""", (name, norm, country, sire_id, horse_id))
        return horse_id

    cur.execute("INSERT INTO horses (name, name_norm, country, sire_id, dam_id, year_foaled) VALUES (?, ?, ?, ?, ?, ?)",
                (name, norm, country, sire_id, dam_id, yob))
    return cur.lastrowid


def find_or_create_ancestor(cur, name, sire_id=None, dam_id=None):
    norm, country = split_name(name) 
    row = cur.execute("""
                      SELECT horse_id FROM horses
                      WHERE name_norm = ?
                        AND country IS ?
                        AND (sire_id IS NULL or ? IS NULL OR sire_id = ?)
                        AND (dam_id  IS NULL or ? IS NULL OR dam_id  = ?)
                      LIMIT 1""", (norm, country, sire_id, sire_id, dam_id, dam_id)).fetchone()

    if row:
        cur.execute("""
                    UPDATE horses SET
                        sire_id = COALESCE(sire_id, ?),
                        dam_id  = COALESCE(dam_id, ?)
                    WHERE horse_id =?""", (sire_id, dam_id, row[0]))
        return row[0]

    cur.execute("INSERT INTO horses (name, name_norm, country, sire_id, dam_id) VALUES (?, ?, ?, ?, ?)",
                (name, norm, country, sire_id, dam_id))
    return cur.lastrowid


def insert_threecross(cur, h):
    def a(name, sire_id=None, dam_id=None):
        return find_or_create_ancestor(cur, name, sire_id, dam_id)
    
    sire_sire = a(h["sire_sire"], a(h["sire_sire_sire"]), a(h["sire_sire_dam"]))
    sire_dam  = a(h["sire_dam"], a(h["sire_dam_sire"]), a(h["sire_dam_dam"]))
    dam_sire  = a(h["dam_sire"], a(h["dam_sire_sire"]), a(h["dam_sire_dam"]))
    dam_dam   = a(h["dam_dam"], a(h["dam_dam_sire"]), a(h["dam_dam_dam"]))

    sire = a(h["sire"], sire_sire, sire_dam)

    if h["dam_yob"]:
        dam = find_or_create_by_dam(cur, h["dam"], dam_sire, dam_dam, h["dam_yob"], h["page"])
    else:
        dam = a(h["dam"], dam_sire, dam_dam)

    name = None if unnamed.match(h["name"]) else h["name"]
    return find_or_create_by_dam(cur, name, sire, dam, h["yob"], h["page"])


def load_into_db(horses, db_path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(f"CREATE INDEX IF NOT EXISTS inx_horses_name_key ON horses({NAME_MATCH})")
    cur.execute("CREATE INDEX IF NOT EXISTS inx_horses_dam_yob ON horses(dam_id, year_foaled)")
    count = 0
    for h in horses:
        insert_threecross(cur, h)
        count += 1
    con.commit()
    con.close()
    print(f"Loaded {count} horses")



if __name__ == "__main__":
    extract_3cross(PDF_FILE, THREE_CROSS)
    horses = list(parse_horse(THREE_CROSS))
    write_review(horses, LABELED_FILE)
    load_into_db(horses, DB_FILE)
