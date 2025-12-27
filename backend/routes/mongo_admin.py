"""MongoDB admin routes for import/export operations."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Any
import json
from bson import json_util, ObjectId
from utils.database import get_db

router = APIRouter(prefix="/mongo", tags=["MongoDB Admin"])


class ExportRequest(BaseModel):
    collection: str
    query: Optional[str] = "{}"  # JSON query string
    projection: Optional[str] = None  # JSON projection string
    limit: Optional[int] = 1000
    sort: Optional[str] = None  # JSON sort string, e.g. {"created_at": -1}


class ImportRequest(BaseModel):
    collection: str
    documents: str  # JSON array of documents or single document
    mode: str = "insert"  # "insert", "upsert", "replace"
    upsert_field: Optional[str] = "_id"  # Field to match for upsert


class DeleteRequest(BaseModel):
    collection: str
    query: str  # JSON query string


class AggregateRequest(BaseModel):
    collection: str
    pipeline: str  # JSON array of pipeline stages


class CollectionStats(BaseModel):
    name: str
    count: int


def parse_json_safe(json_str: str, default=None):
    """Safely parse JSON string."""
    if not json_str:
        return default
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")


@router.get("/collections")
async def list_collections():
    """List all collections with document counts."""
    db = await get_db()
    collections = await db.list_collection_names()
    
    result = []
    for name in sorted(collections):
        if not name.startswith("system."):
            count = await db[name].count_documents({})
            result.append({"name": name, "count": count})
    
    return {"collections": result}


@router.post("/export")
async def export_data(request: ExportRequest):
    """Export data from a collection."""
    db = await get_db()
    
    # Check if collection exists
    collections = await db.list_collection_names()
    if request.collection not in collections:
        raise HTTPException(status_code=404, detail=f"Collection '{request.collection}' not found")
    
    # Parse query
    query = parse_json_safe(request.query, {})
    projection = parse_json_safe(request.projection, None)
    sort_spec = parse_json_safe(request.sort, None)
    
    # Build cursor
    cursor = db[request.collection].find(query, projection)
    
    if sort_spec:
        cursor = cursor.sort(list(sort_spec.items()))
    
    if request.limit:
        cursor = cursor.limit(request.limit)
    
    # Fetch documents
    documents = await cursor.to_list(length=request.limit or 1000)
    
    # Convert to JSON-serializable format
    # Use json_util for proper ObjectId handling
    json_str = json_util.dumps(documents, ensure_ascii=False, indent=2)
    
    return {
        "collection": request.collection,
        "count": len(documents),
        "data": json_str
    }


@router.post("/import")
async def import_data(request: ImportRequest):
    """Import data into a collection."""
    db = await get_db()
    
    # Parse documents
    try:
        # Use json_util to handle MongoDB extended JSON format
        documents = json_util.loads(request.documents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    # Ensure it's a list
    if isinstance(documents, dict):
        documents = [documents]
    
    if not isinstance(documents, list):
        raise HTTPException(status_code=400, detail="Documents must be a JSON array or object")
    
    if not documents:
        raise HTTPException(status_code=400, detail="No documents to import")
    
    collection = db[request.collection]
    
    inserted = 0
    updated = 0
    errors = []
    
    if request.mode == "insert":
        # Simple insert
        try:
            result = await collection.insert_many(documents, ordered=False)
            inserted = len(result.inserted_ids)
        except Exception as e:
            errors.append(str(e))
    
    elif request.mode == "upsert":
        # Upsert based on field
        for doc in documents:
            try:
                filter_val = doc.get(request.upsert_field)
                if filter_val is None:
                    errors.append(f"Document missing upsert field '{request.upsert_field}'")
                    continue
                
                result = await collection.update_one(
                    {request.upsert_field: filter_val},
                    {"$set": doc},
                    upsert=True
                )
                if result.upserted_id:
                    inserted += 1
                elif result.modified_count:
                    updated += 1
            except Exception as e:
                errors.append(str(e))
    
    elif request.mode == "replace":
        # Replace documents based on _id
        for doc in documents:
            try:
                doc_id = doc.get("_id")
                if doc_id is None:
                    errors.append("Document missing _id for replace")
                    continue
                
                result = await collection.replace_one(
                    {"_id": doc_id},
                    doc,
                    upsert=True
                )
                if result.upserted_id:
                    inserted += 1
                elif result.modified_count:
                    updated += 1
            except Exception as e:
                errors.append(str(e))
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {request.mode}")
    
    return {
        "collection": request.collection,
        "mode": request.mode,
        "inserted": inserted,
        "updated": updated,
        "errors": errors[:10] if errors else []  # Limit error messages
    }


@router.post("/delete")
async def delete_data(request: DeleteRequest):
    """Delete documents from a collection."""
    db = await get_db()
    
    # Parse query
    query = parse_json_safe(request.query, None)
    
    if query is None or query == {}:
        raise HTTPException(status_code=400, detail="Empty query not allowed for delete. Use {\"_id\": ...} or specific filter.")
    
    collection = db[request.collection]
    
    # First count how many will be deleted
    count = await collection.count_documents(query)
    
    if count == 0:
        return {"collection": request.collection, "deleted": 0, "message": "No matching documents"}
    
    # Delete
    result = await collection.delete_many(query)
    
    return {
        "collection": request.collection,
        "deleted": result.deleted_count
    }


@router.post("/aggregate")
async def aggregate_data(request: AggregateRequest):
    """Run aggregation pipeline on a collection."""
    db = await get_db()
    
    # Parse pipeline
    pipeline = parse_json_safe(request.pipeline, None)
    
    if not isinstance(pipeline, list):
        raise HTTPException(status_code=400, detail="Pipeline must be a JSON array")
    
    collection = db[request.collection]
    
    # Run aggregation
    cursor = collection.aggregate(pipeline)
    documents = await cursor.to_list(length=1000)
    
    # Convert to JSON
    json_str = json_util.dumps(documents, ensure_ascii=False, indent=2)
    
    return {
        "collection": request.collection,
        "count": len(documents),
        "data": json_str
    }


@router.get("/stats")
async def database_stats():
    """Get database statistics."""
    db = await get_db()
    
    collections = await db.list_collection_names()
    
    stats = {
        "database": db.name,
        "collections_count": len([c for c in collections if not c.startswith("system.")]),
        "collections": []
    }
    
    for name in sorted(collections):
        if not name.startswith("system."):
            count = await db[name].count_documents({})
            stats["collections"].append({
                "name": name,
                "documents": count
            })
    
    return stats
