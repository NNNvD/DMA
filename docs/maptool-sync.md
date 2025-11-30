# MapTool Sync Integration

The DMA backend can exchange map state with a MapTool server. The adapter wraps session authentication, map fetches, token CRUD operations, and fog/light updates so the API can trigger sync actions.

## Configuration

Set the following environment variables (or add them to `.env`) to configure the adapter:

- `MAPTOOL_BASE_URL`: Base URL for the MapTool REST API (default `http://localhost:5000/api`).
- `MAPTOOL_USERNAME` and `MAPTOOL_PASSWORD`: Credentials used when an `Authorization` header is not supplied by the caller.
- `MAPTOOL_TIMEOUT_SECONDS`: Request timeout in seconds (default `10`).
- `MAPTOOL_MAX_RETRIES`: Maximum attempts for a MapTool request before surfacing an error (default `3`).

## API routes

Two API helpers are exposed under `/api/maptool`:

- `POST /api/maptool/pull`: Pull the current state of a map. Accepts `map_id` and optional `retries` in the body. If the caller provides an `Authorization` header it will be forwarded; otherwise the adapter authenticates using configured credentials. Returns a normalized campaign map payload.
- `POST /api/maptool/push`: Push token moves or note updates. Accepts `map_id`, optional `retries`, and a list of token updates. The adapter retries failed MapTool requests up to the configured limit.

Requests should include the `Authorization` header when a session token is already available. This header is forwarded directly to MapTool to avoid unnecessary login requests.
