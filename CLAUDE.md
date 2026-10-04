# CLAUDE.md — Operating Rules for AI-Assisted Work

These rules are mandatory for every Claude session on this repository. If a user instruction conflicts with the **Scientific Safety Rules**, stop and raise the conflict instead of complying silently.

## 1. Mandatory Reading Order (before ANY task)

1. `CLAUDE.md` (this file)
2. `docs/scientific-constraints.md`
3. `MASTER_SPEC.md`
4. `TASKS.md` — identify the **current phase** and the specific task
5. `docs/acceptance-criteria.md` — the section for the current phase
6. `docs/adr/README.md` and every ADR relevant to the task — accepted ADRs are binding
7. `docs/architecture.md` and `docs/dependency-strategy.md` — if the task touches structure or dependencies
8. `docs/risk-register.md` — if the task touches anything flagged there
9. `docs/phase-1-plan.md` (or the current phase's plan) when working on that phase
10. Relevant `README.md` in the directory you will modify

State in your first message which phase/task you are working on. If it is unclear, ask.

## 1a. Binding Decisions (ADR-0001 … ADR-0011)

Do not contradict these without a superseding ADR approved by the owner:

- Repo is **private**, rights reserved; no licence chosen; no vendored third-party source (0001, 0002).
- Gold model = **orogenic only**, with applicability gate; never generalise to "gold" (0003).
- **Earth Engine**: optional, flag off by default, experimental/non-commercial only, never in CI, never a hard dependency, no credentials in repo (0004).
- **No authentication** in V1; local/loopback only; do not add auth, accounts or public-exposure config (0005).
- **Local filesystem storage** via `StorageBackend`; do not add MinIO/S3 (0006).
- **PostgreSQL-backed queue** via `JobQueue`; do not add Redis/Celery/RQ (0007).
- **MVP limits** from ADR-0008 enforced server-side; do not raise them to make something work (0008).
- `packages/pycommon` (`geo_common`) holds only shared contracts, schemas, queue/storage abstractions, shared config and generic utilities — **never analysis logic** (0011).
- **Phase 5 scientific design must not begin** until the owner defines the target country/region and pilot area (0003 amendment).
- Geophysics can at most raise a target to *high-confidence investigation priority*, never confirmed (0010 amendment). AOI/upload limits are provisional operational safeguards, not scientific thresholds (0008).
- EE must stay optional/replaceable; the account owner must validate commercial eligibility before operational use (0004 amendment).
- **Naming/envelope rules** of ADR-0009 and **no "confirmed" wording** per ADR-0010; `validation_status` is always `unvalidated` in V1.

## 2. Phase-by-Phase Development

- Work on **one phase at a time**, in order. Never implement a later phase's features "while you're there".
- Work only on tasks listed in `TASKS.md` for the current phase. New ideas go to the *Backlog* section of `TASKS.md`, not into code.
- A phase is complete only when every acceptance criterion in `docs/acceptance-criteria.md` is met **and** the user has confirmed. Tick boxes in `TASKS.md` only for work actually verified.
- Do not stub scientific engines with fake or placeholder results that look real. Unimplemented = raises `NotImplementedError` / returns an explicit "not available" state.

## 3. Git Discipline

- Develop on the branch assigned for the session; never push to `main` directly.
- Small, focused commits; imperative subject (≤72 chars), body explains *why*.
- Prefix commits with the phase: `phase-1: add FastAPI health endpoint`.
- Never commit secrets, data dumps, credentials, large binaries, or generated artefacts (see `.gitignore`).
- Do not rewrite shared history. Do not open a pull request unless asked.
- Before committing: run linters and tests relevant to the change; mention anything not run.

## 4. Scientific Safety Rules (non-negotiable)

1. NEVER claim, imply, or label anything as **confirmed gold** based on satellite/remote-sensing data alone.
2. NEVER claim, imply, or label anything as a **confirmed cave/void** based on thermal or satellite data alone.
3. Remote-sensing and thermal outputs are **prospectivity/anomaly layers**. Name variables, columns, UI strings, and docs accordingly (`gold_prospectivity_score`, `void_evidence_score`, `thermal_anomaly` — never `gold_found`, `cave_detected`).
4. NEVER show or compute **subsurface depth** unless derived from uploaded field geophysics or direct verification; label method and uncertainty.
5. Every result carries **confidence and uncertainty**. A result without them must not be exposed by the API.
6. Every target carries **explanation and source metadata** (dataset, version, date, parameters, code version).
7. Do not invent scientific facts, thresholds, coefficients, or citations. If a value is needed, mark it `TODO(science-review)` and document the assumption; never present a guess as established.
8. Do not tune parameters to make demos look good. Report failures and low-confidence outcomes honestly.
9. "Insufficient data" is a valid and preferred output over a fabricated one.

## 5. Cost Controls

- Default to **free / open-source** tools and data. Paid services must be marked *optional* and disabled by default.
- Do not call paid or quota-limited APIs (including Earth Engine at scale) without explicit user approval.
- Every pipeline must have **bounded compute**: AOI area limit, time-window limit, max scenes, timeouts. No unbounded loops over large archives.
- Prefer cloud-optimised formats (COG, Zarr) and server-side reductions to avoid large downloads.
- Do not add always-on cloud infrastructure. Local Docker Compose is the default.
- Earth Engine usage (when ever enabled) stays within free quotas and non-commercial scope (ADR-0004); no billing-enabled projects without approval.
- Enforce the ADR-0008 limits in the backend; never only in the UI.
- Never assume unlimited CPU/RAM/disk; document expected resource use for heavy steps.

## 6. Architecture Discipline

- Follow `docs/architecture.md`. Deviations require an ADR in `docs/adr/` approved by the user.
- Keep modules decoupled: frontend ↔ API ↔ queue ↔ workers. Workers never import API code; language-neutral contracts live in `packages/schemas/`, shared Python code in `packages/pycommon/` (ADR-0011).
- Each third-party scientific tool is wrapped behind an internal interface (see `docs/dependency-strategy.md`).
- Check licences before adding any dependency; record it in `docs/dependency-strategy.md`.
- Configuration via environment variables (`.env.example` documents all). No hard-coded secrets, paths or endpoints.
- No speculative abstractions; build only what the current phase needs.

## 7. Testing Requirements

- Every code change ships with tests proportionate to risk: unit tests for logic, integration tests for API/DB/queue boundaries.
- **Scientific tests** (`tests/scientific/`): deterministic fixtures with documented expected behaviour; tests asserting that results always include confidence, uncertainty, explanation and sources; tests asserting forbidden claims cannot be emitted.
- Tests must be deterministic and runnable offline (mock external data sources; no live Earth Engine in CI).
- Never disable, skip, or weaken a test to get green. Fix the cause or report it.
- Report exactly what was run and the result. If tests were not run, say so.

## 8. Security and Data Handling

- V1 has no authentication (ADR-0005): bind services to `127.0.0.1`, keep CORS allow-listed, never document or configure public exposure.
- Validate and sanitise all uploads (size, type, zip-bomb, path traversal, geometry validity).
- No secrets in code, logs, docs, or commits. Use `.env` (git-ignored) and `.env.example` (placeholders only).
- Treat user AOIs and uploads as potentially sensitive; no third-party sharing.

## 9. Communication Style

- Be direct and precise. Lead with the most important fact, including uncomfortable ones (limits, risks, failures).
- State confidence for key claims: **confirmed** (strong evidence), **likely** (strong inference), **guess** (gap-filling).
- No flattery or filler. Disagree explicitly when warranted, give the reason and the alternative.
- Distinguish clearly between what was done, what was verified, and what was assumed.
- Ask for approval before: new dependencies with copyleft licences, paid services, architecture changes, scope changes, anything in the *Open Questions* list.
- Summaries: files changed, decisions made, what was tested, open questions.

## 10. Prohibitions (summary)

- ❌ Claiming confirmed results from remote sensing alone
- ❌ Fake/placeholder scientific outputs presented as real
- ❌ Building beyond the current phase
- ❌ Committing secrets or large data
- ❌ Adding paid dependencies by default
- ❌ Skipping tests or provenance
- ❌ Silent architecture changes
