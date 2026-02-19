# Media ML Annotations Platform

Monorepo containing the annotation platform and experimental sandboxes.

## Structure

```
.
├── AnnotationPlatform/    # Production annotation platform
│   ├── backend/           # FastAPI backend (auth, projects, datasets, ML)
│   ├── frontend/          # Vanilla JS annotation UI
│   ├── worker/            # Celery workers (CPU + GPU)
│   ├── docker-compose.yml
│   └── ...
│
└── Sandboxes/             # Experimental toy examples
    └── index-factory/     # Live indexation platform with hybrid search
        ├── backend/       # FastAPI + SQLAlchemy (async)
        ├── frontend/      # React + TypeScript + Tailwind
        ├── worker/        # Celery + CLIP + sentence-transformers
        └── docker-compose.yml
```

## Sandboxes

### index-factory

A self-contained live indexation platform built with:

- **PostgreSQL** + **QDrant** for hybrid storage
- **CLIP** (ViT-B/32) for image embeddings
- **sentence-transformers** for text embeddings
- **React + TypeScript** frontend with dark theme
- **RabbitMQ + Celery** for async task processing

See [Sandboxes/index-factory/README.md](Sandboxes/index-factory/README.md) for details.
