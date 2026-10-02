# Who Eats Whom Backend Deployment Contract

## Service Basics
- **Container command**: `uvicorn main:app --host 0.0.0.0 --port 8000`
- **Port**: 8000 (container/pod listens on `0.0.0.0:8000`)
- **Health endpoint**: `GET /health` (JSON `{"status":"ok"}`)
- **API base paths**: `/api` (docs/OpenAPI) and `/api/v1` for versioned resources

## Routing Recommendation
- Configure the shared domain to proxy `https://<domain>/api` (and `/api/*`) to this backend service.
- Allow unauthenticated health probes at `https://<domain>/health` for load balancers / uptime checks.

## Environment Variables
- `APP_VERSION` *(optional)*: surfaced at `/api/v1/version`, defaults to `0.1.0`.
- `RELOAD` *(optional)*: when set to `true`, enables `uvicorn` autoreload (useful for development only).

No database credentials or third-party integrations are required in Phase 1.
