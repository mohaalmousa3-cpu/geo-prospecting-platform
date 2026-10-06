# Acceptance Reconciliation — Phases 0, 1, 2, 2.5

Date: 2026-10-04 (verification rounds) · updated 2026-10-05 (owner decisions D-1…D-6 recorded in §2a, the owner's second message in §2b, the third in §2c and the fourth — acceptance of ADR-0014 — in §2d; evidence for commit `5ac5a27` in §3 and §4b) · Base commit of the verification rounds: `da90ce2b7051dc650dfcb4247155a4eccbf4a8f0` (branch `docs/status-refresh-adr-0013`). Sections 4–7 record local verification on the **dirty working tree** over that base (before the commit that contains this file). CI evidence for commit `5ac5a27` (run #11) is recorded in §3; the CI result of the later documentation-only commit that records the 2026-10-05 decisions is **not** recorded here (a commit cannot cite its own run).

> **What this document is — and is not.** It is **not** itself an acceptance: owner acceptance exists only as the owner's decisions transcribed in §2 and §2a. It records, per criterion, what was implemented, what was verified (and where), what the owner decided (as transcribed), and what is still open. After the owner's decisions of 2026-10-05 only the checkboxes those decisions support were ticked (listed in §2a). The local runs in §4–§4a are **not** CI evidence for any committed SHA. Phase 3 remains: *Planned — not started; ADR-0014 Accepted 2026-10-05 (not implemented); the fixtures-only Phase 3a scope accepted 2026-10-05 (scope acceptance only, not a start instruction); blocked pending a separate, explicit, bounded start instruction; D8 strategy resolved (option D), live-verification readiness pending; Phase 0 follow-up F-1 open and non-blocking only for fixtures-only 3a; no live host or network control approved.* ADR-0014 is Proposed and non-binding; decision D8 is OPEN.

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
| **D-4** accept, specific | the upload/archive boundary-test gap, via the committed tests green in CI #11 (the `TASKS.md` box mentioned in the next column was later approved in §2b item 1); **not** the whole composite CRS/limits criterion by those tests alone | the composite box was examined aspect by aspect (see `acceptance-criteria.md` Phase 2 note) and ticked because each aspect has its own existing evidence; reprojection from CRSs other than EPSG:32632 is explicitly *not* claimed. **The `TASKS.md` Phase 2 box "GitHub Actions run green on the Phase 2 commits" stays open** — D-4 does not mention it |
| **D-5** accept | terminology-guard hardening and the locked-dependency audit gate, with the guard's limits kept documented; `docs/**` added to the `push` branch filter; GitHub token permissions not to be widened | no checkbox; §6 and §7a stand; workflow keeps `permissions: contents: read` |
| **D-6** accept, temporary | dev-only `braces` chain, advisory GHSA-vfj7-8cjw-p6xm, **until 2026-11-04**; conditions below (§7b) | no checkbox; recorded in §7b; no automatic extension |

## 2b. Owner message of 2026-10-05 (after CI run #12) — faithful transcription

**Transcription by Claude; not an independent signed record.** The owner stated they had received the report for commit `059216a…` and CI run #12 and requested no further general verification round. Original text (Arabic), verbatim, items 1–5:

> 1. Phase 2 TASKS item — I approve marking the Phase 2 “Actions green” item as complete based on the documented evidence from runs #4 and #5. Preserve the note that commit 46596b4 has no independent CI run. If the item's wording literally requires a run for every Phase 2 commit, do not mark it complete until the wording is clarified. Do not let the checkbox imply evidence that does not exist.
>
> 2. Phase 0 — My acceptance within its historical scope remains valid. Keep the internal-documentation-consistency criterion open as a documented follow-up. Do not claim that all prerequisite acceptance criteria are complete. If the phase-start rule makes this open criterion a blocker, explicitly identify that conflict so we can resolve it before any start instruction.
>
> 3. ADR-0014 — I support the proposed direction for further review. I am NOT accepting ADR-0014 in its current form. Revise the proposal, through documentation changes only, to specify: consistency between database-row deletion and stored-file deletion (operation ordering, failure states, retries, reconciliation; simplest suitable mechanism, no broad subsystem without demonstrated need); how deletion of a project/AOI is protected against concurrent job insertion or execution, and how a job's project_id is guaranteed to match the project belonging to its aoi_id; outbound-request protection (HTTPS, explicitly permitted hosts and ports, prevention of access to internal and cloud-metadata destinations, revalidation of every redirect or pagination URL before following it; distinguish application controls from network controls and state their limitations); licence review for direct dependencies and bundled binary components, with licences recorded before adding rasterio or other packages; a concise alternatives section. ADR-0014 remains Proposed and non-binding. Present the revised text before requesting my acceptance.
>
> 4. D8 — I select option D as the verification strategy: Phase 3a is fixtures-only. Live verification is mandatory before accepting the relevant live connector slices, including 3b and DEM. The preferred live-verification route is B if the environment supports it, subject to separate approval of the exact host allowlist. Otherwise, use route A. Do not expand network access now. Do not treat speculative hostnames as approved. Before live verification, confirm from official sources: exact endpoints and required hosts; terms of service, licenses, and attribution requirements; request limits and any applicable costs. Do not send the project's private AOI geometry during connectivity checks; use small, fixed queries or public example data where necessary. Do not load-test providers or deliberately probe their rate limits. Distinguish: D8 strategy decision — resolved by this instruction; live-verification readiness — pending its prerequisites. Selecting this strategy is not acceptance of live connector functionality.
>
> 5. Scope and stopping point — documentation-only changes; present the diff and remaining gates. No code, dependency or network-setting changes. Do not commit or push this round until the owner has reviewed the wording. No merge; Phase 3 not begun. The owner will separately decide whether to accept ADR-0014 and issue an explicit, bounded start instruction for Phase 3a only.

| Item | Scope / limits (as stated) | Effect recorded |
|---|---|---|
| 1 Phase 2 `TASKS.md` "Actions green" | approved on runs #4 (`2ddef67`) and #5 (`1e7c823`); not to imply a run for `46596b4`; if the wording literally required a run per commit, do not tick before clarifying | The `TASKS.md` item wording was **clarified** to the evidenced claim (tip commits of the Phase 2 pushes; `46596b4` had no independent run; original wording preserved inside the item and noted as *not satisfied if read literally*) and then ticked. The owner may revert the clarification |
| 2 Phase 0 | acceptance within the historical scope stays valid; *internally consistent* stays open as a documented follow-up (F-1); no claim that all prerequisite criteria are complete; identify any conflict with the phase-start rule | F-1 recorded; **conflict identified** in `MASTER_SPEC.md` (see §9, item 3) — not resolved |
| 3 ADR-0014 | direction supported for review; **not accepted at that time** (accepted later — §2d) | revision 2 of `docs/adr/0014-…` (documentation only); still Proposed, non-binding |
| 4 D8 | strategy option D resolved; readiness pending; route B preferred subject to a separate allowlist approval; no network change; no host approved | `docs/phase-3-plan.md` §8a and the D8 row; no network setting touched |
| 5 Scope | documentation only; do not commit/push before the owner reviews the wording | the revision is in the working tree, **uncommitted** |

## 2c. Owner message of 2026-10-05 (after ADR-0014 revision 2) — faithful transcription

**Transcription by Claude; not an independent signed record.** Original text (English), verbatim:

> Revision 2 is substantially clearer, but I am not accepting ADR-0014 yet. Make one bounded documentation revision addressing the items below. Date: 2026-10-05.
>
> 1. Phase 2 TASKS wording — I approve your clarified wording and the checked item, provided the ancestry claim is verified from Git: 46596b4 must actually be an ancestor of the tip tested by run #4. Preserve the distinction between: the tested tip containing earlier changes; an independent CI run for each earlier commit. Do not imply that every intermediate snapshot was tested.
>
> 2. Phase 0 follow-up F-1 — I designate F-1 as a non-blocking documentation follow-up for the fixtures-only Phase 3a slice. This is a narrow owner-authorized exception, not a general change to the phase-start rules and not a declaration that F-1 is satisfied. Keep F-1 open, list the known unresolved consistency issues, and require its closure before authorization to begin a live connector slice. This decision does NOT authorize Phase 3a to start.
>
> 3. Database integrity — Make the proposed constraints explicit: data_asset.project_id and data_asset.aoi_id are NOT NULL. data_asset.job_id remains optional. When job_id is present, the composite FK must enforce that the asset belongs to that job's AOI and project. Explain the intended NULL behaviour of each composite FK. Enumerate which existing job types must satisfy the non-noop rule. Specify migration/backfill handling for existing jobs before applying new constraints. Do not assume all existing rows already qualify. Do not describe AOI movement as universally prohibited merely because ON UPDATE RESTRICT prevents changes while referenced. State the actual application policy and database protection separately.
>
> 4. Concurrency — Specify the supported transaction isolation level and the exact lock/check/delete ordering. Include project deletion versus concurrent AOI creation, not only AOI deletion versus job insertion. Specify a consistent lock ordering for insertion, deletion and cleanup, and handling of deadlocks, serialization failures and FK conflicts. Keep the concurrency claims labelled as design obligations pending implementation tests. Do not claim that they have already been proved. The tests belong to the authorized implementation slice; they are not a prerequisite that requires unapproved code before accepting the ADR.
>
> 5. Files and tombstones — I support the transaction-plus-tombstone direction, with these additions: storage keys are unique, immutable and never reused; cleanup cannot delete a newly referenced or replacement asset; concurrent cleanup attempts are safe and idempotent; define the response semantics when database deletion succeeded but file cleanup remains pending (do not report the database operation as failed merely because post-commit cleanup failed). Replace "never a row without a file" with a narrower guarantee: the normal creation sequence writes the file before committing its row. Explicitly retain the limitations involving external file removal, filesystem failure and crash durability. The 24-hour orphan age is a minimum eligibility threshold, not proof that a file is safe to delete. Orphan deletion must additionally avoid in-progress writes, active jobs and concurrent publication.
>
> 6. Network protection and slice boundaries — Keep the security requirements, but do not lock the design into a bespoke HTTP transport before evaluating maintained alternatives. Address pinning and TLS verification are implementation requirements to validate, not established capabilities. Provide a short slice-boundary table: what is implemented in 3a; what is deferred to the live slices; what must pass before any live request. Do not add unused rasterio, live network code or speculative provider configuration to fixtures-only 3a. No live connector execution is authorized without separate approval of the exact hosts and the proposed application/network controls. Do not imply that the worker can have no outbound connectivity at all: it still needs its explicitly required internal service connections.
>
> 7. Licensing — I am the owner who acknowledges weak-copyleft or unusual licence cases. Record each such acknowledgement in the licence register, linked to the relevant dependency version and owner decision. Strong-copyleft or unknown cases remain blocked under the existing rules. List bundled binary components only after inspecting the selected distribution artifacts. Keep the current component list labelled as illustrative, not as a verified inventory.
>
> 8. Governance and status — D8 strategy remains resolved as option D. Live-verification readiness remains pending. ADR-0014 remains Proposed. Phase 3 remains not started. Use one canonical status value consistent with the repository's ADR convention; do not alternate ambiguously between Approved and Accepted.
>
> 9. Deliverable and stopping point — Present the revised ADR sections and concise diff; the proposed exact Phase 3a implementation scope; its acceptance tests and remaining start gates; the remaining F-1 issues. Documentation changes only. No code, dependencies, network changes, commit, push or merge. Do not start Phase 3. Stop for my review.

| Item | Effect recorded |
|---|---|
| 1 | Ancestry **verified from Git**: `46596b4` is the direct parent of `2ddef67` (run #4's tip) and an ancestor of `1e7c823` (run #5's tip); the `TASKS.md` item now says the tested tip contains `46596b4`'s changes and that this is not an independent run for it and that no intermediate snapshot was tested separately |
| 2 | F-1 designated a narrow, non-blocking exception for fixtures-only 3a; stays open; issues listed in §9a; closure required before any live connector slice; 3a start **not** authorised |
| 3–7 | ADR-0014 revision 3 (`docs/adr/0014-…` §7–§11); Proposed at that time (accepted later as revision 4 — §2d) |
| 8 | canonical ADR status vocabulary `Proposed → Accepted` written into `docs/adr/README.md`; "Approved" replaced by "Accepted" where it referred to ADR-0014; D8 strategy resolved, readiness pending |
| 9 | revision is in the working tree, **uncommitted** |

## 2d. Owner message of 2026-10-05 (after ADR-0014 revision 3) — faithful transcription

**Transcription by Claude; not an independent signed record.** Original text (English), verbatim:

> Revision 3 is sufficient to settle the architectural direction. I do not want another broad redesign round. Date: 2026-10-05.
>
> I accept the fixtures-only Phase 3a scope you presented, subject to the clarifications below. This is scope acceptance, NOT a start instruction. I accept the transaction-plus-tombstone approach, the files_pending_cleanup response, and the 24-hour minimum orphan-age rule with its additional safety conditions.
>
> Before marking ADR-0014 Accepted, make these bounded corrections:
>
> 1. Transaction errors and lock ordering — Replace "duplicate tombstone key 23505: ignored" with explicit, targeted conflict handling: INSERT ... ON CONFLICT (storage_key) DO NOTHING, or an equivalent transaction-safe mechanism. Retries must roll back and restart the entire affected transaction, not continue issuing statements in an aborted transaction. The project deletion algorithm must match the stated global lock order. Do not claim a global project → all AOIs → all jobs → all assets order while implementing a per-AOI traversal that acquires an asset lock before another AOI's job lock. Choose and document one consistent ordering. Keep its correctness subject to the implementation concurrency tests. Do not map every foreign-key violation blindly to 404. Translate known constraint failures appropriately and surface unexpected integrity failures as errors rather than hiding them.
>
> 2. Licence acknowledgements — Do not hand-edit the generated third-party licence register. Use a durable, version-controlled source of truth for owner acknowledgements, referenced by the generated register. Evaluate the existing generator/input structure before adding anything. A separate acknowledgement file is acceptable if needed, recording: package/component, version, licence, artifact class, owner decision, date, source message and conditions. Do not invent or retroactively infer Phase 1 acknowledgements. Record only decisions supported by actual owner messages; list unsupported cases for my decision. If modifying the generator requires code, leave that implementation for a separately authorized task. No such code change is authorized in this documentation step.
>
> 3. No-network test — The fixtures-only connector must make no external network requests. The socket/network guard must target connector execution and must not prohibit the worker's necessary PostgreSQL connections. Specify how the test distinguishes connector-originated network activity from test infrastructure and internal service connections.
>
> 4. Empty catalogue behaviour — Clarify the zero-results behaviour in T4. It must remain an ingestion/catalogue status, not a scientific result. Do not introduce confidence, scoring or interpretation, and do not write a scientific result merely because a catalogue search is empty. If insufficient_data is used, identify its contract and meaning.
>
> 5. Orphan cleanup — Until safe exclusion of concurrent publication is implemented and tested, orphan cleanup must remain report-only. Do not enable destructive orphan cleanup based only on file age or the absence of queued/running jobs.
>
> 6. Acceptance and persistence — If these clarifications can be made without changing the agreed architectural direction, I explicitly accept ADR-0014 with them included. Mark it Accepted, not Implemented, and record this owner decision with its date and conditions. If you believe any clarification requires a substantive design change, keep the ADR Proposed and ask me before proceeding. I authorize commit and push of the documentation-only revision to docs/status-refresh-adr-0013. Inspect the complete diff first. No code, dependency, licence-generator or network changes. No merge. Report: the new commit SHA and changed-file list; the exact CI run and outcome for that SHA; any remaining prerequisite for starting 3a. F-1 remains open and non-blocking only for fixtures-only 3a. D8 strategy remains resolved; live readiness remains pending. No live host or network control is approved by this message. Do NOT begin Phase 3a. After reviewing your documentation commit and CI report, I will issue a separate bounded implementation start instruction. Stop for review.

| Item | Effect recorded |
|---|---|
| Scope acceptance | fixtures-only Phase 3a scope (`docs/phase-3-plan.md` §6) accepted **as scope**; **not a start instruction** |
| Approach | transaction-plus-tombstone, `files_pending_cleanup`, 24 h minimum with its safety conditions accepted — orphan cleanup **report-only** |
| 1 | `ON CONFLICT (storage_key) DO NOTHING`; whole-transaction retries; one level-by-level lock order (project → all AOIs → all non-terminal-checked jobs → all assets) with the project-deletion algorithm rewritten to match; constraint-specific error translation with unexpected integrity failures surfaced as 500 (ADR-0014 §7.5–§7.6) |
| 2 | evaluated `scripts/licences.py` (approval input = empty in-code `APPROVED_COPYLEFT`; register is generated); new version-controlled `docs/licence-acknowledgements.toml` (OA-0001: the owner's Phase 1 decision, "acknowledged for now", recorded provisionally for the 18 packages named in the question; 11 `lightningcss-<platform>` entries pending; corrected 2026-10-05 after an overstatement; four unsupported cases listed); the generator and the register are **not** changed — the generator task is not authorised |
| 3 | plan T5: connector-execution-scoped guard (contextvar, patched only around `fetch()`), subprocess audit-hook test that allows only the test PostgreSQL endpoint and fails on any `geo_connectors` frame on the stack, static import allow-list |
| 4 | plan T4: zero results → existing job status `insufficient_data` (queue contract) = "search completed, no items matched"; no `result` row, no `data_asset`, no confidence/score/interpretation; explanation in `job.error` |
| 5 | ADR §8: orphan cleanup report-only; no destructive mode in 3a |
| 6 | no substantive design change was needed → **ADR-0014 marked Accepted (not Implemented)**; decision, date and conditions recorded in the ADR's *Owner decision record*; commit/push authorised for `docs/status-refresh-adr-0013` (no merge) |

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
- Nothing here exercises live Earth Observation providers (the sandbox cannot reach them; Phase 3 D8: strategy resolved 2026-10-05, live-verification readiness pending).

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
| 0 | all files exist and are internally consistent | open | **open — documented follow-up F-1** | D-2 and §2b item 2: not claimed complete |
| 0 | constraints documented and referenced | open | ticked | `grep` evidence (2/2/1 references) + D-2 acceptance within historical scope |
| 0 | open questions listed | open | ticked | `TASKS.md` section + D-2 |
| 0 | no application code | open | ticked (as of `ca2d4e4`) | D-2 |
| 0 | user review completed | open | ticked | D-2 |
| 1 | forbidden-term scan runs in CI | open | ticked | D-3; CI #3 … #11 step "Scientific guards"; guard limits documented (§6, D-5) |
| 1 | schema pipeline/drift | open | ticked | D-3; CI frontend step; run #2 failed on drift |
| 1 | CI runs lint/type/tests/secret scan | open | ticked | D-3; CI #3 … #11 |
| 1 | `TASKS.md` "CI workflow executed green" | open | ticked | D-3 |
| 2 | composite CRS/limits box | open | ticked | D-4 (upload/archive gap) + each other aspect tied to existing evidence (`acceptance-criteria.md` Phase 2 note); other-CRS reprojection explicitly not claimed |
| 2 | `TASKS.md` "Actions green" on the Phase 2 pushes | open | ticked, **wording clarified** (2026-10-05, §2b item 1) | runs #4 (`2ddef67`) and #5 (`1e7c823`) success; `46596b4` had no independent run, stated in the item |
| 2.5 | `phase-2.5.md` §4 items 1–10 | open | ticked | D-1 (gate closed); verification in §2/§6 of that report, CI #7 (historical), #10, #11 |
| 2.5 | `acceptance-criteria.md` Phase 2.5 items | ticked | ticked | unchanged |
| 3+ | all | open | **open** | not in scope of any decision; Phase 3 not started |

## 9. Remaining gaps and open items (after the owner messages of 2026-10-05)

1. **Follow-up F-1 (Phase 0):** `acceptance-criteria.md` *all files exist and are internally consistent* — open, documented, not claimed complete (D-2; §2b item 2).
2. ~~`TASKS.md` Phase 2 "Actions green"~~ — closed on 2026-10-05 with clarified wording (§2b item 1); no independent run exists for `46596b4`.
3. **F-1 and the phase-start rule:** `CLAUDE.md` §2 (a phase is complete only when every criterion is met and the user confirmed) and `MASTER_SPEC.md` §10 (a phase starts when the previous phase's criteria are met and recorded) conflict with an open Phase 0 criterion under the ordered-chain reading. **Resolved by the owner's narrow exception (2026-10-05, §2c item 2):** F-1 is non-blocking for the fixtures-only Phase 3a slice only; it is not a general change to the rules and not a declaration that F-1 is satisfied; it must be closed before any live connector slice is authorised. Not claimed: that all prerequisite criteria are complete, or that the owner has declared Phase 2 as a whole "complete" (its boxes are all ticked).
4. **ADR-0014:** **Accepted** by the owner on 2026-10-05 (revision 4; not implemented). Acceptance is not a start instruction. Open under it: the generator task for the licence acknowledgements (separately authorised), the implementation branch/base for 3a, and everything listed in the ADR's owner decision record.
5. **D8:** strategy resolved (option D); readiness pending R1–R8 in `docs/phase-3-plan.md` §8a (official-source confirmation of hosts, terms/licences/attribution, limits/costs; allowlist approval or reviewed script; ADR-0014 §9 accepted; start instruction). No host approved; no network change.
6. **Phase 3a** needs a separate, explicit, bounded start instruction (the fixtures-only scope is accepted as scope). Live slices additionally need F-1 closed, D8 readiness R1–R8, approved exact hosts/ports and controls, and a start instruction per slice.
7. D-6 exception expires **2026-11-04**; renewal or remediation decision required; tell the owner if exposure conditions change.
8. Limits that remain true: the terminology guard is a source-text scan (§6); other-CRS reprojection untested (risk P-10); ADR-0008 limits unmeasured; no live provider verification; Phase 5 region gate and Earth Engine eligibility unchanged.
9. The revision described in §2b is **uncommitted**; the CI result of the commit that eventually records it cannot be recorded inside that commit.

## 9a. F-1 — known unresolved documentation-consistency issues (**closed 2026-10-06 — see §9b**; the list below is the historical state; it was not exhaustive)

F-1 = Phase 0 checklist item *all files exist and are internally consistent*. Verified instances (file:line as of this revision) — none has been fixed in this round:

| # | Location | Inconsistency |
|---|---|---|
| F1-1 | `docs/architecture.md:3` | "Status: Draft v0.1" while `MASTER_SPEC.md` is v0.2 and the document already contains the Phase 2.5 section (§2b) |
| F1-2 | `TASKS.md` Backlog (line ~141) | "Authentication / multi-user / **projects**" — projects exist since Phase 2.5 (ADR-0013); only authentication/multi-user are unbuilt |
| F1-3 | `docs/risk-register.md:43` (P-9) | "(OSM default)" — the default basemap is `none` since the Phase 2.5 follow-up |
| F1-4 | `docs/phase-reports/phase-2.md:36, 46` | "GitHub Actions … checked only after push" and "No `project` entity" are stale (header notes only the CORS amendment) |
| F1-5 | `docs/phase-reports/phase-1.md:54`, `docs/phase-reports/phase-2.5.md:3` | "GitHub Actions has not run" / "proposal only" — historical statements; annotated in the header or by a dated note, but still present as plain text |
| F1-6 | `TASKS.md` phase headers; `docs/acceptance-criteria.md` phase headings | "Awaiting owner acceptance" / "Owner acceptance still required" — labelled historical by dated notes but still present as plain text |
| F1-8 | `docs/third-party-licences.md` (header and "Pending owner acknowledgement" section) and `scripts/licences.py` (`APPROVED_COPYLEFT = {}`) | the register says "nothing here has been approved" although the owner provisionally acknowledged ("for now") the packages named in the Phase 1 question on 2026-10-04 (recorded in `docs/licence-acknowledgements.toml` OA-0001; scope narrower than the whole generated list); reconciling the generated register is generator work, not authorised |
| F1-7 | not yet reviewed systematically | `docs/data-model.md`, `docs/job-lifecycle.md`, `docs/dependency-strategy.md` (beyond the driver line), `docs/scientific-constraints.md`, directory READMEs under `apps/`, `workers/`, `packages/`, `infrastructure/` |

(Resolved in this revision, therefore not part of F-1: the "Approved"/"Accepted" vocabulary for ADR-0014.)

**Closure criteria:** every listed item is corrected or explicitly annotated, a systematic pass over F1-7 is recorded, and the owner confirms. **Gate:** non-blocking for fixtures-only Phase 3a (owner exception, 2026-10-05); **must be closed before any live connector slice is authorised.**

## 9b. F-1 reconciliation status (2026-10-06; **F-1 closed with the F1-8 reconciliation; closure is not live readiness**)

Scope of this pass: documentation corrections and a review note only. No code, schema, migration, Compose, CI, test, generated file or licence-generator change; no provider request; **F-1 is not closed and nothing here approves live readiness** (live work still needs F-1 closed, D8 R1–R8 and the owner's explicit start instruction; see `docs/phase-3-plan.md` §8a).

| Item | Status | Evidence / what was done |
|---|---|---|
| F1-1 | **resolved** (2026-10-06 completion pass) | `docs/architecture.md` now has §5a *Phase 3a as built* (backend boundary, migrations 0004–0006, AOI/project/job/asset/provenance/result relationships, queue and worker boundary, `geo_connectors`, `catalog_search` and `CONNECTOR_MODE`, `LocalStorage` staging/publication, tombstones, drain, report-only `reconcile-assets`, deletion guards, explicit absences, deferred live design points); §1, §2, §5 and §8 were annotated or corrected so design intent is not read as implementation. Cross-checked against ADR-0014, `docs/connectors.md`, `docs/data-model.md`, `docs/job-lifecycle.md` and the code layout |
| F1-2 | resolved | `TASKS.md` Backlog now reads "Authentication / multi-user" |
| F1-3 | resolved | `docs/risk-register.md` P-9: "OSM is opt-in; default basemap is none (ADR-0013)" |
| F1-4 | resolved by annotation | `docs/phase-reports/phase-2.md` §3 (CI after push) and §4 item 1 (no project entity) carry dated `[historical]` notes; text kept |
| F1-5 | resolved by annotation | `docs/phase-reports/phase-1.md` (CI "has not run") now carries a `[historical]` note. `docs/phase-reports/phase-2.5.md:3` was left unchanged: the note on line 4 expressly states that the status line and "proposal only" wording are preserved as written and superseded |
| F1-6 | resolved (existing annotations reviewed and accepted as sufficient) | `TASKS.md:25,41,55` carry `[historical, superseded…]` tags with status notes (`:38,:52`); `docs/acceptance-criteria.md` Phase 1/2/2.5 each have a status note immediately below the "Owner acceptance still required" sentence. Left unchanged |
| F1-7 | **resolved for every specified item** (2026-10-06 completion pass); observations recorded below | stale items corrected in `data-model.md`, `job-lifecycle.md`, root `README.md`, `apps/backend/README.md`, `apps/frontend/README.md`, `workers/connectors/README.md`; `packages/pycommon/README.md` added; `scientific-constraints.md` reviewed and annotated as current. Residual observations (not inconsistencies): `docs/dependency-strategy.md` has no row for the `geo-connectors` workspace member and **no HTTP-client or transport entry — client selection remains pending and is not covered there** |
| F1-8 | **resolved** (2026-10-06, F1-8 task) | Owner decision: OA-0001 is the project's explicit acknowledgement for **MPL-2.0 where already present in the locked dependency graph**. Implemented as a narrow policy in `scripts/licences.py`: `[[approved]]` records in `docs/licence-acknowledgements.toml` (AP-0001 certifi 2026.7.22 runtime, AP-0002 pathspec 1.1.1 dev, AP-0003 axe-core 4.13.0 npm dev, AP-0004 lightningcss 1.33.0 npm dev), **MPL-2.0 only**, matched exactly on ecosystem + name + version + licence string + scope; a stale record fails the check; strong copyleft and unknown licences are unchanged; `APPROVED_COPYLEFT` stays empty. The generated register no longer says "nothing here has been approved": it has an *Approved weak-copyleft entries* section citing OA-0001 per package, and the pending section lists only what is still undecided (LGPL entries; the 11 `lightningcss-<platform>` packages, P-0001). Tests: `tests/unit/test_licences_approvals.py`. **Not approved by this:** certifi/httpx or any other package as a *new* runtime dependency, any future MPL-2.0 dependency (needs separate review; a version bump needs a new record) |

**F1-7 systematic-review note (state after the 2026-10-06 completion pass; the first pass at `7242dcf` found the "was" items):**

| File | Result | Was → now |
|---|---|---|
| `docs/data-model.md` | reviewed — **corrected, current** | "current for Phase 2.5" / job relationships "(planned)" / §3 item 1 "planned … 0004 or later" → status line for Phase 3a (migrations 0001–0006), relationship block with `data_asset`, as-built migration 0004 description; engine-result items still marked planned |
| `docs/job-lifecycle.md` | reviewed — **corrected, current** | "only job type is `noop`" and "never retried" → two job types (`noop`, fixtures-only `catalog_search`); retryable-exception path distinguished; no live retry/back-off claimed |
| `docs/dependency-strategy.md` | reviewed — current, **incomplete (recorded, not edited)** | no `geo-connectors` row; no HTTP-client/transport entry (selection pending, ADR-0014 §9–§10); licence column "likely, unverified" as it states |
| `docs/architecture.md` | reviewed (whole) — **corrected, current** | see F1-1 |
| `README.md` (root) | status lines reviewed — **corrected** | Phase 3a "in progress, not accepted" → accepted as fixtures-only (2026-10-06), no live provider/HTTP client/cache/egress control; older statements kept and marked `[Historical …]`; layout and index rows updated |
| `apps/backend/README.md` | reviewed — **corrected, current** | "Not implemented — Phase 1+" → implemented scope and boundaries |
| `apps/frontend/README.md` | reviewed — **corrected, current** | "Not implemented — Phase 1+" → implemented workbench/status/disclaimer/generated types; no UI for jobs/assets/connectors; no 3D |
| `packages/pycommon/README.md` | **added** | was missing |
| `packages/schemas/README.md` | reviewed — current | |
| `workers/README.md` | reviewed — current | |
| `workers/connectors/README.md` | reviewed — **corrected, current** | file list now covers `handler`, `provenance`, `request_hash`, `errors`, fixtures, registry and the no-live-network boundary |
| `workers/{thermal,gold_prospectivity,void_evidence,insar,geophysics}/README.md` | reviewed — current | each "Not implemented — Phase N" |
| `infrastructure/README.md`, `tests/README.md`, `data/README.md` | reviewed — current | |
| `docs/scientific-constraints.md` | reviewed — **current**; dated annotation added | no factual inconsistency with the fixtures-only scope |

**Remaining open under F-1:** **none.** F1-1…F1-8 are resolved and F-1 is **closed** (owner-directed F1-8 reconciliation, 2026-10-06). **Closure of F-1 does not approve live networking, a provider (Earth Search / Element 84 is a candidate for later R1–R3 research only), any host or port, HTTP-client selection, or Phase 3b.** Live work still needs D8 readiness R1–R8 and the owner's explicit start instruction (`docs/phase-3-plan.md` §8a). Residual licence items: P-0001 and the LGPL components stay pending/unapproved.

## 10. Verification of the code baseline

The owner accepted the reported evidence (D-3) and requested no further general verification round. For the record: commit `5ac5a27` has CI run #11 (§3) and a clean-checkout Compose run (§4b, local). The commit recording the owner decisions changes documentation only.

## 11. Owner decision record

| Item | Decision | Date | Where |
|---|---|---|---|
| D-1 Phase 2.5 follow-ups + derived CORS | accepted with limits | 2026-10-05 | §2a |
| D-2 Phase 0 / "no application code" | accepted within the historical scope; confirmed again; F-1 stays open | 2026-10-05 | §2a, §2b |
| D-3 Phase 1 open boxes + TASKS CI box | accepted | 2026-10-05 | §2a |
| D-4 Phase 2 upload/archive boundary tests | accepted (specific) | 2026-10-05 | §2a |
| Phase 2 `TASKS.md` "Actions green" | approved on runs #4/#5 with clarified wording; ancestry of `46596b4` verified from Git (parent of the run #4 tip); no independent run for `46596b4`, no intermediate snapshot tested separately | 2026-10-05 | §2b, §2c |
| D-5 guard + audit gate + `docs/**` trigger | accepted | 2026-10-05 | §2a |
| D-6 dev-only `braces` exception | accepted, temporary, until 2026-11-04 | 2026-10-05 | §7b |
| Commit and push (earlier bounded work) | authorised for `docs/status-refresh-adr-0013` only; merge not authorised | 2026-10-05 | owner messages |
| ADR-0014 | **explicitly Accepted (not Implemented)**, revision 4, with conditions (earlier: direction supported 2026-10-05 §2b/§2c; accepted after r4 §2d) | 2026-10-05 | §2d, `docs/adr/0014-…` *Owner decision record* |
| Phase 3a scope (fixtures-only) | accepted **as scope**, not a start instruction | 2026-10-05 | §2d, plan §6 |
| Licence acknowledgements | OA-0001 recorded provisionally (18 named packages, "for now"; 11 pending; corrected 2026-10-05); four unsupported cases listed for the owner (`docs/licence-acknowledgements.toml`); generator not changed | 2026-10-05 | §2d |
| D8 strategy | **resolved: option D** (3a fixtures-only; live verification mandatory before accepting live slices 3b and DEM; route B preferred subject to separate allowlist approval, else route A) | 2026-10-05 | §2b, plan §8a |
| D8 live-verification readiness | **pending** (R1–R6) | — | plan §8a |
| F-1 and the phase-start rule | **narrow owner exception:** F-1 is non-blocking for fixtures-only Phase 3a only; stays open; must be closed before any live connector slice is authorised; not a change to the rules; 3a start not authorised | 2026-10-05 | §2c, §9 |
| Phase 3a start | **not authorised** — a separate, bounded start instruction is required (it should state the implementation branch/base) | — | §2d |
