"""
Index demo: run the SAME query before and after creating an index,
and compare the explain() results. Take screenshots of the output
for your README.

Usage (from the backend/ folder):
    python scripts/explain_demo.py
"""
import os
from datetime import datetime

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient
from pymongo.errors import OperationFailure

load_dotenv()
client = MongoClient(os.environ["MONGODB_URI"])
db = client[os.getenv("DB_NAME", "healthstats")]

COLLECTION = "vaccinations"
FILTER = {"iso_code": "PAK", "date": {"$gte": datetime(2021, 1, 1)}}
SORT = {"date": 1}
INDEX_KEYS = [("iso_code", ASCENDING), ("date", ASCENDING)]
INDEX_NAME = "iso_date_idx"


def stage_names(node):
    """Collect plan stage names (COLLSCAN, IXSCAN, SORT, FETCH...) in order."""
    found = []
    if isinstance(node, dict):
        if "stage" in node:
            found.append(node["stage"])
        for value in node.values():
            found += stage_names(value)
    elif isinstance(node, list):
        for value in node:
            found += stage_names(value)
    return found


def run_explain():
    result = db.command(
        {
            "explain": {"find": COLLECTION, "filter": FILTER, "sort": SORT},
            "verbosity": "executionStats",
        }
    )
    stats = result["executionStats"]
    plan = result["queryPlanner"]["winningPlan"]
    stages = list(dict.fromkeys(stage_names(plan)))
    return {
        "plan stages": " -> ".join(stages),
        "documents returned": stats["nReturned"],
        "index keys examined": stats["totalKeysExamined"],
        "documents examined": stats["totalDocsExamined"],
        "execution time (ms)": stats["executionTimeMillis"],
    }


def show(title, info):
    print(f"\n=== {title} ===")
    for key, value in info.items():
        print(f"  {key:22}: {value}")


coll = db[COLLECTION]
print(f"Query: {COLLECTION}.find({FILTER}).sort({SORT})")

# Make sure we start WITHOUT the index
try:
    coll.drop_index(INDEX_NAME)
    print(f"(dropped existing index '{INDEX_NAME}')")
except OperationFailure:
    pass

before = run_explain()
show("BEFORE index", before)

coll.create_index(INDEX_KEYS, name=INDEX_NAME)
print(f"\nCreated index {INDEX_NAME} on {INDEX_KEYS}")

after = run_explain()
show("AFTER index", after)

b, a = before["documents examined"], after["documents examined"]
print(f"\nDocuments examined: {b:,} -> {a:,}")
