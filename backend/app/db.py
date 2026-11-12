import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
db = client[os.getenv("DB_NAME", "healthstats")]
