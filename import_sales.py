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



###############################################################################
# SCHEMA
###############################################################################


SCHEMA = """
CREATE TABLE IF NOT EXISTS sales (
    sale_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    company     TEXT NOT NULL,
    sale_name   TEXT,
    sale_year   INTEGER NOT NULL,
    sale_date   TEXT,
    hip         TEXT NOT NULL,
    horse_name  TEXT
    sex         TEXT,
    color       TEXT,
    year_foaled INTEGER,
    sire        TEXT,
    dam         TEXT,
    bms         TEXT,
    consignor   TEXT,
    buyer       TEXT,
    price       INTEGER,
    status      TEXT,           -- SOLD, RNA, OUT, ETC.
    source_file TEXT,
    UNIQUE (company, sale_name, sale_year, hip)
);

CREATE INDEX IF NOT EXISTS inx_
