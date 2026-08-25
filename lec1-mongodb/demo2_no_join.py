"""Demo 2: embed related data instead of JOIN.

A supplier document contains the parts it supplies.
Relational equivalent: suppliers ⋈ supply ⋈ parts.
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
suppliers = db.suppliers

suppliers.drop()

suppliers.insert_many(
    [
        {
            "sid": 16,
            "name": "General Supply",
            "city": "Boston",
            "state": "Ma",
            "parts": [
                {"pid": 27, "name": "Power saw", "color": "silver", "qty": 100, "price": 20.00},
                {"pid": 42, "name": "bolts", "color": "gray", "qty": 1000, "price": 0.10},
            ],
        },
        {
            "sid": 24,
            "name": "Special Supply",
            "city": "Detroit",
            "state": "Mi",
            "parts": [
                {"pid": 42, "name": "bolts", "color": "gray", "qty": 5000, "price": 0.08},
            ],
        },
    ]
)
print(f"Inserted {suppliers.count_documents({})} suppliers with embedded parts\n")

print("General Supply catalog — no join; parts are already on the document:")
supplier = suppliers.find_one({"sid": 16})
print(f"  {supplier['sid']}: {supplier['name']} ({supplier['city']}, {supplier['state']})")
for part in supplier["parts"]:
    print(f"    pid {part['pid']}: {part['name']} ({part['color']}) qty={part['qty']} ${part['price']:.2f}")

print("\nWho supplies bolts (query into the embedded array):")
for supplier in suppliers.find({"parts.pid": 42}):
    print(f"  {supplier['name']}")

print("\nSpecial Supply starts carrying Power saws with $push (no supply table):")
suppliers.update_one(
    {"sid": 24},
    {"$push": {"parts": {"pid": 27, "name": "Power saw", "color": "silver", "qty": 50, "price": 22.00}}},
)
supplier = suppliers.find_one({"sid": 24})
print("  catalog:", [part["name"] for part in supplier["parts"]])
