"""
Load the Our World in Data COVID dataset into MongoDB.

Usage (from the backend/ folder):
    python scripts/load_data.py owid-covid-data.csv
"""
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv()

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "owid-covid-data.csv"
client = MongoClient(os.environ["MONGODB_URI"])
db = client[os.getenv("DB_NAME", "healthstats")]


def to_docs(df):
    """DataFrame -> list of dicts, dropping empty (NaN) fields."""
    return [
        {k: v for k, v in row.items() if pd.notna(v)}
        for row in df.to_dict("records")
    ]


def insert(coll, docs, batch=5000):
    for i in range(0, len(docs), batch):
        coll.insert_many(docs[i : i + batch], ordered=False)
    print(f"  {coll.name}: {len(docs):,} documents")


print(f"Reading {CSV_PATH} ...")
df = pd.read_csv(CSV_PATH, parse_dates=["date"])
df = df[~df["iso_code"].str.startswith("OWID_")]  # drop aggregates (World, Europe...)

# Start fresh so the script can be re-run safely
for name in ["countries", "daily_stats", "vaccinations", "hospital_stats", "users_reports"]:
    db.drop_collection(name)

# 1) countries: one doc per country, demographics EMBEDDED
print("Loading collections ...")
meta = (
    df.groupby("iso_code")
    .agg(
        location=("location", "first"),
        continent=("continent", "first"),
        population=("population", "first"),
        median_age=("median_age", "first"),
        gdp_per_capita=("gdp_per_capita", "first"),
    )
    .reset_index()
)
countries = []
for r in meta.to_dict("records"):
    demo = {k: r[k] for k in ("population", "median_age", "gdp_per_capita") if pd.notna(r[k])}
    countries.append(
        {
            "iso_code": r["iso_code"],
            "location": r["location"],
            "continent": r["continent"] if pd.notna(r["continent"]) else None,
            "demographics": demo,
        }
    )
insert(db.countries, countries)
db.countries.create_index("iso_code", unique=True)

# 2) daily_stats: TIME-SERIES collection (advanced feature)
db.create_collection(
    "daily_stats",
    timeseries={"timeField": "date", "metaField": "iso_code", "granularity": "hours"},
)
cols = ["total_cases", "new_cases", "total_deaths", "new_deaths"]
d = df[["iso_code", "date"] + cols].dropna(subset=cols, how="all")
insert(db.daily_stats, to_docs(d))

# 3) vaccinations (regular collection)
cols = ["total_vaccinations", "people_vaccinated", "people_fully_vaccinated"]
v = df[["iso_code", "date"] + cols].dropna(subset=cols, how="all")
insert(db.vaccinations, to_docs(v))

# 4) hospital_stats (regular collection)
cols = ["icu_patients", "hosp_patients", "new_tests", "total_tests"]
h = df[["iso_code", "date"] + cols].dropna(subset=cols, how="all")
insert(db.hospital_stats, to_docs(h))

# 5) users_reports: user-submitted reports (CRUD demo), seeded with samples
db.users_reports.insert_many(
    [
        {"iso_code": "PAK", "author": "demo_user", "title": "Local outbreak report",
         "body": "Cases rising in the city after the festival.", "status": "open"},
        {"iso_code": "USA", "author": "demo_user", "title": "Vaccination drive update",
         "body": "New booster clinics opened downtown.", "status": "open"},
    ]
)
print("  users_reports: 2 sample documents")

print("Done.")
