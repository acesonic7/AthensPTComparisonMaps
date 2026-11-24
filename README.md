# Athens transit vs car reach maps

**Live: [athens-transit-reach.vercel.app](https://athens-transit-reach.vercel.app)**

An interactive map of how far you can get from any point in the Athens basin in 15, 30 or 45 minutes:

- **Public transport**: walking plus bus, trolley, metro (M1–M3), tram and Proastiakos suburban rail, using real timetables
- **Car**: driving with a modelled typical-weekday traffic profile, one-way streets and an optional allowance for parking

Pick any departure time from 05:00 to 04:45 the following night (with Now, Morning peak, Midday, Evening and Night presets; Now uses the time in Athens), and click anywhere to set the origin. Streets fill in minute by minute, coloured by travel time. All routing runs in the browser. The views are:

- **Transit** and **Car**: travel time to every street. On the car map, faint streets are ones the car drives past and solid streets are ones you have parked and walked to.
- **Side by side**: both maps, with pan and zoom linked.
- **Which is faster**: each street coloured by whether transit or the car gets there first.
- **Transit by mode**: public transport only; each street coloured by the vehicle you spend longest on to reach it (bus, trolley, metro, tram, suburban rail, or walking only).

Switch to **Click shows trip** and click a destination to see both journeys step by step, with times, and their routes drawn on the map.

The page is in English and Greek (**ΕΛ / EN** at the top right). It opens in English, remembers a choice made with the switch, and `?lang=el` opens it in Greek. **Save image** downloads the current map as a PNG with a title, the start point and time, the legend and credits.

Under each map's clock, a line gives the area within reach for the chosen time budget, next to the other modes. **Share link** copies a link to the exact map on screen: the start point, departure time, view, time budget, car options and any trip you opened are all kept in the address (for example `?from=-2000,3500&at=0200&view=both`).

## Why

Whether a job, a school or a hospital is "close" depends on how you travel. In Athens, two people living a few streets apart can have very different cities within reach, depending on how near they are to a metro station or a frequent bus line. This project makes that visible street by street. It aims to:

- **Show how accessible the city is by public transport**: how much of Athens buses, trolleys, metro, tram and suburban rail put within 15, 30 or 45 minutes.
- **Find the areas public transport serves poorly**: neighbourhoods where transit adds little over walking, or where the car is far quicker.
- **Put traffic congestion in context**: comparing door-to-door times, parking included, shows where transit already competes with the car and where it does not yet.
- **Stay open**: anyone can check the method, rerun it with new timetables, or adapt it to another city.

It is a planning sketch, not a journey planner: transit uses scheduled times, and car times come from a traffic model rather than live data.

## Run it

```bash
python3 -m http.server 8765 -d site
```

Then open http://localhost:8765. The page needs no build step: `site/data/` already holds the packed street network and timetables. `site/about.html` explains why the map was made and who made it.

## Deploy

The site is hosted on Vercel and every push to `main` deploys it automatically to https://athens-transit-reach.vercel.app. `vercel.json` serves `site/` as static files, with no build step.

The social preview image `site/og.jpg` is a screenshot of the page in poster mode (`/?poster`). Re-render it with `prep/render_og.sh` while the site is served locally on port 8766.

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
- **Transit**: every connection of a working day (Tuesday) and the night after it, including the night buses, routed with the Connection Scan Algorithm. The timetable is split into one file per departure hour (`site/data/conn/`), so the page only downloads the hours it needs. The next morning's first runs are copied from the same day, so night trips can connect to them. You walk to the first stop and from the last one. Transfers between stops up to about 350 m apart are allowed, with a 1-minute buffer before boarding. Walking speed is 4.8 km/h.
- **Car**: a model, not live traffic. Free-flow speed by road type, times a congestion factor that follows a working day: morning peak 08:00–09:00, afternoon peak 14:30–15:30, a smaller evening peak, and light traffic late at night. Each junction adds a delay, and driving within about 2.5 km of Syntagma is 15% slower. With parking on, a car trip is: reach the car (2 min), drive to any parking spot, search for a space there (8 min near the centre, down to 1 min in the suburbs), then walk to the destination. Walking straight there is allowed when it's quicker. The numbers are listed in the page under *How car travel times are modelled* and are set at the top of the script in `site/index.html`.

## Limitations

- The OASA/STASY timetables are the summer 2026 ones; the Proastiakos timetable is for 1 Dec 2026.
- Bus times are scheduled times, not real running times.
- Car times come from a model that hasn't been checked against measured traffic.

## Author

**Dr Ioannis Tsouros**: transportation researcher, Lead Scientist and co-founder of MobyX, and external scientist at the Transportation and Decision-Making Laboratory, University of the Aegean.

[Website](https://www.jtsouros.site/) · [GitHub](https://github.com/acesonic7) · [LinkedIn](https://www.linkedin.com/in/ioannis-tsouros-ba582243) · [Google Scholar](https://scholar.google.com/citations?user=nahTqW0AAAAJ&hl=en)

Corrections and ideas are welcome as [issues](https://github.com/acesonic7/AthensPTComparisonMaps/issues).

## Data sources and licences

- Streets: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL. `site/data/` is derived from OSM, so it is also under the ODbL.
- OASA and STASY GTFS: published by OASA on data.gov.gr, mirrored by the [Mobility Database](https://mobilitydatabase.org).
- Hellenic Train GTFS: community-built feed at [jbb.ghsq.de](https://jbb.ghsq.de/gtfs/), listed on [Transitland](https://www.transit.land/feeds/f-hellenic~train~gr). Its attribution names OpenStreetMap contributors.
