"""Demo 1: schema is per document, not per table.

Same collection can hold suppliers and parts with different fields.
Relational equivalent: ALTER TABLE, extra tables, or lots of NULLs.
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

password = os.getenv("DB_PASSWORD")
cluster = os.getenv("DB_CLUSTER")
uri = f"mongodb+srv://admin:{password}@{cluster}/?appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi("1"))
db = client.demo
catalog = db.catalog

catalog.drop()

catalog.insert_many(
    [
        {
            "kind": "supplier",
            "sid": 16,
            "name": "General Supply",
            "location": {"city": "Boston", "state": "Ma"},
            "since": 1984,
        },
        {
            "kind": "supplier",
            "sid": 24,
            "name": "Special Supply",
            "location": {"city": "Detroit", "state": "Mi"},
            "warehouse": True,
        },
        {
            "kind": "part",
            "pid": 27,
            "name": "Power saw",
            "weight": 7,
            "color": "silver",
            "specs": {"voltage": 120, "corded": True},
        },
        {
            "kind": "part",
            "pid": 42,
            "name": "bolts",
            "weight": 12,
            "color": "gray",
            "pack_qty": 100,
        },
    ]
)
print(f"Inserted {catalog.count_documents({})} catalog docs (different shapes, one collection)\n")

print("Each document has its own fields:")
for doc in catalog.find():
    fields = sorted(key for key in doc if key != "_id")
    label = doc.get("name")
    print(f"  {doc['kind']} {label}: {fields}")

print("\nSuppliers in Massachusetts (nested field, no extra table):")
for doc in catalog.find({"kind": "supplier", "location.state": "Ma"}):
    print(f"  {doc['sid']} {doc['name']} — {doc['location']}")

print("\nParts only — supplier fields are simply absent, not NULL:")
for doc in catalog.find({"kind": "part"}):
    print(f"  {doc}")
