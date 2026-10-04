# Data Sources (Candidates)

Status: candidates only; nothing is implemented. Access methods, licences and quotas MUST be verified at connector implementation (Phase 3). Entries reflect general knowledge (confidence: *likely*).

Default policy: open data, no paid access, cached, request-budgeted, provenance recorded.

## 1. Optical / multispectral
| Source | Use | Access | Notes |
|---|---|---|---|
| Sentinel-2 L2A (ESA/Copernicus) | Alteration indices, vegetation/cover masks | STAC (e.g. Earth Search, Planetary Computer, CDSE) | 10–20 m; free. Verify each catalogue's terms/rate limits. |
| Landsat 8/9 Collection 2 (USGS) | Multispectral, SWIR ratios, long archive | STAC / USGS / AWS open data | 30 m. |
| ASTER (NASA) | Mineral mapping (SWIR/TIR) | NASA Earthdata (free account) | Archive-limited; SWIR detectors degraded since 2008 (verify). |
| EnMAP / PRISMA hyperspectral | Mineral mapping | Agency portals (registration) | Backlog item; coverage sparse; licence terms vary. |

## 2. Thermal
| Source | Use | Access | Notes |
|---|---|---|---|
| Landsat 8/9 Collection 2 Level-2 Surface Temperature | LST (~100 m native) | STAC / USGS | Primary thermal source. Revisit 16 d (8 d combined, cloud permitting). |
| ECOSTRESS (NASA) | High-revisit LST, varied overpass times | Earthdata / AppEEARS | ~70 m; useful for diurnal analysis; coverage irregular. |
| MODIS/VIIRS LST | Coarse context | Earthdata | 375 m–1 km; context only. |
| ERA5-Land (Copernicus) | Meteorological context (air temp, radiation) | CDS API (free account) | For normalisation / confounder control. |

## 3. SAR / deformation
| Source | Use | Access | Notes |
|---|---|---|---|
| Sentinel-1 (ESA) | InSAR, backscatter | ASF DAAC, CDSE | Free. |
| ASF HyP3 | On-demand InSAR products | Earthdata account | Quota-limited; usage must be approved. |
| OPERA / ARIA products | Pre-processed products | NASA | Coverage-limited (verify). |

## 4. Terrain
| Source | Use | Access | Notes |
|---|---|---|---|
| Copernicus DEM GLO-30 | Primary DEM | AWS open data / CDSE | 30 m; surface model (includes canopy/buildings). Licence terms to verify. |
| SRTM 1 arc-sec | Fallback DEM | USGS/NASA | Older; voids in steep terrain. |
| ALOS AW3D30 | Alternative DEM | JAXA (registration; terms restrictions) | Verify licence. |
| National LiDAR / DTMs | High-res where available | Country-specific | Out of default scope; user-supplied. |
| Terrain tiles for 3D | Cesium/MapLibre terrain | Open terrain providers (e.g. AWS Terrain Tiles) | Avoid default reliance on Cesium ion. |

## 5. Geology & mineral occurrences
| Source | Use | Access | Notes |
|---|---|---|---|
| USGS MRDS / USMIN | Mineral occurrences (US) | Download/API | MRDS is no longer updated (verify). |
| OneGeology / national geological surveys (BGS, GA, BGR, etc.) | Lithology, structure | WMS/WFS/downloads | Coverage and scale vary; licences vary per survey. |
| GLiM / GMNA global lithology | Coarse lithology | Download | Coarse; context only. |
| USGS Global geochemistry / national geochemical atlases | Geochemistry | Download | Sparse, regional. |
| Macrostrat | Geologic units | API | Verify terms. |
| Known caves / karst inventories (e.g. WOKAM-type, national speleological DBs) | Void validation/context | Variable, often restricted | Sensitive data (cave locations may be protected). Handle ethically. |

## 6. Background / basemaps
OpenStreetMap-derived tiles (respect tile usage policy; prefer self-hosted or permitted providers), Natural Earth, open satellite basemaps with permissive terms. Do not use basemaps whose terms prohibit this use.

## 7. Platforms (optional connectors)
| Platform | Role | Constraint |
|---|---|---|
| Google Earth Engine | Server-side EO processing | Optional, flagged; terms (non-commercial vs commercial) and credentials need user decision; no keys in repo. |
| STAC APIs (pystac-client) | Default open catalogue access | Preferred default. |
| Microsoft Planetary Computer / AWS Open Data / CDSE | Hosted open data | Verify rate limits/terms. |

## 8. Data-source metadata required per dataset
`id`, `name`, `provider`, `version`, `licence`, `access_method`, `spatial_resolution`, `temporal_coverage`, `known_limitations`, `citation`, `retrieved_at`, `checksum` (if downloaded).

## 9. Data availability caveats
Cloud cover, coverage gaps, stale occurrence databases, differing CRSs/vertical datums, and regional licence restrictions will limit results. The platform must report `insufficient_data` instead of degrading silently.
