import asyncio
import chromadb
from app.config import settings

ROLES = ["ai_ml", "data_science", "backend"]
COLLECTION_PREFIX = "interview_kb"

_chroma_client: chromadb.PersistentClient = None
_embedder = None


def _get_embedder():
    """Local all-MiniLM-L6-v2 embedder — no per-query API quota (robust at runtime).

    Prefers ChromaDB's built-in ONNX runtime (lightweight, ~200MB — fits small free
    tiers like Render). Falls back to a torch implementation of the *same* model if
    onnxruntime can't load (e.g. a Windows DLL issue locally). Both produce identical
    384-dim vectors, so a vector store built with one is queryable by the other.
    """
    global _embedder
    if _embedder is None:
        try:
            from fastembed import TextEmbedding
            # Cache in a project-relative dir so the model baked in at build time
            # is reused at runtime (no slow/flaky download on first request).
            model = TextEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                cache_dir="fastembed_cache",
            )

            def encode(texts: list[str]) -> list[list[float]]:
                return [list(map(float, v)) for v in model.embed(list(texts))]

            encode(["warmup"])  # force model download/load so failures surface here
            _embedder = encode
        except Exception as onnx_err:
            print(f"[embedder] fastembed unavailable ({onnx_err}); falling back to torch MiniLM", flush=True)
            _embedder = _torch_embedder()
    return _embedder


def _torch_embedder():
    from transformers import AutoTokenizer, AutoModel
    import torch
    import torch.nn.functional as F

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()

    def encode(texts: list[str]) -> list[list[float]]:
        with torch.no_grad():
            enc = tokenizer(list(texts), padding=True, truncation=True, max_length=256, return_tensors="pt")
            out = model(**enc)
            mask = enc["attention_mask"].unsqueeze(-1).float()
            emb = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            emb = F.normalize(emb, p=2, dim=1)
        return emb.numpy().tolist()

    return encode


def _get_chroma():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
    return _chroma_client


def _collection_name(role: str) -> str:
    return f"{COLLECTION_PREFIX}_{role}"


def get_or_create_collection(role: str):
    client = _get_chroma()
    return client.get_or_create_collection(
        name=_collection_name(role),
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(role: str, chunks: list[str], ids: list[str], metadatas: list[dict] = None):
    col = get_or_create_collection(role)
    encode = _get_embedder()
    embeddings = encode(chunks)
    col.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas or [{} for _ in chunks],
        embeddings=embeddings,
    )


def query_knowledge(role: str, query: str, n_results: int = 5) -> list[str]:
    col = get_or_create_collection(role)
    count = col.count()
    if count == 0:
        return []
    n_results = min(n_results, count)
    encode = _get_embedder()
    query_embedding = encode([query])
    results = col.query(query_embeddings=query_embedding, n_results=n_results)
    return results["documents"][0] if results["documents"] else []


# Pretty names for the source books (for the glass-box / explainable-RAG panel)
SOURCE_LABELS = {
    "tom_mitchell_ml.pdf": "Machine Learning — Tom Mitchell",
    "burkov_hundred_page_ml.pdf": "The Hundred-Page ML Book — Burkov",
    "intro_ml_python.pdf": "Intro to ML with Python — Müller & Guido",
}


def _pretty_source(filename: str) -> str:
    if not filename:
        return "Knowledge Base"
    if filename in SOURCE_LABELS:
        return SOURCE_LABELS[filename]
    # Fall back to a humanised filename for curated .txt notes
    return filename.replace("_", " ").replace(".txt", "").replace(".pdf", "").title()


def query_knowledge_detailed(role: str, query: str, n_results: int = 5) -> list[dict]:
    """Returns retrieval hits with source attribution + similarity for the glass-box panel."""
    col = get_or_create_collection(role)
    count = col.count()
    if count == 0:
        return []
    n_results = min(n_results, count)
    encode = _get_embedder()
    query_embedding = encode([query])
    results = col.query(query_embeddings=query_embedding, n_results=n_results)

    docs = results["documents"][0] if results["documents"] else []
    metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
    dists = results["distances"][0] if results.get("distances") else [None] * len(docs)

    hits = []
    for doc, meta, dist in zip(docs, metas, dists):
        source_file = (meta or {}).get("source", "")
        similarity = round(1 - dist, 3) if dist is not None else None  # cosine distance -> similarity
        hits.append({
            "book": _pretty_source(source_file),
            "source_file": source_file,
            "snippet": doc[:240].strip(),
            "text": doc,
            "similarity": similarity,
        })
    return hits


async def async_query_knowledge(role: str, query: str, n_results: int = 5) -> list[str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query_knowledge, role, query, n_results)


def get_collection_count(role: str) -> int:
    try:
        col = get_or_create_collection(role)
        return col.count()
    except Exception:
        return 0


def collection_exists_with_data(role: str) -> bool:
    return get_collection_count(role) > 0
