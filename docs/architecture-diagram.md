# DMA Architecture Diagram

```mermaid
flowchart LR
  subgraph Client
    Dev[Developer / Agent]
  end

  Dev -->|HTTP/JSON| API[FastAPI App]
  API -->|CRUD| DocsDB[(SQLite/Postgres)]
  API -->|Embeddings| Embed[Embedding Service]
  API -->|Schedule| Sched[APScheduler]
  Sched -->|Jobs| API

  subgraph Persistence
    DocsDB
  end

  subgraph Services
    Embed
    Sched
  end
```

- API: `backend/api/main.py`, routers under `backend/api/routes/*`
- DB: async SQLAlchemy session/engine in `backend/models/base.py`
- Embeddings: `backend/services/embedding_service.py`
- Scheduler: `backend/services/scheduler.py`
- Retrieval: `backend/services/retrieval_service.py`
