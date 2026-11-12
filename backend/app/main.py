from fastapi import FastAPI
from .db import db

app = FastAPI(title="HealthStats COVID API")


@app.get("/health")
def health():
    db.command("ping")
    return {"status": "ok"}


@app.get("/countries")
def list_countries():
    return list(db.countries.find({}, {"_id": 0}).sort("location", 1))
