from fastapi import APIRouter, Query

from . import pipelines
from .db import db

router = APIRouter(prefix="/analytics", tags=["Analytics (aggregations)"])


def run(collection, pipeline):
    return list(db[collection].aggregate(pipeline, allowDiskUse=True))


@router.get("/top-countries")
def top_countries(limit: int = Query(10, ge=1, le=100)):
    """Pipeline 1: countries with the most cases per million people."""
    return run("daily_stats", pipelines.top_countries(limit))


@router.get("/monthly-trend/{iso_code}")
def monthly_trend(iso_code: str):
    """Pipeline 2: new cases and deaths per month for one country (e.g. PAK)."""
    return run("daily_stats", pipelines.monthly_trend(iso_code.upper()))


@router.get("/continent-fatality")
def continent_fatality():
    """Pipeline 3: case fatality rate per continent."""
    return run("daily_stats", pipelines.continent_fatality())


@router.get("/moving-average/{iso_code}")
def moving_average(iso_code: str):
    """Pipeline 4: 7-day moving average of new cases (uses $setWindowFields)."""
    return run("daily_stats", pipelines.moving_average(iso_code.upper()))


@router.get("/vaccination-vs-deaths")
def vaccination_vs_deaths():
    """Pipeline 5: vaccination coverage vs deaths per million, per country."""
    return run("daily_stats", pipelines.vaccination_vs_deaths())


@router.get("/peak-waves")
def peak_waves(limit: int = Query(10, ge=1, le=100)):
    """Pipeline 6: the worst day (peak new cases) per country."""
    return run("daily_stats", pipelines.peak_waves(limit))
