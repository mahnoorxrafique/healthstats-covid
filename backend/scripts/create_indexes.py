"""
Create all project indexes (safe to run more than once).

Usage (from the backend/ folder):
    python scripts/create_indexes.py
"""
import os

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv()
client = MongoClient(os.environ["MONGODB_URI"])
db = client[os.getenv("DB_NAME", "healthstats")]

# Compound indexes for the per-country, over-time queries
db.vaccinations.create_index(
    [("iso_code", ASCENDING), ("date", ASCENDING)], name="iso_date_idx"
)
db.hospital_stats.create_index(
    [("iso_code", ASCENDING), ("date", ASCENDING)], name="iso_date_idx"
)

# Group/filter countries by continent
db.countries.create_index("continent", name="continent_idx")

# Reports: filter by country + full-text search on title/body
db.users_reports.create_index("iso_code", name="report_country_idx")
db.users_reports.create_index(
    [("title", "text"), ("body", "text")], name="reports_text_idx"
)

for name in ["vaccinations", "hospital_stats", "countries", "users_reports"]:
    print(name, "->", list(db[name].index_information().keys()))
print("Done.")
