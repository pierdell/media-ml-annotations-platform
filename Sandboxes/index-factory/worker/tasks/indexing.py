"""
Celery tasks for indexing images (CLIP) and documents (sentence-transformers)
into Qdrant for hybrid search.
"""
import os
import uuid
import structlog
from celery_app import app
from PIL import Image
import tiktoken

logger = structlog.get_logger()

# Lazy-loaded models
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None
_text_model = None


def _get_clip():
    global _clip_model, _clip_preprocess, _clip_tokenizer
    if _clip_model is None:
        import open_clip
        model_name = os.getenv("CLIP_MODEL_NAME", "ViT-B-32")
        pretrained = os.getenv("CLIP_PRETRAINED", "openai")
        _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
        _clip_tokenizer = open_clip.get_tokenizer(model_name)
        _clip_model.eval()
        logger.info("CLIP model loaded", model=model_name)
    return _clip_model, _clip_preprocess, _clip_tokenizer


def _get_text_model():
    global _text_model
    if _text_model is None:
        from sentence_transformers import SentenceTransformer
        _text_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Text embedding model loaded")
    return _text_model


def _get_qdrant():
    from qdrant_client import QdrantClient
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
        api_key=os.getenv("QDRANT_API_KEY", "qdrant_secret"),
    )


def _get_db_connection():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    url = os.getenv("DATABASE_URL", "postgresql://indexfactory:indexfactory_secret@localhost:5432/indexfactory")
    engine = create_engine(url)
    return Session(engine)


def _chunk_text(text: str, max_tokens: int = 256) -> list[str]:
    """Split text into chunks of ~max_tokens."""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i : i + max_tokens]
        chunks.append(enc.decode(chunk_tokens))
    return chunks


@app.task(name="worker.tasks.index_image", bind=True, max_retries=3)
def index_image(self, media_id: str, file_path: str):
    """Generate CLIP embedding for an image and upsert into Qdrant."""
    import torch
    from qdrant_client.models import PointStruct

    logger.info("Indexing image", media_id=media_id)
    try:
        model, preprocess, _ = _get_clip()
        image = Image.open(file_path).convert("RGB")
        image_tensor = preprocess(image).unsqueeze(0)

        with torch.no_grad():
            features = model.encode_image(image_tensor)
            features /= features.norm(dim=-1, keepdim=True)
        vector = features[0].tolist()

        # Upsert to qdrant
        client = _get_qdrant()
        collection = os.getenv("QDRANT_COLLECTION_IMAGE", "image_embeddings")
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, media_id))

        # Fetch media record for metadata
        db = _get_db_connection()
        row = db.execute(
            "SELECT object_id, file_name, mime_type FROM reference_media WHERE id = :id",
            {"id": media_id},
        ).mappings().first()

        payload = {
            "source_id": media_id,
            "content_type": "reference_media",
            "file_name": row["file_name"] if row else "",
            "object_id": str(row["object_id"]) if row else "",
        }
        # Get user_id through object
        if row:
            obj_row = db.execute(
                "SELECT user_id FROM objects WHERE id = :id",
                {"id": str(row["object_id"])},
            ).mappings().first()
            if obj_row:
                payload["user_id"] = str(obj_row["user_id"])

        client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

        # Mark as indexed
        db.execute(
            "UPDATE reference_media SET indexed = true WHERE id = :id",
            {"id": media_id},
        )
        db.commit()
        db.close()

        logger.info("Image indexed", media_id=media_id)
    except Exception as exc:
        logger.error("Image indexing failed", media_id=media_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)


@app.task(name="worker.tasks.index_document", bind=True, max_retries=3)
def index_document(self, document_id: str):
    """Chunk document, generate text embeddings, upsert into Qdrant."""
    from qdrant_client.models import PointStruct
    from sqlalchemy import text as sql_text

    logger.info("Indexing document", document_id=document_id)
    try:
        db = _get_db_connection()
        doc = db.execute(
            sql_text("SELECT id, user_id, title, raw_text, source_type FROM documents WHERE id = :id"),
            {"id": document_id},
        ).mappings().first()

        if not doc or not doc["raw_text"]:
            logger.warning("Document not found or empty", document_id=document_id)
            return

        # Chunk the text
        chunks = _chunk_text(doc["raw_text"])
        model = _get_text_model()
        client = _get_qdrant()
        collection = os.getenv("QDRANT_COLLECTION_TEXT", "text_embeddings")
        enc = tiktoken.get_encoding("cl100k_base")

        points = []
        for i, chunk in enumerate(chunks):
            # Store chunk in DB
            chunk_id = str(uuid.uuid4())
            token_count = len(enc.encode(chunk))
            db.execute(
                sql_text(
                    "INSERT INTO document_chunks (id, document_id, chunk_index, content, token_count, indexed) "
                    "VALUES (:id, :doc_id, :idx, :content, :tokens, true)"
                ),
                {"id": chunk_id, "doc_id": document_id, "idx": i, "content": chunk, "tokens": token_count},
            )

            # Generate embedding
            vector = model.encode(chunk).tolist()
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{i}"))
            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "source_id": document_id,
                    "chunk_id": chunk_id,
                    "chunk_index": i,
                    "content_type": "document_chunk",
                    "title": doc["title"] or "",
                    "snippet": chunk[:200],
                    "user_id": str(doc["user_id"]),
                },
            ))

        if points:
            client.upsert(collection_name=collection, points=points)

        db.execute(
            sql_text("UPDATE documents SET indexed = true WHERE id = :id"),
            {"id": document_id},
        )
        db.commit()
        db.close()

        logger.info("Document indexed", document_id=document_id, chunks=len(chunks))
    except Exception as exc:
        logger.error("Document indexing failed", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)


@app.task(name="worker.tasks.auto_categorize", bind=True, max_retries=3)
def auto_categorize(self, item_id: str, item_type: str, object_id: str):
    """
    Auto-assign categories by finding nearest ontology node embeddings.
    Uses cosine similarity between item embedding and ontology node reference embeddings.
    """
    from sqlalchemy import text as sql_text

    logger.info("Auto-categorizing", item_id=item_id, item_type=item_type)
    try:
        db = _get_db_connection()
        client = _get_qdrant()

        # Get the item's vector from qdrant
        if item_type == "reference_media":
            collection = os.getenv("QDRANT_COLLECTION_IMAGE", "image_embeddings")
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, item_id))
        else:
            collection = os.getenv("QDRANT_COLLECTION_TEXT", "text_embeddings")
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:0"))

        # Get ontology nodes for this object
        nodes = db.execute(
            sql_text("SELECT id, name FROM ontology_nodes WHERE object_id = :oid"),
            {"oid": object_id},
        ).mappings().all()

        if not nodes:
            logger.info("No ontology nodes, skipping auto-categorize", object_id=object_id)
            return

        # For each ontology node, compute similarity by encoding the node name
        model = _get_text_model()
        item_vector = None

        # Retrieve the stored vector
        try:
            results = client.retrieve(collection_name=collection, ids=[point_id], with_vectors=True)
            if results:
                item_vector = results[0].vector
        except Exception:
            pass

        if item_vector is None:
            logger.warning("Could not retrieve vector for auto-categorize", item_id=item_id)
            return

        # Score each node
        import numpy as np
        item_vec = np.array(item_vector)

        best_score = 0.0
        best_node = None

        for node in nodes:
            node_vec = np.array(model.encode(node["name"]))
            # Normalize
            if np.linalg.norm(item_vec) > 0 and np.linalg.norm(node_vec) > 0:
                sim = float(np.dot(item_vec, node_vec) / (np.linalg.norm(item_vec) * np.linalg.norm(node_vec)))
            else:
                sim = 0.0
            if sim > best_score:
                best_score = sim
                best_node = node

        if best_node and best_score > 0.3:
            assignment_id = str(uuid.uuid4())
            media_col = "reference_media_id" if item_type == "reference_media" else "document_id"
            db.execute(
                sql_text(
                    f"INSERT INTO category_assignments (id, {media_col}, ontology_node_id, confidence, assigned_by) "
                    f"VALUES (:id, :item_id, :node_id, :conf, 'auto')"
                ),
                {"id": assignment_id, "item_id": item_id, "node_id": str(best_node["id"]), "conf": best_score},
            )
            db.commit()
            logger.info("Auto-categorized", item_id=item_id, node=best_node["name"], confidence=best_score)

        db.close()
    except Exception as exc:
        logger.error("Auto-categorize failed", item_id=item_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
