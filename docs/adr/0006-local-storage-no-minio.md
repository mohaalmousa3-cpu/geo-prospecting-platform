# ADR-0006: Local filesystem storage first; no MinIO

- **Status:** Accepted
- **Date:** 2026-10-04
- **Decided by:** Project owner (Decision 6)

## Context
Rasters (COG), uploads and reports need storage. MinIO adds a service and an AGPL-licensed component (unverified) for no V1 benefit.

## Decision
- V1 uses a **local filesystem storage backend** under `STORAGE_LOCAL_PATH` (Docker volume / bind mount, git-ignored).
- Code accesses storage only through a `StorageBackend` interface (`put`, `get`, `exists`, `delete`, `open_path`) with a single `LocalStorage` implementation. Keys are logical (`aoi/<id>/…`), never raw user-supplied paths.
- **MinIO and S3-compatible backends are not added**, not in Compose, not in `.env.example`.
- Raster outputs use Cloud-Optimised GeoTIFF so a later object-store move is a backend swap.

## Consequences
- Path-traversal protection is mandatory in `LocalStorage` (normalise, reject `..`/absolute keys, confine to root) and tested.
- Backend and worker must share the volume; documented in Compose.
- Disk exhaustion (risk I-3) is handled by size limits and a documented cleanup script (Phase 2+).
- Supersedes the "MinIO optional" notes in earlier drafts; risk L-4 (MinIO licence) no longer applies to V1.

## Revisit when
Multi-host workers, large archives, or hosted deployment require shared object storage.
