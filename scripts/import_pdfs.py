# My goal is to import the PDFs and build out the database with the three cross
# information from this. It will add to the size of database file, but worth it.
#

import re
import pymupdf

# Sire line: Stops waste by stopping at the sire blurb line
#
sire_line = re.compile(r"^By [A-Z '()-]+ \(\d{4}\)", re.MULTILINE)

with pymupdf.open("../data/kee/pdf/jan-2011.pdf") as pdf, open("texttest.txt", "w", encoding="utf-8") as out:
    for i, page in enumerate(pdf, start=1):
        text = page.get_text()
        match = sire_line.search(text)
        if match:
            out.write(f"--- PAGE {i} ---\n")
            out.write(text[:match.start()].rstrip() + "\n")
