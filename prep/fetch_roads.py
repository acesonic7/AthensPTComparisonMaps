"""Download the street network (walkable streets + motorways for driving) for the Athens basin
from OSM and save it as a directed GraphML (one-way streets kept)."""
import os, sys, time, osmnx as ox

HERE = os.path.dirname(os.path.abspath(__file__))
# west, south, east, north — Athens basin incl. Piraeus, Kifisia, Elliniko, airport
BBOX = (23.58, 37.84, 23.97, 38.13)
FILTER = ('["highway"~"motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|'
          'tertiary|tertiary_link|residential|unclassified|living_street|pedestrian|road"]'
          '["access"!~"private|no"]["area"!~"yes"]')

ox.settings.use_cache = True
ox.settings.cache_folder = os.path.join(HERE, "cache2")
ox.settings.requests_timeout = 300
ox.settings.useful_tags_way = list(ox.settings.useful_tags_way) + ["foot", "motor_vehicle"]
for attempt in range(8):
    try:
        G = ox.graph_from_bbox(BBOX, custom_filter=FILTER, simplify=True, retain_all=False)
        break
    except Exception as e:
        print("attempt", attempt, "failed:", str(e)[:120], file=sys.stderr, flush=True)
        time.sleep(30 * (attempt + 1))
else:
    sys.exit(1)
print(len(G.nodes), "nodes", len(G.edges), "edges")
ox.save_graphml(G, os.path.join(HERE, "roads2.graphml"))
