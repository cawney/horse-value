CREATE TABLE horses (
	horse_id	INTEGER PRIMARY KEY,
	name		TEXT,
	name_norm	TEXT,		-- STRIPPED PUNCTUATION AND ALL UPPER CASE
	country		TEXT,		-- The stripped country to normalize name
	year_foaled	INTEGER,
	sex		TEXT,
	color		TEXT,
	sire_id		INTEGER REFERENCES horse(horse_id),
	dam_id		INTEGER REFERENCES horse(horse_id),
	UNIQUE (sire_id, dam_id, year_foaled)
);

CREATE TABLE sale_events (
	sale_id		INTEGER PRIMARY KEY,
	company		TEXT,		-- Kee, FT, OBS
	sale_name	TEXT,		-- Sept Yearling, etc.
	start_date	DATE
);

