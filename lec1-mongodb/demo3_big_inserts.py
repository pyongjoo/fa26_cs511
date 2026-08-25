"""Demo 3 load: sampled suppliers, parts, supply, and an embedded copy.

Run this once before demo3_big_join.py. Drops join_* collections, then
reloads them with no extra indexes.
"""

import os
import random
from collections import defaultdict

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

N_SUPPLIERS = 2_000
N_PARTS = 2_000
N_SUPPLY = 25_000
BATCH = 2_000
SEED = 42

CITIES = [
    ("Boston", "Ma"),
    ("Detroit", "Mi"),
    ("Chicago", "Il"),
    ("Houston", "Tx"),
    ("Seattle", "Wa"),
    ("Denver", "Co"),
    ("Atlanta", "Ga"),
    ("Phoenix", "Az"),
    ("Portland", "Or"),
    ("Miami", "Fl"),
    ("Cleveland", "Oh"),
    ("Pittsburgh", "Pa"),
]

COMPANY = [
    "General",
    "Special",
    "Midwest",
    "Pacific",
    "Summit",
    "Harbor",
    "Pioneer",
    "Atlas",
    "Frontier",
    "Valley",
]
KIND = ["Supply", "Hardware", "Tools", "Parts", "Industrial", "Wholesale"]

PART_NAMES = [
    "Power saw",
    "bolts",
    "wrench",
    "hammer",
    "drill",
    "pliers",
    "screws",
    "nails",
    "sandpaper",
    "clamp",
    "chisel",
    "level",
    "tape measure",
    "socket set",
    "utility knife",
]
COLORS = ["silver", "gray", "black", "red", "blue", "yellow", "green", "white"]


def insert_batches(collection, docs):
    for i in range(0, len(docs), BATCH):
        collection.insert_many(docs[i : i + BATCH], ordered=False)


rng = random.Random(SEED)

suppliers.drop()
parts.drop()
supply.drop()
embedded.drop()

supplier_docs = []
for sid in range(1, N_SUPPLIERS + 1):
    city, state = rng.choice(CITIES)
    supplier_docs.append(
        {
            "sid": sid,
            "name": f"{rng.choice(COMPANY)} {rng.choice(KIND)}",
            "city": city,
            "state": state,
        }
    )

part_docs = []
for pid in range(1, N_PARTS + 1):
    part_docs.append(
        {
            "pid": pid,
            "name": rng.choice(PART_NAMES),
            "color": rng.choice(COLORS),
            "weight": rng.randint(1, 25),
        }
    )

pairs = set()
while len(pairs) < N_SUPPLY:
    pairs.add((rng.randint(1, N_SUPPLIERS), rng.randint(1, N_PARTS)))

supply_docs = [
    {
        "sid": sid,
        "pid": pid,
        "qty": rng.choice([50, 100, 250, 500, 1000, 5000]),
        "price": round(rng.uniform(0.05, 40.0), 2),
    }
    for sid, pid in pairs
]

parts_by_pid = {doc["pid"]: doc for doc in part_docs}
listings_by_sid = defaultdict(list)
for row in supply_docs:
    part = parts_by_pid[row["pid"]]
    listings_by_sid[row["sid"]].append(
        {
            "pid": row["pid"],
            "name": part["name"],
            "color": part["color"],
            "qty": row["qty"],
            "price": row["price"],
        }
    )

embedded_docs = []
for doc in supplier_docs:
    embedded_docs.append({**doc, "parts": listings_by_sid[doc["sid"]]})

print("Loading sampled suppliers / parts / supply (no extra indexes)...")
insert_batches(suppliers, supplier_docs)
insert_batches(parts, part_docs)
insert_batches(supply, supply_docs)
insert_batches(embedded, embedded_docs)

print(
    f"Inserted {suppliers.count_documents({})} suppliers, "
    f"{parts.count_documents({})} parts, "
    f"{supply.count_documents({})} supply rows, "
    f"{embedded.count_documents({})} embedded suppliers"
)
