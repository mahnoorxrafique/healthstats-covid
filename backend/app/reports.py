"""
CRUD endpoints for user-submitted health reports (collection: users_reports),
plus full-text search using the text index on title + body.
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .db import db

router = APIRouter(prefix="/reports", tags=["Reports (CRUD + text search)"])
coll = db.users_reports


class ReportIn(BaseModel):
    iso_code: str = Field(min_length=3, max_length=3, examples=["PAK"])
    author: str = Field(min_length=1, examples=["demo_user"])
    title: str = Field(min_length=1, examples=["Vaccination camp update"])
    body: str = Field(min_length=1, examples=["New vaccination camp opened in the city."])
    status: Literal["open", "in_review", "closed"] = "open"


class ReportUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    status: Optional[Literal["open", "in_review", "closed"]] = None


def to_json(doc):
    doc["id"] = str(doc.pop("_id"))
    return doc


def to_object_id(report_id: str):
    try:
        return ObjectId(report_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Report not found")


# ---------- CREATE ----------
@router.post("", status_code=201)
def create_report(report: ReportIn):
    doc = report.model_dump()
    doc["iso_code"] = doc["iso_code"].upper()
    # Referencing: make sure the country exists in the `countries` collection
    if not db.countries.find_one({"iso_code": doc["iso_code"]}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Unknown country code")
    doc["created_at"] = datetime.now(timezone.utc)
    result = coll.insert_one(doc)
    return to_json(coll.find_one({"_id": result.inserted_id}))


# ---------- READ (list, with optional filters) ----------
@router.get("")
def list_reports(
    iso_code: Optional[str] = None,
    status: Optional[Literal["open", "in_review", "closed"]] = None,
    limit: int = Query(20, ge=1, le=100),
):
    query = {}
    if iso_code:
        query["iso_code"] = iso_code.upper()
    if status:
        query["status"] = status
    docs = coll.find(query).sort("_id", -1).limit(limit)
    return [to_json(d) for d in docs]


# ---------- TEXT SEARCH (must be declared before /{report_id}) ----------
@router.get("/search")
def search_reports(q: str = Query(..., min_length=2), limit: int = Query(20, ge=1, le=100)):
    cursor = (
        coll.find({"$text": {"$search": q}}, {"score": {"$meta": "textScore"}})
        .sort([("score", {"$meta": "textScore"})])
        .limit(limit)
    )
    return [to_json(d) for d in cursor]


# ---------- READ (one) ----------
@router.get("/{report_id}")
def get_report(report_id: str):
    doc = coll.find_one({"_id": to_object_id(report_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    return to_json(doc)


# ---------- UPDATE ----------
@router.put("/{report_id}")
def update_report(report_id: str, changes: ReportUpdate):
    update = changes.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    update["updated_at"] = datetime.now(timezone.utc)
    doc = coll.find_one_and_update(
        {"_id": to_object_id(report_id)},
        {"$set": update},
        return_document=True,  # return the document AFTER the update
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    return to_json(doc)


# ---------- DELETE ----------
@router.delete("/{report_id}")
def delete_report(report_id: str):
    result = coll.delete_one({"_id": to_object_id(report_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"deleted": report_id}
