# Tests

- `unit/` – pure logic
- `integration/` – API/DB/queue boundaries (offline; mocked external sources)
- `scientific/` – guard tests: forbidden-claim scans, envelope completeness, depth gating, deterministic fixtures with documented expectations

No live network calls in CI. Never skip or weaken tests to get green.
