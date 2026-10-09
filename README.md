# horse-value
A searchable sales result for race horses.

## Horse Data Tree

All horse results are in the `/data/` directory. Then subdivided into the three
main sales companies, Fasig Tipton, Keeneland, and OBS. Then within there, I
put two different folders for each one, the CSV results and the PDF catalog.
OBS had the most inconsistent data, so those will probably be problems later on
in the process.

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
