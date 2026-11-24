# Athens transit vs car reach maps

An interactive map of how far you can get from any point in the Athens basin in 15, 30 or 45 minutes:

- **Public transport**: walking plus bus, trolley, metro (M1–M3), tram and Proastiakos suburban rail, using real timetables
- **Car**: driving with a modelled typical-weekday traffic profile, one-way streets and an optional allowance for parking

Click anywhere to set the origin. Streets fill in minute by minute, coloured by travel time. The views are **Transit**, **Car**, **Side by side**, and **Which is faster**, which colours each street by whether transit or the car gets there first. All routing runs in the browser.

## Run it

```bash
python3 -m http.server 8765 -d site
```

Then open http://localhost:8765. The page needs no build step: `site/data/` already holds the packed street network and timetables.

## Rebuild the data

```bash
pip install -r requirements.txt
```

1. Download the timetables (GTFS) into `dl/`:

   ```bash
   mkdir -p dl && cd dl
   curl -L -o bus.zip  https://files.mobilitydatabase.org/mdb-3220/latest.zip   # OASA buses + trolleys
   curl -L -o rail.zip https://files.mobilitydatabase.org/mdb-3221/latest.zip   # STASY metro + tram
   curl -L -o ht.zip   https://jbb.ghsq.de/gtfs/gr-hellenic-train.gtfs.zip     # Hellenic Train (Proastiakos)
   unzip -o bus.zip -d bus && unzip -o rail.zip -d rail && unzip -o ht.zip -d ht
   cd ..
   ```

2. Download the street network from OpenStreetMap through Overpass. The script retries if the server is busy.

   ```bash
   python3 prep/fetch_roads.py
   ```

3. Pack everything into `site/data/`:

   ```bash
   python3 prep/build_data.py
   ```

The service days are set at the top of `prep/build_data.py` (`BUS_SERVICE`, `RAIL_SERVICE`, `HT_DATE`). Update them when you download newer timetables.

## How it works

- **Streets**: OSM highways from motorway down to pedestrian streets, simplified with osmnx. Each street segment records its road type, whether you can walk on it, and which directions cars may use.
- **Transit**: connections departing 06:30–10:30 on a Tuesday, routed with the Connection Scan Algorithm. You walk to the first stop and from the last one. Transfers between stops up to about 350 m apart are allowed, with a 1-minute buffer before boarding. Walking speed is 4.8 km/h.
- **Car**: a model, not live traffic. Free-flow speed by road type, times a congestion factor that depends on the departure time and peaks around 08:00–09:00. Each junction adds a delay, and driving within about 2.5 km of Syntagma is 15% slower. With parking on, a trip adds time to reach the car, find a space and walk to the door. That time is longest near the centre. The numbers are listed in the page under *How car travel times are modelled* and are set at the top of the script in `site/index.html`.

## Limitations

- The OASA/STASY timetables are the summer 2026 ones; the Proastiakos timetable is for 1 Dec 2026.
- Bus times are scheduled times, not real running times.
- Car times come from a model that hasn't been checked against measured traffic.

## Data sources and licences

- Streets: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL. `site/data/` is derived from OSM, so it is also under the ODbL.
- OASA and STASY GTFS: published by OASA on data.gov.gr, mirrored by the [Mobility Database](https://mobilitydatabase.org).
- Hellenic Train GTFS: community-built feed at [jbb.ghsq.de](https://jbb.ghsq.de/gtfs/), listed on [Transitland](https://www.transit.land/feeds/f-hellenic~train~gr). Its attribution names OpenStreetMap contributors.
