from fastapi import FastAPI

from .analytics import router as analytics_router
from .db import db
from .reports import router as reports_router

app = FastAPI(title="HealthStats COVID API")
app.include_router(analytics_router)
app.include_router(reports_router)


@app.get("/health")
def health():
    db.command("ping")
    return {"status": "ok"}


@app.get("/countries")
def list_countries():
    return list(db.countries.find({}, {"_id": 0}).sort("location", 1))