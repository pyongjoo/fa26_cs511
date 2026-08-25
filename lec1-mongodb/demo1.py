"""Demo 1: schema is per document, not per table.

Same collection can hold documents with different fields.
Relational equivalent: ALTER TABLE, extra tables, or lots of NULLs.
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

password = os.getenv("DB_PASSWORD")
uri = f"mongodb+srv://admin:{password}@cluster0.i1h9lzm.mongodb.net/?appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi("1"))
db = client.demo
products = db.products

products.drop()

products.insert_many(
    [
        {"sku": "BK-1", "type": "book", "title": "CS511 Notes", "pages": 320},
        {
            "sku": "LP-9",
            "type": "laptop",
            "brand": "Framework",
            "specs": {"ram_gb": 32, "cpu": "Ryzen 7"},
        },
        {
            "sku": "HP-2",
            "type": "headphones",
            "brand": "Sony",
            "wireless": True,
        },
    ]
)
print(f"Inserted {products.count_documents({})} products (different shapes, one collection)\n")

print("Each document has its own fields:")
for product in products.find():
    fields = sorted(key for key in product if key != "_id")
    print(f"  {product['sku']} ({product['type']}): {fields}")

print("\nLaptops with at least 32GB RAM (nested field, no extra table):")
for product in products.find({"type": "laptop", "specs.ram_gb": {"$gte": 32}}):
    print(f"  {product['sku']} {product['brand']} — {product['specs']}")

print("\nBooks only — laptop/headphone fields are simply absent, not NULL:")
for product in products.find({"type": "book"}):
    print(f"  {product}")
