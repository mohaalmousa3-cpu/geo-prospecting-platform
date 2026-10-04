# Acceptance Reconciliation — Phases 0, 1, 2, 2.5

Date: 2026-10-04 (verification rounds) · updated 2026-10-05 (owner decisions D-1…D-6 recorded in §2a; evidence for commit `5ac5a27` in §3 and §4b) · Base commit of the verification rounds: `da90ce2b7051dc650dfcb4247155a4eccbf4a8f0` (branch `docs/status-refresh-adr-0013`). Sections 4–7 record local verification on the **dirty working tree** over that base (before the commit that contains this file). CI evidence for commit `5ac5a27` (run #11) is recorded in §3; the CI result of the later documentation-only commit that records the 2026-10-05 decisions is **not** recorded here (a commit cannot cite its own run).

> **What this document is — and is not.** It is **not** itself an acceptance: owner acceptance exists only as the owner's decisions transcribed in §2 and §2a. It records, per criterion, what was implemented, what was verified (and where), what the owner decided (as transcribed), and what is still open. After the owner's decisions of 2026-10-05 only the checkboxes those decisions support were ticked (listed in §2a). The local runs in §4–§4a are **not** CI evidence for any committed SHA. Phase 3 remains: *Planned — blocked pending an explicit start instruction, an explicit owner decision on ADR-0014 (Proposed) and decision D8 (OPEN); prerequisite-phase acceptance decisions recorded 2026-10-05; plan approved with constraints; implementation not started.* ADR-0014 is Proposed and non-binding; decision D8 is OPEN.

Four kinds of statement are kept apart throughout:

| Label | Meaning |
|---|---|
| **IMPL** | Implementation evidence — code/docs that exist (commit SHA). |
| **VERIF** | Verification evidence — a check that was run, with scope (CI run + SHA, or a local run on a stated tree). |
| **OWNER** | Owner decision — **as transcribed** (see §2). |
| **GAP** | Unresolved gap or blocker. |

## 1. Scope of the working tree verified in this round

Base `da90ce2`; uncommitted at the time of verification:

- Documentation: `CLAUDE.md`, `MASTER_SPEC.md`, `README.md`, `TASKS.md`, `docs/acceptance-criteria.md`, `docs/phase-reports/phase-2.5.md`, this file, `docs/phase-3-plan.md`, `docs/adr/README.md`, `docs/adr/0014-connectors-package-and-data-assets.md` (status wording only; design unchanged).
- Tests: `apps/backend/tests/test_aoi_upload_limits.py` (upload/archive boundary tests), `tests/unit/test_audit_deps.py` (audit-gate classification and CI wiring), regression cases in `tests/scientific/test_guards.py`.
- Tooling/CI (second round): `scripts/audit_deps.py` and `make audit` (dependency-audit gate), `.github/workflows/ci.yml` (audit job rewritten; **and** push trigger extended with `docs/**` — see §7a), `tests/scientific/forbidden_terms.py` (guard hardening).
- **No application or production-source change**: `apps/*/src`, `packages`, `workers`, `infrastructure` are byte-identical to `HEAD` (checked with `git diff --quiet HEAD -- …`). The two production files that were temporarily mutated for the boundary-test mutation check (`apps/backend/src/app/api/aois.py`, `apps/backend/src/app/aoi/archive.py`) were restored with per-file `git checkout -- <file>` and are identical to their `HEAD` blobs (`git hash-object` equals `git rev-parse HEAD:<file>`); no broad checkout/reset was used.

## 2. Owner decisions — transcriptions, not signed records

**Every row below is a transcription made by Claude from the owner's chat messages.** The repository contains no owner-authored, signed or independently timestamped acceptance record. The quoted text is as retained in the session (elisions marked `…`); where the repo mentions the decision, the file is named. Treat all of it as *the best available record*, not as an independent attestation.

| # | Decision (owner message, quoted) | Recorded in repo at | Effect |
|---|---|---|---|
| T1 | "Approved with decisions below. Update the repository documentation before any application code work." (ten scope decisions) | ADR-0001…0010 ("Decided by: Project owner"), `TASKS.md` Phase 0 | Scope decisions; **no explicit Phase 0 acceptance statement** |
| T2 | "Approved to proceed with Phase 1 foundation work only." (plus T8 → ADR-0011 and amendments) | ADR-0011, amendments to ADR-0003/0004/0008/0010, `TASKS.md` | Approval of the Phase 1 plan, not acceptance of Phase 1 |
| T3 | "Phase 1 is accepted with follow-up checks, not fully closed yet." | `phase-1.md` status line, `phase-1-closeout.md` §1–2 | Phase 1 accepted **with follow-up checks** |
| T4 | "Phase 2 is approved with follow-up items. Do not start Phase 3 yet. Instead, implement a small Phase 2.5 …" | `phase-2.md` status line | Phase 2 approved **with follow-up items**; Phase 2.5 authorised |
| T5 | "Phase 2.5 is approved, with two required follow-ups before Phase 3 …" (browser smoke test in CI; default basemap `none`) | `phase-2.5.md` status line and §6, ADR-0013 amendment | Phase 2.5 **conditionally** approved |
| T6 | "Approved with constraints. Proceed only with planning refinements, not implementation …" (Phase 3 plan) | `docs/phase-3-plan.md`, ADR-0014 status | Plan approved with constraints; ADR-0014 stays Proposed. **Not** acceptance of any earlier phase and **not** authorisation to start |
| T7 | "Preserve MASTER_SPEC §10 unchanged. Phase 3 remains planned but BLOCKED pending reconciliation and recorded acceptance of prerequisite phases, including the Phase 2.5 follow-ups. Approval of the Phase 3 plan is not authorization to start implementation." | `MASTER_SPEC.md` (Current Project Status), `TASKS.md`, `README.md`, `docs/phase-3-plan.md` | Phase 3 blocked |
| T8 | "I authorize one bounded acceptance-reconciliation and verification round. This is NOT phase acceptance and NOT authorization to start Phase 3." | this document | Scope of this round |

**No owner message found or transcribed** records: (a) an explicit owner decision that the two Phase 2.5 follow-ups meet the owner's requirement; (b) a Phase 0 acceptance; (c) the owner ticking any checklist box.

## 2a. Owner decisions of 2026-10-05 — faithful transcription (D-1 … D-6)

**Transcription by Claude of the owner's chat message of 2026-10-05; not an independent signed record** (the owner stated that no additional formal signature is needed). Baseline named by the owner: `5ac5a278a9b93aaab4877e7ef84aa2640ff94b7c`. The owner relied on the CI run #11 report and the clean-checkout Compose verification of that commit, "with the limits of the evidence stated". Original text (Arabic), verbatim:

> D-1 — قبول بقيود: أقبل متابعتَي المرحلة 2.5: اختبار المتصفح في CI، وbasemap الافتراضي none. وأقبل إضافة CORS المشتقة ضمن نطاقها الموثق. هذا يغلق بوابة قبول المرحلة 2.5، ولا يعني تغطية شاملة لكل تفاعلات الواجهة أو النصوص المعروضة وقت التشغيل.
>
> D-2 — قبول ضمن النطاق التاريخي: أعتبر معيار "لا كود تطبيقي" مستوفى عند ca2d4e4، وليس شرطاً على HEAD الحالي. أقبل المرحلة 0 ضمن نطاق التخطيط والتأسيس التاريخي. لا تعتبر ذلك إثباتاً بأن كل الوثائق الحالية خالية من التناقضات.
>
> D-3 — قبول: أعتبر الأدلة المبلّغ عنها كافية لقبول البنود الثلاثة المفتوحة في المرحلة 1 وبند CI في TASKS. تشغيل Compose من نسخة نظيفة كافٍ ضمن الفحوص المنفذة. لا أطلب جولة تحقق عامة إضافية.
>
> D-4 — قبول محدد: أقبل إغلاق فجوة اختبارات حدود الرفع والأرشيف التي عالجتها الاختبارات الجديدة المرتكبة والمبلّغ عن نجاحها في CI #11. لا تستنتج من اختبارات الرفع والأرشيف وحدها استيفاء معيار CRS/الحدود المركب كله. إذا كان صندوق الاختيار يشمل جوانب أخرى، اربطها بأدلتها القائمة؛ وأبقِ أي جانب غير مدعوم مفتوحاً.
>
> D-5 — قبول: أقر تقوية حارس المصطلحات وبوابة تدقيق التبعيات المقفولة، مع إبقاء حدود الحارس موثقة. وأقر إضافة docs/** إلى فلتر فروع push في workflow. لا توسّع صلاحيات GitHub token.
>
> D-6 — قبول مؤقت بقيود: أقبل استثناء المخاطرة التطويرية لسلسلة braces الموثقة والتنبيه GHSA-vfj7-8cjw-p6xm حتى 2026-11-04. الشروط: settings.next.rootDir يبقى غير مضبوط؛ لا تصل أنماط يحددها المستخدم إلى هذا المسار؛ لا تُشغّل هذه الأدوات على مستودعات غير موثوقة؛ نتائج الإنتاج وفشل الماسح تبقى مانعة لنجاح البوابة؛ تحذيرات التطوير تبقى ظاهرة بلا قمع؛ تُراجع المخاطرة مبكراً عند توفر إصلاح متوافق. هذا ليس قبولاً لأي ثغرة تطوير مستقبلية. عند انتهاء المهلة يلزم قرار تجديد أو معالجة؛ لا تمديد تلقائي. إذا تغيرت شروط التعرض، أبلغني لإعادة تقييم الاستثناء.
>
> (Also stated: record these as a faithful transcription with date and scope; update only the status and checkboxes these decisions support; keep unsupported criteria open and explain; record run #11 as evidence for `5ac5a278…` and Compose as locally reported evidence for the same commit; no extra code changes; no merge; Phase 3 not started; acceptance of earlier phases is not permission to start Phase 3; ADR-0014 stays Proposed and non-binding and D8 stays OPEN until the owner's explicit decisions and a separate start instruction.)

| Decision | Scope / limits (as stated) | Effect recorded in the repository |
|---|---|---|
| **D-1** accept with limits | the two Phase 2.5 follow-ups and the derived-CORS addition, within their documented scope; not exhaustive UI-interaction or runtime-displayed-text coverage | Phase 2.5 acceptance gate closed; `phase-2.5.md` §4 items 1–10 ticked; status notes updated |
| **D-2** accept within the historical scope | "no application code" satisfied **at `ca2d4e4`**, not a condition on HEAD; Phase 0 accepted as planning/scaffolding; not a proof that current documents are contradiction-free | Phase 0 boxes ticked: *constraints referenced*, *open questions listed*, *no application code (as of `ca2d4e4`)*, *user review completed*. **Left open: *all files exist and are internally consistent*** |
| **D-3** accept | reported evidence sufficient for the three open Phase 1 boxes and the `TASKS.md` CI box; clean-checkout Compose run sufficient among the checks performed; no further general verification round requested | Phase 1 boxes (forbidden-term scan in CI, schema pipeline/drift, CI runs lint/type/tests/secret scan) and `TASKS.md` "CI workflow executed green" ticked; forbidden-term tick carries the documented guard limits (§6) |
| **D-4** accept, specific | the upload/archive boundary-test gap, via the committed tests green in CI #11; **not** the whole composite CRS/limits criterion by those tests alone | the composite box was examined aspect by aspect (see `acceptance-criteria.md` Phase 2 note) and ticked because each aspect has its own existing evidence; reprojection from CRSs other than EPSG:32632 is explicitly *not* claimed. **The `TASKS.md` Phase 2 box "GitHub Actions run green on the Phase 2 commits" stays open** — D-4 does not mention it |
| **D-5** accept | terminology-guard hardening and the locked-dependency audit gate, with the guard's limits kept documented; `docs/**` added to the `push` branch filter; GitHub token permissions not to be widened | no checkbox; §6 and §7a stand; workflow keeps `permissions: contents: read` |
| **D-6** accept, temporary | dev-only `braces` chain, advisory GHSA-vfj7-8cjw-p6xm, **until 2026-11-04**; conditions below (§7b) | no checkbox; recorded in §7b; no automatic extension |

## 3. CI evidence (GitHub Actions, workflow `ci`, branch `claude/geo-prospecting-foundation-hmcma4`; read on 2026-10-04 and 2026-10-05)

| Run | Commit | Result | Notes |
|---|---|---|---|
| #1 | `823fa87` | failure | first CI run; untracked empty CA file (fixed in `bbab3c8`) |
| #2 | `eda2681` | failure | generated-code drift (fixed in `bbab3c8`) — shows the drift check does fail |
| #3 | `bbab3c8` | success | 5 jobs: python (ruff, format, mypy, unit, integration, guards, licence register), frontend (lint/types/test/build + schema drift), gitleaks, dependency audit (report-only), docker build |
| #4 | `2ddef67` | success | Phase 2 UI commit |
| #5 | `1e7c823` | success | Phase 2 closeout commit; 5 jobs |
| #6 | `46178de` | success | run-level conclusion only |
| #7 | `02b6b05` | success | 6 jobs incl. `e2e` — **historical evidence** for the Phase 2.5 follow-ups |
| #8 | `9a7947e` | cancelled | superseded |
| #9 | `c3cf3a3` | success | run-level conclusion only |
| #10 | `da90ce2` | success | 6 jobs incl. `e2e`; code-identical to `02b6b05` (the 8 files changed since are documentation) — CI evidence for that baseline (historical) |
| **#11** | **`5ac5a278a9b93aaab4877e7ef84aa2640ff94b7c`** (branch `docs/status-refresh-adr-0013`) | **success** | 6 jobs: python (lint, types, unit, integration, guards, licences), frontend (+ schema drift), `e2e` browser smoke test, docker build, secret scan (gitleaks, CI image), **dependency audit (locked deps)** — audit log: Python production CLEAN (37), Python all groups CLEAN (63), npm production CLEAN, npm full FINDINGS (5 high, dev-only, printed as warnings), `exit=0`. CI evidence for this commit. https://github.com/mohaalmousa3-cpu/geo-prospecting-platform/actions/runs/37222835783 |

Scope limits of CI: it does not run `docker compose up` (only a build), its secret scan/audit/licence steps are as described, and the **dependency-audit job is report-only and, as written, audits the wrong environment** (§7).

## 4. Working-tree verification run in this round (base `da90ce2`, dirty tree)

**This is not CI evidence for any committed SHA.** Environment: local PostgreSQL 16 + PostGIS started from the existing local cluster (databases `geo_test`, `geo_e2e`; the integration fixture resets only `geo_test`), Chromium from `/opt/pw-browsers`, Docker started manually. No production credentials; no pre-existing containers, volumes or `.env` existed.

| Check | Command | Outcome |
|---|---|---|
| Lint / format | `make lint` | exit 0 — ruff check passed, 108 files formatted |
| Types | `make typecheck` | exit 0 — mypy: no issues in 36 source files |
| Unit tests | `make test` | exit 0 — **251 passed** (198 + 19 audit-gate + 34 guard regression), 132 deselected |
| Integration tests (PostGIS) | `make test-integration` (`GEO_TEST_DATABASE_URL`→`geo_test`) | exit 0 — **132 passed**, 198 deselected |
| Scientific guards | `make guard` | exit 0 — **61 passed** (27 + 34 regression cases) |
| Licence register | `make licences` | exit 0 |
| Schema drift | `make schemas-check` | exit 0 (only a `FutureWarning` from the generator) |
| Frontend | `make frontend-check` | exit 0 — lint, typecheck, format, **58 tests (5 files)**, production build |
| Browser smoke test (dev servers) | `make e2e` | exit 0 — **1 passed** (16.2 s); Playwright started its own API + Next servers |
| Docker Compose startup | `docker compose -p geo-verify … up -d --build` with a temporary git-ignored `.env` (placeholder values, random throw-away DB password; removed afterwards) | exit 0 — services `postgis`, `migrate`, `worker`, `backend`, `frontend` (no Redis/MinIO); built from the **dirty working tree, not a fresh clone** |
| Migrations | `alembic_version` in the Compose DB | `0003`; `postgis` extension present; 9 public tables |
| Health | `GET /api/v1/health`, `/health/ready`, frontend `/` | `{"status":"ok"}`, 200, 200 |
| Ports | `docker compose ps` | backend `127.0.0.1:8000`, frontend `127.0.0.1:3000`; PostgreSQL not published |
| `noop` job | `POST /api/v1/jobs {"type":"noop"}` then poll | `queued → running → succeeded`, `attempts=1` |
| Browser smoke test against the Compose stack | `npx playwright test` with `CI` unset (Playwright reused the running servers: no `WebServer` lines in the log) | exit 0 — **1 passed** (4.9 s). The temporary `.env` set `CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000` because the test browser origin is `127.0.0.1`, while `.env.example` defaults to `http://localhost:3000` (test configuration, not a product defect) |
| Teardown | `docker compose -p geo-verify … down -v`; `rm .env` | only the `geo-verify` network and its two volumes were removed; 0 containers/volumes remain; no `.env` remains |

**Not run / limits (honest list)**
- **gitleaks, CI form (`docker run zricethezav/gitleaks:latest …`)**: first round not run; second round the image could not be pulled (see §4a).
- **Fresh-clone Compose start** (Phase 1 criterion wording "from a clean clone") was **not performed**: Compose ran from the dirty working tree.
- A `ss`-based port-free check printed nothing because `ss` is not installed in this sandbox; the e2e start and the later Compose start succeeded, which shows the ports were free in practice.
- Throughput/limit profiling (ADR-0008 values) remains unmeasured.
- Nothing here exercises live Earth Observation providers (sandbox cannot reach them; Phase 3 D8 is open).

## 4a. Second round: re-run after the audit/guard changes, and gitleaks

Same dirty tree over `da90ce2` plus the §1 tooling changes; same environment as §4.

| Check | Outcome |
|---|---|
| `make lint` · `make typecheck` · `make licences` · `make schemas-check` | exit 0 · exit 0 (36 files) · exit 0 · exit 0 |
| `make test` / `make test-integration` / `make guard` | **251** passed / **132** passed / **61** passed |
| `make frontend-check` / browser smoke test (`npx playwright test`, dev servers) | exit 0 (58 tests, build) / 1 passed (14.7 s) |
| `python3 scripts/audit_deps.py` (= `make audit`) | exit 0 — Python production CLEAN (37), Python all groups CLEAN (63), npm production CLEAN, npm full FINDINGS (5 high, all dev-only; printed as `::warning`) |
| Audit gate under a simulated scanner failure (`npm_config_registry=http://127.0.0.1:9`) | **exit 2**, both npm scans reported `SCANNER-FAILURE` (not clean) |
| Guard regression cases against the **previous** scanner (`HEAD` version) | 20 of 21 new violation cases were **not detected** by the old scanner; all are detected by the new one |
| **gitleaks, CI form** — `docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect --source /repo --no-banner --redact` | **BLOCKED**: the image cannot be pulled (Docker Hub: "unauthenticated pull rate limit"); the same project's `ghcr.io/gitleaks/gitleaks:latest` also failed (blob host unreachable from the sandbox) |
| **gitleaks, same `detect` command with the locally built binary** (gitleaks v8.21.2 from the pre-commit hook cache; **not** the CI image, so the version may differ) | exit 0 — "20 commits scanned … no leaks found" (git history of the current branch) |
| Residue check on mutation-touched production files | identical to `HEAD` (see §1) |

A staged-content gitleaks scan is run immediately before committing (reported in the hand-over message).

## 4b. Clean-checkout Compose verification of commit `5ac5a27` (local, reported — not CI)

Clone of `origin/docs/status-refresh-adr-0013`; `HEAD` = `5ac5a278a9b93aaab4877e7ef84aa2640ff94b7c`, working tree clean. Isolated Compose project `geo-clean` with a temporary git-ignored `.env` (placeholder values, random throw-away DB password, `CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000` for the test browser origin), disposable data. Environment limits: Docker started manually in the sandbox; images built behind a TLS-intercepting proxy using the sandbox CA bundle (build time only); Chromium from `/opt/pw-browsers`.

| Check | Outcome |
|---|---|
| `docker compose up -d --build` | exit 0; services postgis, migrate, worker, backend, frontend (no Redis/MinIO) |
| Migrations | `alembic_version = 0003`; `postgis` present; 9 public tables |
| Health | `/api/v1/health` ok; `/health/ready` 200; frontend 200 |
| Ports | backend `127.0.0.1:8000`, frontend `127.0.0.1:3000`; PostgreSQL not published |
| `noop` job | `succeeded`, `attempts=1` |
| Browser smoke test against the stack (`npm ci` then `npx playwright test`, servers reused) | 1 passed (5.2 s) |
| Dependency-audit gate from the clean checkout | exit 0 (same results as CI) |
| Teardown | `down -v`; 0 containers/volumes left; `.env` removed |

## 5. Upload / archive boundary tests (item added this round)

File: `apps/backend/tests/test_aoi_upload_limits.py` (24 tests: 15 unit, 9 PostGIS-backed). Semantics tested = **documented** intent (ADR-0012 §8): reject an upload *larger than* `MAX_UPLOAD_MB`; reject an archive with *more than* `MAX_ARCHIVE_FILES` entries; reject uncompressed archive content *exceeding* `MAX_ARCHIVE_UNCOMPRESSED_MB` (declared sizes are not trusted; bytes counted as read). A value exactly at the limit is therefore accepted. Limits were lowered through settings so fixtures stay small; production defaults were not touched.

| Limit | Just below | Exactly at | Just above | Level |
|---|---|---|---|---|
| Upload size (`MAX_UPLOAD_MB=1`) | 201 | 201 | 413 `payload_too_large` | API |
| Archive entries (`MAX_ARCHIVE_FILES=5`) KMZ | accepted | accepted | `archive_too_many_files` | parser + API |
| Archive entries, zipped Shapefile (4 entries) | limit 5 accepted | limit 4 accepted | limit 3 rejected | parser |
| Archive uncompressed (`MAX_ARCHIVE_UNCOMPRESSED_MB=1`), single member | accepted | accepted | `archive_too_large` | parser + API |
| Archive uncompressed, sum across members | accepted | accepted | `archive_too_large` | parser |
| Actually-read byte budget (cumulative across members) | accepted | accepted | `archive_too_large` | `SafeZip.read` |

**Result:** all 24 pass; **no production defect found**. **Mutation check (temporary, restored with `git checkout`):** changing `>` to `>=` in each of the four comparison sites (upload size in `api/aois.py`; entry count, declared size and read cap in `aoi/archive.py`) made the suite fail every time (4/4 caught). Production source was verified unchanged afterwards.

**Not covered:** the forged-header case (declared size smaller than actual) is exercised only at the `SafeZip.read` level, not through a hand-forged ZIP; the request-body middleware cap (`MAX_UPLOAD_MB` + 1 MiB slack) is covered only indirectly by the "exactly at limit" API case.

## 6. Scientific-terminology guard — coverage of user-visible strings

Scanner: `tests/scientific/forbidden_terms.py`, run by `tests/scientific/test_guards.py::test_repo_contains_no_forbidden_claims` over `git ls-files -co --exclude-standard` (tracked **and** untracked-but-not-ignored files; git-ignored files are not scanned). Measured on the working tree: 169 files; **113 scanned**; 56 excluded.

**Covered (scanned):** files with suffix `.py .ts .tsx .js .mjs .json .yml .yaml .toml .md .html .css .sql .example` outside the exclusions — i.e. all backend/worker/common source (error messages, API summaries and descriptions are written in `.py`), all frontend source (31 files under `apps/frontend`: components, pages, lib, tests, e2e, config), `packages/schemas`, workflows, `README.md`, and `.env.example`.

**Excluded:**
- Allow-listed prefixes `docs/`, `CLAUDE.md`, `MASTER_SPEC.md`, `TASKS.md`, `tests/scientific/` (37 files) — documentation may discuss the terms.
- Path parts `node_modules .venv .next __pycache__ .git .mypy_cache .ruff_cache snapshots` — includes the OpenAPI snapshot (its text originates in scanned `.py`) and any built output.
- Names `package-lock.json`, `uv.lock`.
- Suffixes not scanned (16 files): `.dockerignore .editorconfig .gitignore .python-version LICENSE Makefile .prettierignore *.svg (apps/frontend/src/app/icon.svg) .gitkeep *.Dockerfile .crt *.mako *.sh`.
- Anything git-ignored.

**Gaps (why a passing guard is not proof of full coverage):**
1. It scans **source text, not rendered UI**: no check reads the DOM that users see (the e2e test does not assert on forbidden terms).
2. Strings assembled at runtime, split across lines or code constructs are not matched; non-English text is not matched; images/SVG text is not scanned.
3. The patterns are phrase-shaped. Probes run this round: *hit* — "Gold found here", "Cave detected", "Confirmed deposit", "Gold confirmed", "Void confirmed", "Detected void", "gold_found", "goldFound", "caveDetected", "mineralisation confirmed". *Miss* — "found gold", "cave identified", "void located", "Mineralization confirmed" (American spelling; the pattern covers `mineralis*` only), "gold present", "ore body detected", and a phrase broken across two lines.
4. Directory-level exclusions mean new documentation-like files under `docs/` are never scanned.

**Second round — what changed (guard hardening).** `tests/scientific/forbidden_terms.py` now (a) matches reverse word order (`found gold`, `identified deposit`, `located void`); (b) adds the verbs `identified`, `located`, `encountered` and the word `present` (`gold present`, `void present`); (c) covers American and British spelling (`mineralization`/`mineralisation`); (d) treats `ore body` like `ore`; (e) matches phrases split by line breaks and by comment/markdown decoration (`#`, `//`, `*`), reporting them at the first line; the `forbidden-term-ok` marker on any touched line still suppresses a match. 34 regression cases were added (violations, false-positive guards, multi-line reporting, and the documentation allow-list behaviour of `scan_repo`). The new scanner reports **no hits** on the current repository (113 scanned files), so no source text had to change. The justified exclusions (documentation prefixes, `tests/scientific/`, lockfiles, snapshots, build output) are unchanged.

**What this still does not establish:** phrases split by HTML/JSX tags, strings assembled at run time, non-English text, images/SVG text and any wording outside the phrase shapes still pass; a passing scan is evidence about *source text*, not proof about the rendered DOM or every language. A DOM-text scan in the e2e test was **not** added (out of scope for this round); decide separately whether it is wanted.

## 7. Dependency audit

### 7a. The CI gate (second round)

**Defect found (first round):** the CI step `uv sync --all-packages --frozen && uvx pip-audit --local || true` ran `pip-audit` in `uvx`'s own isolated environment and audited 29 packages — pip-audit's own dependencies, not the project's — and `|| true` plus job-level `continue-on-error` hid every outcome.

**Fix:** `scripts/audit_deps.py` (also `make audit`), called by the rewritten CI job `audit` (no `|| true`, no `continue-on-error`).

| Aspect | Definition |
|---|---|
| Python inputs | `uv export --frozen --no-hashes --no-emit-workspace --all-packages --no-dev` (**production**, 37 pins) and `… --all-groups` (**everything**, 64 lines / 63 audited); source of truth `uv.lock` (sha256 printed at run time) |
| Python scanner | `uvx --from pip-audit==2.10.1 pip-audit -r <export> --no-deps --disable-pip --format json` (version pinned) |
| npm inputs | `apps/frontend/package-lock.json` (sha256 printed): `npm audit --omit=dev --json` (**production**) and `npm audit --json` (**full**) |
| Outcomes (never blurred) | `CLEAN` (ran on a non-empty input, nothing found) · `FINDINGS` (ran, vulnerabilities reported; also when the tool exits non-zero) · `SCANNER-FAILURE` (no parsable report, `error` object, empty input, packages that could not be audited, non-zero exit with no findings, tool/network failure) |
| Gate | exit **0** = no failure and no production findings · **1** = Python or npm **production** findings · **2** = any scanner failure (precedence over 1). Development-only findings (present in the full/all-groups scan but not in the production scan) never change the exit code but are printed in full and as GitHub `::warning` annotations; there is no allow-list and nothing is suppressed |
| Lockfiles | unchanged |
| Tests | `tests/unit/test_audit_deps.py` (19 cases: three outcomes for each scanner, failure modes, gate precedence, dev-only separation, CI wiring forbids `|| true`/`continue-on-error`/`pip-audit --local`) |

**Results on the working tree:** Python production CLEAN (37 packages), Python all groups CLEAN (63), npm production CLEAN (0), npm full FINDINGS (5 high, all dev-only; §7b). Gate exit 0. Under a simulated registry outage the gate exits 2 (§4a). Note: npm reports `metadata.dependencies.total` for the whole tree even with `--omit=dev`, so the "packages audited" figure for the npm production scan (547) is the tree size, not a production-only count (production dependencies: 46).

**CI trigger change (needs your review):** `ci.yml` ran on `push` only for `main` and `claude/**`, so a push to `docs/status-refresh-adr-0013` would have produced **no CI run** (and the requested post-push CI evidence would not exist). I added `"docs/**"` to the `push` branch filter. This is a workflow change beyond the audit fix; it is reversible and grants nothing (the workflow keeps `permissions: contents: read`).

### 7b. The npm development-only advisory — investigation

Evidence (`npm audit --json`, npm 10.9.4, audit report v2): `metadata.vulnerabilities = {high: 5, total: 5}`; production audit total 0.

```json
{"name":"braces","severity":"high","isDirect":false,
 "via":[{"source":1240992,"name":"braces","title":"braces vulnerable to stack-exhaustion denial of service through deeply nested patterns",
         "url":"https://github.com/advisories/GHSA-vfj7-8cjw-p6xm","severity":"high","cwe":["CWE-674"],
         "cvss":{"score":7.5,"vectorString":"CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"},"range":"<=3.0.3"}],
 "effects":["micromatch"],"range":"*","nodes":["node_modules/braces"],
 "fixAvailable":{"name":"eslint-config-next","version":"14.2.35","isSemVerMajor":true}}
```

Installed path (`npm ls`, lockfile): `eslint-config-next@16.3.8 → @next/eslint-plugin-next@16.3.8 → fast-glob@3.3.1 → micromatch@4.0.8 → braces@3.0.3`. In `package-lock.json` all four are `dev: true`; nothing else in the tree depends on `braces`, `micromatch` or `fast-glob`; `next` itself does not declare them. (Next ships its own vendored compiled copies, which `npm audit` cannot see and which were **not** assessed.)

**Can untrusted patterns reach the vulnerable package through this project's lint/build/CI usage? — likely no.**
- The only caller is `@next/eslint-plugin-next/dist/utils/get-root-dirs.js`, which calls `fast-glob`'s `globSync` **only when** the ESLint setting `settings.next.rootDir` is a string/array. `apps/frontend/eslint.config.mjs` does not set it (no `rootDir` anywhere in the frontend config), so the rule `no-html-link-for-pages` takes the default `[context.cwd]` and no glob/brace expansion runs.
- Even if it were set, the pattern would come from the repository's own ESLint configuration (committed, reviewed), not from uploaded files, API input or CI event data. CI lint runs on the repository checkout; pull-request authors could change the config, which is the normal trust boundary of any lint config.
- `next build`, `vitest`, `prettier` and Playwright do not use this chain (they are not dependents in the lockfile).
- Confidence: *likely* (read of the installed plugin source and the lockfile; not a dynamic trace).

**Compatible upstream fix? — none found.**
- Registry state on 2026-10-04: `braces` latest = **3.0.3** (published 2024-05-21), which is the installed and an affected version (advisory range `<=3.0.3`; no patched version exists); `micromatch` latest = 4.0.8 (installed); `fast-glob` latest = 3.3.3, whose dependency is still `micromatch ^4.0.8`; `@next/eslint-plugin-next` latest = 16.3.8 and canary `16.4.0-canary.59` both still pin `fast-glob 3.3.1`.
- The only fix `npm audit` offers is `eslint-config-next@14.2.35` (`isSemVerMajor: true`) — a **major downgrade** from 16.3.8 for a Next 16 project. Not applied. `npm audit fix --force` was not run; no Next-related package was downgraded; no override was added; lockfiles are unchanged.
- The advisory text itself could not be retrieved (the sandbox only reaches repository-scoped GitHub endpoints); the title, CWE-674, CVSS 7.5 and range above come from the npm audit report.

**Time-limited exception — ACCEPTED (conditional) by owner decision D-6, 2026-10-05, until 2026-11-04.** Scope: the five dev-only packages of the chain above (`eslint-config-next`, `@next/eslint-plugin-next`, `fast-glob`, `micromatch`, `braces`) and advisory GHSA-vfj7-8cjw-p6xm. Conditions (as stated by the owner):

1. `settings.next.rootDir` stays unset (`apps/frontend/eslint.config.mjs`).
2. No user-specified pattern reaches this path.
3. These tools are not run on untrusted repositories.
4. Production findings and scanner failures remain gate-blocking (the audit gate exits 1/2 on them — §7a).
5. Development warnings stay visible; nothing is suppressed and no allow-list exists.
6. The risk is reviewed early when a compatible fix appears.

Limits of the acceptance: it is **not** acceptance of any future development vulnerability; at expiry (2026-11-04) a renewal or remediation decision is required — **there is no automatic extension**; if the exposure conditions change, the owner must be told so the exception can be re-assessed. The optional mitigation (a unit test asserting `rootDir` is unset) was **not** implemented (no code changes were authorised). Next review date: **2026-11-04**.

## 8. Reconciliation matrix — snapshot taken before the 2026-10-05 owner decisions (current statuses: §8a)

Common to every row: the OWNER evidence is a **transcription** (§2). "—" = nothing beyond the phase-level gap. `bbab3c8`=#3, `2ddef67`=#4, `1e7c823`=#5, `46178de`=#6, `02b6b05`=#7, `da90ce2`=#10; "WT" = the dirty working tree of §4 (not CI).

### Phase 0 — OWNER: T1 (scope decisions); no explicit Phase 0 acceptance. IMPL: `ca2d4e4`, `457a6e3`.

| Criterion | VERIF | GAP | Required next action |
|---|---|---|---|
| Brief files exist and are internally consistent | files present at `da90ce2` (listed); consistency **not met** — status contradictions found and annotated | consistency | owner decides after this reconciliation is accepted |
| Scientific constraints referenced from README, MASTER_SPEC, CLAUDE.md | `grep`: 2 / 2 / 1 references at `da90ce2` | — | owner may tick |
| Open questions with owner decisions pending | `TASKS.md` *Open Questions* section | — | owner may tick |
| No application code or scientific logic | true at `ca2d4e4`; cannot be evaluated at HEAD (code exists by design) | criterion superseded | owner decision: "satisfied at `ca2d4e4`" |
| User review completed | — | no explicit Phase 0 acceptance recorded | explicit owner decision required |

### Phase 1 — OWNER: T3 "accepted with follow-up checks". IMPL: `38fa223`, `cc3b602`, `6168910`, `823fa87`, `eda2681`, `bbab3c8`.

| Criterion | VERIF | GAP | Required next action |
|---|---|---|---|
| `docker compose up` starts postgis, backend, worker, frontend; no Redis/MinIO; loopback ports | reported local fresh-clone run (`phase-1.md` §4); **WT** run in §4 (dirty tree, not a fresh clone); CI #3/#10 only build the images | CI does not start the stack; fresh-clone start not repeated | optional: fresh-clone `make up` at the final commit |
| `/api/v1/health` OK, status page shows health | WT §4 (200); CI integration tests | — | — |
| Migrations apply, PostGIS enabled, tables created | WT §4 (`0003`, postgis, 9 tables); CI integration (up/down/up test) | — | — |
| `noop` job API → DB → worker → DB | WT §4 (`queued→running→succeeded`); CI integration | — | — |
| Queue tests (concurrency, lease, retry, timeout, cancel, queue-full) | CI #3/#10 integration step; WT 132 integration passed; mutation check reported in `phase-1.md` §3 | — | — |
| Storage rejects traversal/absolute keys; envelope requires fields; `validation_status` only `unvalidated`; no auth/Redis/MinIO; LICENSE placeholder | CI unit + guards (#3, #10); WT 198 unit + 27 guards | — | — |
| **[open]** Forbidden-term scan runs in CI over source, fixtures, UI strings, docs allow-list | CI #3…#10 step "Scientific guards"; coverage analysed in §6 | scanner is source-text only; real gaps listed in §6 | owner: tick as "runs in CI" or require the §6 hardening first |
| **[open]** Schema pipeline generates types; CI fails on drift | CI #3…#10 frontend step; #2 failed on drift (check bites); WT `make schemas-check` exit 0 | — | owner tick decision |
| **[open]** CI runs lint, type-check, tests, secret scan | CI #3 (ruff, format, mypy, unit, integration, guards, gitleaks); #10 same | — | owner tick decision |

### Phase 2 — OWNER: T4 "approved with follow-up items". IMPL: `46596b4`, `2ddef67`, `1e7c823`.

| Criterion | VERIF | GAP | Required next action |
|---|---|---|---|
| Point+radius geodesically correct | tests vs reference values (`phase-2.md` §2); CI #4/#5 | — | — |
| Draw rectangle/polygon; save and reload | ad-hoc real-browser check (`phase-2.md`); `e2e` covers create AOI but drawing UI interaction was not audited | drawing not in CI | optional e2e extension |
| Upload GeoJSON/KML/KMZ/Shapefile; hostile files rejected | hostile-upload tests; CI #4/#5; WT 132 integration | real-world exports untested (risk P-10) | owner supplies samples |
| **[open]** Normalised CRS + ADR-0008 limits enforced with boundary tests at / just below / just above each limit | area, min area, radius, vertices: existing. **Upload size, archive size, archive entries: new WT tests (24 pass; mutation 4/4 caught)** — uncommitted, not CI | new tests uncommitted; CRS reprojection tested for EPSG:32632 only | commit the tests, then CI; owner tick decision |
| Antimeridian/polar rejected; no analysis shown | tests; guard tests (no analysis keys); CI | — | — |
| TASKS: Actions green on Phase 2 commits **[open]** | #4 `2ddef67`, #5 `1e7c823` success; `46596b4` has no run of its own | — | owner tick decision |
| Phase 2 "delete works" claim | amended: delete failed in a real browser (CORS) until `46178de` | — | already documented |

### Phase 2.5 — OWNER: T5 "approved with two required follow-ups"; **no explicit owner decision on the follow-ups themselves**. IMPL: `2d7fc0b`, `fffdb8e`, `46178de`, `7eaf0a6`, `02b6b05`.

| Criterion | VERIF | GAP | Required next action |
|---|---|---|---|
| `project` entity, bounded count, AOIs belong to a project, migration | reported `make ci` + browser (`phase-2.5.md` §2); CI #6 `46178de`, #7 `02b6b05`, #10 `da90ce2`; WT | owner checklist (`phase-2.5.md` §4) unticked | owner ticks |
| Contracts/API; save requires `project_id`, preview does not; non-empty delete needs `delete_aois=true` | tests; CI; WT (e2e covers the cascade confirmation) | — | — |
| Project-aware UI; basemap abstraction; docs; validation unchanged; no expansion | unit tests, CI, architecture/guard tests | — | — |
| **Follow-up 1** — browser smoke test in CI | CI #7 `02b6b05` `e2e` ✔ (**historical**); #10 `da90ce2` `e2e` ✔; WT dev-server run and **Compose-stack run** ✔; mutation check (reported earlier) | **explicit owner decision not recorded** | explicit owner decision required |
| **Follow-up 2** — basemap default `none`; `osm` dev-only/refused in production builds; `xyz` explicit + attribution | unit tests; reported production-image check (zero third-party requests); CI | **explicit owner decision not recorded**; the production-image check was not repeated this round | explicit owner decision required |
| CORS derived from OpenAPI operations (extra, requested as "future-safe") | tests for every operation; e2e covers DELETE; WT Compose preflight returned the expected method list | **explicit owner decision not recorded** | explicit owner decision required |
| GitHub Actions run #7 green (six jobs) | #7 (historical) and #10 (current committed baseline) | — | — |

## 8a. Status after the owner decisions of 2026-10-05 (what changed in the checklists)

| Phase | Criterion | Before | Now | Basis |
|---|---|---|---|---|
| 0 | all files exist and are internally consistent | open | **open** | D-2 explicitly does not claim consistency |
| 0 | constraints documented and referenced | open | ticked | `grep` evidence (2/2/1 references) + D-2 acceptance within historical scope |
| 0 | open questions listed | open | ticked | `TASKS.md` section + D-2 |
| 0 | no application code | open | ticked (as of `ca2d4e4`) | D-2 |
| 0 | user review completed | open | ticked | D-2 |
| 1 | forbidden-term scan runs in CI | open | ticked | D-3; CI #3 … #11 step "Scientific guards"; guard limits documented (§6, D-5) |
| 1 | schema pipeline/drift | open | ticked | D-3; CI frontend step; run #2 failed on drift |
| 1 | CI runs lint/type/tests/secret scan | open | ticked | D-3; CI #3 … #11 |
| 1 | `TASKS.md` "CI workflow executed green" | open | ticked | D-3 |
| 2 | composite CRS/limits box | open | ticked | D-4 (upload/archive gap) + each other aspect tied to existing evidence (`acceptance-criteria.md` Phase 2 note); other-CRS reprojection explicitly not claimed |
| 2 | `TASKS.md` "Actions green on the Phase 2 commits" | open | **open** | evidence exists (#4, #5) but no explicit decision covers this box |
| 2.5 | `phase-2.5.md` §4 items 1–10 | open | ticked | D-1 (gate closed); verification in §2/§6 of that report, CI #7 (historical), #10, #11 |
| 2.5 | `acceptance-criteria.md` Phase 2.5 items | ticked | ticked | unchanged |
| 3+ | all | open | **open** | not in scope of any decision; Phase 3 not started |

## 9. Remaining gaps and open items (after the 2026-10-05 decisions)

1. `acceptance-criteria.md` Phase 0: *all files exist and are internally consistent* — open by the owner's own limitation (D-2).
2. `TASKS.md` Phase 2: "GitHub Actions run green on the Phase 2 commits" — open; evidence exists, no explicit decision.
3. Phase 3: blocked — needs an independent explicit start instruction, an explicit owner decision on ADR-0014 (Proposed, non-binding) and decision D8 (OPEN: live-verification route).
4. D-6 exception expires **2026-11-04**; renewal or remediation decision required; notify the owner if exposure conditions change.
5. Limits that remain true: the terminology guard is a source-text scan (§6); other-CRS reprojection untested (risk P-10); ADR-0008 limits unmeasured; no live provider verification; Phase 5 region gate and Earth Engine eligibility unchanged.
6. The CI result of the documentation-only commit that records these decisions is not (and cannot be) recorded inside that commit.

## 10. Verification of the code baseline

The owner accepted the reported evidence (D-3) and requested no further general verification round. For the record: commit `5ac5a27` has CI run #11 (§3) and a clean-checkout Compose run (§4b, local). The commit recording the owner decisions changes documentation only.

## 11. Owner decision record

| Item | Decision | Date | Where |
|---|---|---|---|
| D-1 Phase 2.5 follow-ups + derived CORS | accepted with limits | 2026-10-05 | §2a |
| D-2 Phase 0 / "no application code" | accepted within the historical scope | 2026-10-05 | §2a |
| D-3 Phase 1 open boxes + TASKS CI box | accepted | 2026-10-05 | §2a |
| D-4 Phase 2 upload/archive boundary tests | accepted (specific) | 2026-10-05 | §2a |
| D-5 guard + audit gate + `docs/**` trigger | accepted | 2026-10-05 | §2a |
| D-6 dev-only `braces` exception | accepted, temporary, until 2026-11-04 | 2026-10-05 | §7b |
| Commit and push of the bounded work | authorised for `docs/status-refresh-adr-0013` only; **merge not authorised** | 2026-10-05 | owner messages |
| ADR-0014 | **undecided** — Proposed, non-binding | — | `docs/adr/0014-…` |
| D8 live-verification route | **OPEN** | — | `docs/phase-3-plan.md` |
| Phase 3 start | **not authorised** | — | independent start instruction required |
