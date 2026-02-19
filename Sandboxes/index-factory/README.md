# Index Factory

A live indexation platform with hybrid semantic search. Create objects, define ontologies, ingest documents and images, and search across everything using CLIP + sentence-transformer embeddings via QDrant.

## Architecture

```
                    ┌─────────┐
                    │  nginx  │ :80
                    └────┬────┘
                   ┌─────┴──────┐
              ┌────┴────┐  ┌────┴────┐
              │ frontend │  │   api   │ :8000
              │ (React)  │  │(FastAPI)│
              └──────────┘  └────┬────┘
                           ┌─────┴──────┐
                      ┌────┴────┐  ┌────┴────┐
                      │rabbitmq │  │  redis   │
                      └────┬────┘  └─────────┘
                      ┌────┴────┐
                      │ worker  │ (Celery)
                      │ (CLIP)  │
                      └────┬────┘
                 ┌─────────┴──────────┐
            ┌────┴────┐          ┌────┴────┐
            │postgres │          │ qdrant  │
            │  (SQL)  │          │(vectors)│
            └─────────┘          └─────────┘
```

## Tech Stack

| Layer          | Technology                                    |
|----------------|-----------------------------------------------|
| Frontend       | React 18, TypeScript, Tailwind CSS, Vite      |
| Backend API    | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2  |
| Auth           | JWT (python-jose), bcrypt                     |
| Task Queue     | Celery + RabbitMQ (broker) + Redis (backend)  |
| Vector DB      | QDrant v1.12 (HNSW index, cosine distance)    |
| Relational DB  | PostgreSQL 16 (with pg_trgm for fuzzy search) |
| Image Embed    | OpenCLIP ViT-B/32 (512-dim vectors)           |
| Text Embed     | all-MiniLM-L6-v2 (384-dim vectors)            |
| Reverse Proxy  | Nginx                                         |

## Quick Start

```bash
# 1. Copy env file
cp .env.example .env

# 2. Launch all services
docker compose up -d --build

# 3. Open the app
open http://localhost
```

## Services

| Service     | Port  | Description                            |
|-------------|-------|----------------------------------------|
| nginx       | 80    | Reverse proxy (SPA + API)              |
| frontend    | 3000  | React dev server                       |
| api         | 8000  | FastAPI backend                        |
| postgres    | 5432  | Relational database                    |
| qdrant      | 6333  | Vector database (REST + gRPC:6334)     |
| rabbitmq    | 5672  | Message broker (mgmt UI: 15672)        |
| redis       | 6379  | Cache + Celery result backend          |
| worker      | -     | Celery workers (2 replicas, 4G each)   |

## API Endpoints

### Auth
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Get JWT token
- `GET  /api/auth/me` - Current user info

### Objects
- `GET    /api/objects/` - List user's objects
- `POST   /api/objects/` - Create object
- `GET    /api/objects/:id` - Get object
- `PATCH  /api/objects/:id` - Update object
- `DELETE /api/objects/:id` - Delete object

### Ontology
- `GET    /api/objects/:id/ontology` - List ontology tree
- `POST   /api/objects/:id/ontology` - Add node
- `PATCH  /api/objects/:id/ontology/:nodeId` - Update node
- `DELETE /api/objects/:id/ontology/:nodeId` - Delete node

### Media
- `GET  /api/media/:objectId` - List reference media
- `POST /api/media/:objectId/upload` - Upload image/video
- `DELETE /api/media/:objectId/:mediaId` - Delete media

### Documents
- `GET    /api/documents/` - List documents
- `POST   /api/documents/` - Create document (text/url)
- `POST   /api/documents/upload` - Upload file (PDF, MD, TXT)
- `GET    /api/documents/:id` - Get document
- `GET    /api/documents/:id/chunks` - Get document chunks
- `DELETE /api/documents/:id` - Delete document

### Search
- `POST /api/search/` - Hybrid search (text, image, or both)

### Categories
- `GET    /api/categories/` - List assignments
- `POST   /api/categories/` - Create assignment
- `PATCH  /api/categories/:id/confirm` - Confirm auto-assignment
- `DELETE /api/categories/:id` - Delete assignment

## Indexing Pipeline

1. **Image upload** -> Celery task `index_image`:
   - Load image with PIL
   - Generate 512-dim CLIP embedding (ViT-B/32)
   - Upsert to QDrant `image_embeddings` collection
   - Mark `reference_media.indexed = true`

2. **Document creation** -> Celery task `index_document`:
   - Chunk text into ~256 token segments (tiktoken)
   - Store chunks in `document_chunks` table
   - Generate 384-dim embeddings (all-MiniLM-L6-v2)
   - Upsert to QDrant `text_embeddings` collection
   - Mark `documents.indexed = true`

3. **Auto-categorize** -> Celery task `auto_categorize`:
   - Retrieve item vector from QDrant
   - Encode each ontology node name as text vector
   - Compute cosine similarity
   - Assign to best-matching node if score > 0.3

## Hybrid Search

The search endpoint supports three modes:

- **text** - Encodes query with sentence-transformers, searches `text_embeddings`
- **image** - Encodes query with CLIP text encoder, searches `image_embeddings`
- **hybrid** - Combines both, deduplicates, sorts by score

## Development

```bash
# Backend (hot reload)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (hot reload)
cd frontend
npm install
npm run dev

# Worker
cd worker
pip install -r requirements.txt
celery -A celery_app worker --loglevel=info -Q default,indexing,embedding
```

## Database Schema

7 tables with UUID primary keys, foreign key cascades, and trigram indexes:

- `users` - Authentication
- `objects` - Top-level entities (e.g. "Trees")
- `ontology_nodes` - Hierarchical properties (self-referential)
- `reference_media` - Uploaded images/videos
- `documents` - Ingested text sources
- `document_chunks` - Chunked text for embedding
- `category_assignments` - Object-category mappings (auto/manual)

## Tests

```bash
python -m unittest tests/test_structure.py -v
```

40 structural validation tests covering:
- File presence and project structure
- Docker compose services and volumes
- SQL schema tables, indexes, and foreign keys
- Python syntax validation (AST parsing)
- Model field completeness
- API route coverage
- Frontend config and type definitions
- TypeScript bracket balance
- Dockerfile and requirements validation
