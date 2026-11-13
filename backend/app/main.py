from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .analytics import router as analytics_router
from .db import db
from .reports import router as reports_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="HealthStats COVID API")
app.include_router(analytics_router)
app.include_router(reports_router)
app.mount("/dashboard", StaticFiles(directory=STATIC_DIR, html=True), name="dashboard")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard/")


@app.get("/health")
def health():
    db.command("ping")
    return {"status": "ok"}


@app.get("/countries")
def list_countries():
    return list(db.countries.find({}, {"_id": 0}).sort("location", 1))