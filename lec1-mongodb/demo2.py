"""Demo 2: embed related data instead of JOIN.

A course document contains its students.
Relational equivalent: courses ⋈ enrollments ⋈ students.
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
courses = db.courses

courses.drop()

courses.insert_many(
    [
        {
            "code": "CS511",
            "title": "Advanced Data Management",
            "students": [
                {"netid": "alice", "name": "Alice", "year": 2},
                {"netid": "bob", "name": "Bob", "year": 3},
            ],
        },
        {
            "code": "CS411",
            "title": "Database Systems",
            "students": [
                {"netid": "alice", "name": "Alice", "year": 2},
                {"netid": "cara", "name": "Cara", "year": 1},
            ],
        },
    ]
)
print(f"Inserted {courses.count_documents({})} courses with embedded students\n")

print("CS511 roster — no join; students are already on the document:")
course = courses.find_one({"code": "CS511"})
print(f"  {course['code']}: {course['title']}")
for student in course["students"]:
    print(f"    {student['netid']}: {student['name']} (year {student['year']})")

print("\nCourses Alice is in (query into the embedded array):")
for course in courses.find({"students.netid": "alice"}):
    print(f"  {course['code']}")

print("\nEnroll Dana in CS511 with $push (no enrollments table):")
courses.update_one(
    {"code": "CS511"},
    {"$push": {"students": {"netid": "dana", "name": "Dana", "year": 2}}},
)
course = courses.find_one({"code": "CS511"})
print("  roster:", [student["name"] for student in course["students"]])
