-- Horse Sales Price Lookup Schema
-- Run with: `sqlite3 horses.db < schema.sql

DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS sale_events;
DROP TABLE IF EXISTS horses;
DROP TABLE IF EXISTS raw_sales;

PRAGMA foreign_keys = ON; -- This allows some of these tables to have foreign keys.


CREATE TABLE horses (
	horse_id	INTEGER PRIMARY KEY,
	name		TEXT,
	name_norm	TEXT,		-- STRIPPED PUNCTUATION AND ALL UPPER CASE
	country		TEXT,		-- The stripped country to normalize name
	year_foaled	INTEGER,
	sex		TEXT,
	color		TEXT,
	is_stallion	INTEGER DEFAULT 0,	-- set when a name appears in the 3x as sire or bms
	sire_id		INTEGER REFERENCES horses(horse_id),
	dam_id		INTEGER REFERENCES horses(horse_id),
	UNIQUE (sire_id, dam_id, year_foaled)
);

CREATE TABLE sale_events (
	sale_id		INTEGER PRIMARY KEY,
	company		TEXT,		-- Kee, FT, OBS
	sale_name	TEXT,		-- Sept Yearling, etc.
	start_date	DATE
);

CREATE TABLE sales (
	sale_id		INTEGER REFERENCES sale_events(sale_id),
	hip		TEXT,
	horse_id	INTEGER REFERENCES horses(horse_id),
	session		TEXT,
	horse_type	TEXT, -- hip NN is what type of horse (yearling, wenaling, etc.)
	status		TEXT CHECK (status IN ('SOLD', 'RNA', 'OUT', 'PRIVATE')),
	price		INTEGER,
	consignor	TEXT,
	buyer		TEXT,
	in_foal_to_id	INTEGER REFERENCES horses(horse_id),
	source_file	TEXT,		-- FILE NAME, NOT PATH
	PRIMARY KEY (sale_id, hip)
);

CREATE TABLE raw_sales (
	raw_id		INTEGER PRIMARY KEY,
	source_file	TEXT,
	company		TEXT,
	imported_at	TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX inx_horses_name_norm ON horses(name_norm);
CREATE INDEX inx_horses_dam	  ON horses(dam_id);
CREATE INDEX inx_horses_sire	  ON horses(sire_id);
CREATE INDEX inx_sales_horse	  ON sales(horse_id);
