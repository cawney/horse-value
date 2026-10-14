# horse-value
A searchable sales result for race horses.

## Horse Data Tree

All horse results are in the `/data/` directory. Then subdivided into the three
main sales companies, Fasig Tipton, Keeneland, and OBS. Then within there, I
put two different folders for each one, the CSV results and the PDF catalog.
OBS had the most inconsistent data, so those will probably be problems later on
in the process.

### Progress

#### Fasig Tipton

Stored in `/data/ft/csv` and `/data/ft/pdf`

| Year | Status |
|------|--------|
| 2026 | 

## Schema

5 tables.

* horse
* company
* sales
* sale_results
* import_log

### Horse

This table will have the fields unique to the physical horse, like name, year
of birth, sire, dam, and dam_id. Dam_id is used to make the table self
referencing. It allows to search the dam_id as a horse_id, then you'll be able
to see a second generation of horses.

### company

There are a lot of sales, and they usually overlap in the same month and same
naming convention like 'Fall Yearling Sale'. Which could be nearly any of three
different sales. Adding a company table normalizes the database a bit more to 
help organize all the different sales and results. This allows me to name sales
by their given names, then add the company ID to it to help organize them.

### sales

The different sales would go here. This would store stuff like the company_id,
sale name, when it happened, location, etc. Things specific to the actual sale.

### sale_results

This has all the information for each horse that goes through the ring at an
auction. This would be things like hip number, consignor, buyer, price, etc.
There is more information, but those are the important pieces. Anything that is
in a CSV row would end up in this table.

### import_log

This is a pretty self explanatory table. It just shows the path of what was
imported and when it was imported so that if I need to go back and see if there
is a problem with the table, it can be traced easier. Most unnecessary table
in my opinion.

# KEELAND PDF SCHEMA

It looks likes getting the big PDF for each sale catalog will be a little more
difficult than I thought. The URL schema might be the way to go. I can work on
building out a script for it. This is what it is for the first horse in the
Sept 2026 Sale: [link](https://secure.keeneland.com/sales/k226/pdfs/1.pdf). I
think the k226 will be the term that needs to change per sale. Worst case
scenario is I need to get a URL for each sale then just run that through a
script till I have downloaded all the individual pages.

## URL update

Once you get to the sale URL, change a hip.pdf to 'fullsale.pdf' to access the
full sale PDF. Change the YY to the last two digits in the year.

* November HORA:     /k6YY/ OR /NovYY/
* November Breeding: /k3YY/
* Champions:         /d1YY/
* September:         /k2YY/ OR /SepYY/
* April HORA:        /k5YY/ OR /AprYY/
* January:           /k4YY/ OR /JanYY/



