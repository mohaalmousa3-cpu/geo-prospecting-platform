# Dependency & Open-Source Reuse Strategy

Principles: prefer free/open source; integrate via library/CLI behind internal interfaces; isolate heavy stacks in separate worker images; pin versions; review licences **before** adoption.

> **Licence caveat:** licences below are from general knowledge (confidence: *likely*, not verified in this session). Each MUST be re-verified against the upstream repository at adoption time and recorded in the table with date and commit/tag.

## 1. Candidate scientific tools

| Tool | Role | Likely licence | Integration approach | Phase | Notes / risks |
|---|---|---|---|---|---|
| **EIS Toolkit** | Mineral prospectivity workflows (evidence layers, ML/weights) | EUPL-1.2 (verify) | Python library in gold/void worker image | 5–6 | Copyleft (EUPL); assess compatibility with chosen repo licence. API maturity and maintenance to be checked. |
| **EnMAP-Box** | Hyperspectral/EO analysis (QGIS plugin) | GPL-3.0 (verify) | Reuse *concepts*; use underlying independent libs only where licence permits. Do not embed the QGIS GUI. | 5+ | Hard dependency on QGIS; likely unsuitable as a direct server dependency. |
| **Landsat LST workflows** | Land surface temperature | Data: USGS public domain; code: varies | Prefer USGS Collection 2 Level-2 ST product; implement own thin processing | 4 | Do not copy code without checking its licence. Algorithms from peer-reviewed literature; cite. |
| **MintPy** | InSAR time-series | GPL-3.0 (verify) | Separate optional worker image; CLI invocation; **off by default** | 6 (optional) | Needs interferograms (ISCE/ARIA/HyP3 products); heavy compute/storage; GPL implications if linked. Prefer process isolation (CLI) over linking. |
| **pyGIMLi** | Geophysical modelling/inversion | Apache-2.0 (verify) | Geophysics worker | 8 | Complex install (C++ deps); pin conda env. |
| **ResIPy** | ERT/IP processing & inversion | GPL-3.0 (verify) | Geophysics worker; wraps R2/cR2 executables | 8 | Wraps third-party executables whose licences/redistribution terms must be checked separately. |
| **GPRPy** | GPR processing | MIT (verify) | Geophysics worker | 8 | Maintenance activity to be checked. |
| **GemPy** | 3D geological modelling | EUPL-1.2 (verify) | Optional separate worker | 8+ | Heavy deps (PyTorch/Theano-type stacks historically); optional. |

## 2. Platform dependencies

| Component | Licence (likely) | Notes |
|---|---|---|
| Next.js / React | MIT | |
| FastAPI / Pydantic / Starlette | MIT | |
| SQLAlchemy / Alembic | MIT | |
| PostgreSQL / PostGIS | PostgreSQL / GPL-2.0+ (PostGIS) | Used as a separate service (no linking issue). |
| MapLibre GL JS | BSD-3-Clause | |
| CesiumJS | Apache-2.0 | Cesium ion (hosted terrain/imagery) is a **paid/limited-tier service — optional**; default to open terrain sources. |
| GDAL / Rasterio / Shapely / pyproj | MIT/X, BSD | |
| ~~Redis~~ | **Not used in V1** (ADR-0007: PostgreSQL-backed queue) | Licence question closed for V1. |
| ~~MinIO~~ | **Not used in V1** (ADR-0006: local filesystem) | Licence question closed for V1. |
| Docker / Compose | Apache-2.0 | |

## 3. Licence strategy

- Copyleft tools (GPL/EUPL/AGPL) are run as **separate processes/images** communicating via files, CLI or queue, to limit propagation. *Whether this suffices legally is a question for qualified legal review* — not decided here.
- The repository is private with rights reserved and **no open-source licence is chosen** (ADR-0001, ADR-0002). Never vendor third-party source into this repo.
- Internal use differs from distribution: publication, hosting for third parties, or distributing images changes the licence analysis (network-use clauses of EUPL/AGPL-type licences: confidence *guess*; get qualified legal review before any external exposure).
- Maintain `docs/third-party-licences.md` (created in Phase 1, task P1-12) listing: name, version, licence, how used, link, verification date.

## 4. Wrapping rule

Each third-party scientific tool is accessed only through an internal adapter (`workers/<engine>/adapters/`). Benefits: swap-ability, pinned behaviour, uniform provenance capture, easier testing with mocks.

## 5. Version pinning and environments

- Python: lockfile per worker (uv/pip-tools/conda-lock; choice via ADR). Geo stacks with compiled deps likely need conda/mamba base images.
- Node: lockfile committed; engines field set.
- Record resolved versions in provenance of every run.

## 6. Adding a dependency — checklist

1. Is it necessary for the current phase?
2. Free/open? If paid/quota-limited → mark optional, off by default.
3. Licence verified and recorded? Copyleft → user approval.
4. Maintained (recent releases, active issues)?
5. Install footprint acceptable? Isolated image if heavy?
6. Wrapped behind an adapter? Mockable offline?

## 7. Cost-related options (all optional, default off)

- **Google Earth Engine** — approved only for experimental / non-commercial use, flag-off by default, behind the connector interface (ADR-0004). Commercial use is **not** covered; verify current terms before first use (confidence the free tier is non-commercial only: *likely*).
- Cesium ion, commercial imagery/SAR, managed cloud services — not approved.
