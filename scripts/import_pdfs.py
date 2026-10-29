# My goal is to import the PDFs and build out the database with the three cross
# information from this. It will add to the size of database file, but worth it.
#

import re
import pymupdf  # pyright: ignore[reportMissingImports]

PDF_FILE = "../data/kee/pdf/jan-2011.pdf"
THREE_CROSS = "texttest.txt"
LABELED_FILE = "regextest.txt"


###############################################################################
# Regex
# #############################################################################


sire_line = re.compile(r"^By [A-Z '()-]+ \(\d{4}\)", re.MULTILINE)
name_line = re.compile(r"^[A-Z][A-Z().' -]+$")
page_line = re.compile(r"^--- PAGE (\d+) ---$")
leaders = re.compile(r"\s*\.{2,}\s*$")


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


# Text to labeled text
def label_horses(in_path, out_path):
    with open(in_path, "r", encoding="utf-8") as text:
       lines = [l.strip() for l in text if l.strip()]

    with open(out_path, "w", encoding="utf-8") as out:
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
                "name":           line,
                "description":    description,
                "sire_sire_sire": sire_sire_sire,
                "sire_sire_dam":  sire_sire_dam,
                "sire_dam_sire":  sire_dam_sire,
                "sire_dam_dam":   sire_dam_dam,
                "dam_sire_sire":  dam_sire_sire,
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

            out.write(f"Name: {name}\n")
            out.write(f"Description: {description}\n")
            out.write(f"Sire sire sire: {sire_sire_sire}\n")
            out.write(f"Sire sire dam: {sire_sire_dam}\n")
            out.write(f"Sire dam sire: {sire_dam_sire}\n")
            out.write(f"sire dam dam: {sire_dam_dam}\n")
            out.write(f"Dam sire sire: {dam_sire_sire}\n")
            out.write(f"Dam sire dam: {dam_sire_dam}\n")
            out.write(f"Dam dam sire: {dam_dam_sire}\n")
            out.write(f"Dam dam dam: {dam_dam_dam}\n")
            out.write(f"Sire sire: {sire_sire}\n")
            out.write(f"Sire dam: {sire_dam}\n")
            out.write(f"Dam sire: {dam_sire}\n")
            out.write(f"Dam dam: {dam_dam}\n")
            out.write(f"Sire: {sire}\n")
            out.write(f"Dam: {dam} {dam_yob}\n")


        if page is not None and not found_name:
            out.write(f"PAGE {page}: no name line found\n\n")

if __name__ == "__main__":
    extract_3cross(PDF_FILE, THREE_CROSS)
    label_horses(THREE_CROSS, LABELED_FILE)
