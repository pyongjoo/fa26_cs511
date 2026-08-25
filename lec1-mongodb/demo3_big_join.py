"""Demo 3: JOIN is expensive; embed instead.

Expects join_* collections from demo3_big_inserts.py.
Relational equivalent: suppliers ⋈ supply ⋈ parts.
"""

import os
import time

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

password = os.getenv("DB_PASSWORD")
cluster = os.getenv("DB_CLUSTER")
uri = f"mongodb+srv://admin:{password}@{cluster}/?appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi("1"))
db = client.demo

suppliers = db.join_suppliers
parts = db.join_parts
supply = db.join_supply
embedded = db.join_embedded

CLIENT_LOOPS = 600
SAMPLE_SID = 1


def timed(label):
    start = time.perf_counter()

    class _Timer:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            elapsed = time.perf_counter() - start
            print(f"  {label}: {elapsed:.2f}s")

    return _Timer()


# Keep collections; drop extra indexes so a re-run still shows unindexed $lookup.
suppliers.drop_indexes()
parts.drop_indexes()

n_suppliers = suppliers.count_documents({})
n_parts = parts.count_documents({})
n_supply = supply.count_documents({})
n_embedded = embedded.count_documents({})
print(
    f"Joining {n_suppliers} suppliers, {n_parts} parts, "
    f"{n_supply} supply rows, {n_embedded} embedded suppliers\n"
)

print(f"Same question as Demo 2: catalog for supplier {SAMPLE_SID}")
with timed("embedded find_one (parts already on the document)"):
    doc = embedded.find_one({"sid": SAMPLE_SID})
print(f"  {doc['name']} ({doc['city']}) carries {len(doc['parts'])} parts")
if doc["parts"]:
    p = doc["parts"][0]
    print(f"  e.g. {p['name']} ({p['color']}) qty={p['qty']} ${p['price']:.2f}")

lookup_one = [
    {"$match": {"sid": SAMPLE_SID}},
    {
        "$lookup": {
            "from": "join_parts",
            "localField": "pid",
            "foreignField": "pid",
            "as": "part",
        }
    },
    {"$count": "n"},
]
with timed("$lookup supply ⋈ parts for that supplier (no index)"):
    n = next(supply.aggregate(lookup_one))["n"]
print(f"  joined {n} listings\n")

print("Full catalog: supply ⋈ suppliers ⋈ parts (the expensive case)")
unwind_embedded = [{"$unwind": "$parts"}, {"$count": "n"}]
with timed("scan embedded suppliers ($unwind + $count)"):
    n = next(embedded.aggregate(unwind_embedded))["n"]
print(f"  {n} listings, no join")

lookup_suppliers = [
    {
        "$lookup": {
            "from": "join_suppliers",
            "localField": "sid",
            "foreignField": "sid",
            "as": "supplier",
        }
    },
    {"$count": "n"},
]
with timed("unindexed $lookup supply ⋈ suppliers + $count"):
    n = next(supply.aggregate(lookup_suppliers))["n"]
print(f"  {n} rows")

lookup_both = [
    {
        "$lookup": {
            "from": "join_suppliers",
            "localField": "sid",
            "foreignField": "sid",
            "as": "supplier",
        }
    },
    {
        "$lookup": {
            "from": "join_parts",
            "localField": "pid",
            "foreignField": "pid",
            "as": "part",
        }
    },
    {"$count": "n"},
]
with timed("unindexed $lookup supply ⋈ suppliers ⋈ parts + $count"):
    n = next(supply.aggregate(lookup_both))["n"]
print(f"  {n} rows\n")

print(f"Client-side nested loop ({CLIENT_LOOPS} supply rows → find_one supplier)")
with timed(f"{CLIENT_LOOPS} round trips"):
    hits = 0
    for row in supply.find({}, {"sid": 1}).limit(CLIENT_LOOPS):
        if suppliers.find_one({"sid": row["sid"]}):
            hits += 1
print(f"  resolved {hits} suppliers")
print(f"  full {n_supply} rows would be ~{n_supply / CLIENT_LOOPS:.0f}× this wait\n")

print("Same $lookup after an index on suppliers.sid")
suppliers.create_index("sid")
with timed("indexed $lookup supply ⋈ suppliers + $count"):
    n = next(supply.aggregate(lookup_suppliers))["n"]
print(f"  {n} rows — faster than unindexed, still slower than embedding")
