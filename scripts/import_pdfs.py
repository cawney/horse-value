# My goal is to import the PDFs and build out the database with the three cross
# information from this. It will add to the size of database file, but worth it.
#

import re
import pymupdf

# Sire line: Stops waste by stopping at the sire blurb line
#

###############################################################################
# Regex
# #############################################################################


sire_line = re.compile(r"^By [A-Z '()-]+ \(\d{4}\)", re.MULTILINE)
name_line = re.compile(r"^[A-Z][A-Z().' -]+[^.]+$")
page_line = re.compile(r"^--- PAGE (\d+) ---$")

with pymupdf.open("../data/kee/pdf/jan-2011.pdf") as pdf, open("texttest.txt", "w", encoding="utf-8") as out:
    for i, page in enumerate(pdf, start=1):
        text = page.get_text()
        match = sire_line.search(text)
        if match:
            out.write(f"--- PAGE {i} ---\n")
            out.write(text[:match.start()].rstrip() + "\n")

with open("texttest.txt", "r", encoding="utf-8") as text, open("regextest.txt", "w", encoding="utf-8") as out:
    page = None
    found_name = None
    for i, horse in enumerate(text):
        m = page_line.match(horse)
        if m:
            page = int(m[1])
            found_name = False # resets found name.
            out.write(f"Page Number: {page}\n")
            continue 

        if not found_name and name_line.match(horse):
            found_name = True
            name = horse
            out.write(f"Name: {name}\n")

