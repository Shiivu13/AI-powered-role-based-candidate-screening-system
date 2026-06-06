import asyncio
from fastapi import APIRouter, BackgroundTasks
from app.ml.vector_store import get_collection_count, collection_exists_with_data, ROLES
from app.models.schemas import KnowledgeStatusOut

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/status", response_model=KnowledgeStatusOut)
async def knowledge_status():
    loop = asyncio.get_event_loop()
    collections = {}
    total = 0
    for role in ROLES:
        count = await loop.run_in_executor(None, get_collection_count, role)
        collections[role] = count
        total += count
    return KnowledgeStatusOut(
        ingested=total > 0,
        collections=collections,
        total_chunks=total,
    )


@router.post("/ingest")
async def trigger_ingest(background_tasks: BackgroundTasks):
    from scripts.ingest_knowledge import ingest_all
    background_tasks.add_task(ingest_all)
    return {"message": "Knowledge ingestion started in background"}
