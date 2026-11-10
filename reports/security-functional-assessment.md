# Security, Functional, Regression, Vulnerability and Penetration Assessment

Assessment date: 2026-11-02. Scope: the current local Django/React application, resolved dependencies, an isolated localhost Waitress instance, and Django test databases.

## Verdict

Functional and regression checks passed for the exercised workflows. Security controls blocked the exercised unauthorized actions. **Production security sign-off is withheld** because dependency advisories and confirmed hardening gaps remain. A passing test suite is not a finding-free penetration-test certification.

No application code or dependency versions were remediated during this assessment. Eleven repeatable security-assessment tests were added. The Python audit utility was installed only in the project virtual environment. No external target, password guessing against live accounts, denial-of-service attack, real SMTP send, or modification to live users/assets was performed.

## Remediation Follow-up (2026-11-10)

This addendum supersedes the earlier finding status where noted; the findings and evidence below remain the original 2026-11-02 baseline.

- **F1/F3: Resolved for the scanned Python packages.** Upgraded Django REST Framework to 3.18.2, cryptography to 50.0.0, and Pillow to 13.0.0. Current `pip-audit`: **no known vulnerabilities**; `pip check`: **no broken requirements**. The bounded JSON parser now rejects requests above the configured 10 MiB limit with HTTP 413; a regression test confirms the rejected request does not create an asset.
- **F2: Production configuration hardened.** `DEBUG` now defaults to false. Development launch explicitly enables it; production launch refuses to start unless `DJANGO_DEBUG=false` and a private `DJANGO_SECRET_KEY` are set. `manage.py check --deploy` under production-mode settings reports no issues. HTTPS termination, correct public hosts/origins, and proxy behavior still require deployment-specific configuration and verification.
- **F4: Application-level SMTP allowlist implemented.** Saved SMTP hosts must match `SMTP_ALLOWED_HOSTS`; a private relay can be used only when explicitly allowlisted. Outbound firewall/egress rules remain an operator responsibility, including protection against DNS changes or rebinding for approved names. No real SMTP connection was made during this follow-up.
- **F5: CSP implemented on Django-served responses.** The policy permits only the app origin plus the configured Google Fonts and Unsplash resources and blocks objects/framing. The Vite development server does not carry the production Django CSP and must remain loopback-only.
- **F6: Shared cache support added.** Setting `REDIS_URL` selects Django's Redis cache backend; otherwise development uses process-local memory. Redis coordination was not runtime-tested because no Redis service or Docker daemon was available. Production should configure Redis and edge rate limits for multi-worker deployments.
- **F7: Credential and SMTP audit events implemented.** Actor, asset (where applicable), action, and timestamp are stored. SMTP metadata contains only host and port; credential values are not stored. The audit table is not exposed as a user-facing endpoint.
- **Vite workspace-file exposure: Mitigated.** The development server now denies backend source, Python files, runtime data, and SQLite files. Browser checks returned 403 with no file content for the database and source paths. Django itself returned 404 for the same paths.
- **Verification:** `npm test` passed **50 tests**; `npm run build` passed; migration consistency check reported no changes; production-mode `check --deploy` reported no issues; `npm audit` reported zero known npm vulnerabilities; `pip-audit` reported no known Python vulnerabilities. Browser checks confirmed CSP, auth gating, file blocking, and version-silent headers.

Remaining deployment checks: configure and verify the actual HTTPS reverse proxy and public host/origin settings; set the SMTP host allowlist and outbound firewall policy; provision and exercise the shared Redis service; and run a post-deployment external scan against the authorized public endpoint. The current validation did not include real SMTP delivery, load testing, external penetration testing, or production infrastructure.

## Findings (Priority Order)

### F1: High Priority - DRF Advisories and Confirmed JSON Body-Limit Bypass

Installed Django REST Framework: **3.16.1**. The Python scanner reports five distinct advisory IDs for this package. A small safe test with `DATA_UPLOAD_MAX_MEMORY_SIZE=128` still accepted a JSON asset request containing a 512-character notes field. This confirms that the Django setting alone is not enforcing the intended limit on this DRF path; it does not demonstrate actual resource exhaustion.

Evidence: `assets/tests/test_security_assessment.py`, test `test_json_parser_accepts_body_above_django_upload_limit`; `assets/views.py` consumes `request.data`; `reports/python-audit.json`.

Recommended action: review upstream fixes and upgrade DRF to a release covering all reported advisories (scanner recommends 3.18.2 for the latest ones), revise the `<3.17` dependency constraint, and enforce bounded request bodies and headers at the application/reverse-proxy layer. Retest JSON and Accept-header handling after remediation. No large/compressed payload or Accept-header exhaustion attack was attempted.

### F2: High if Deployed Unchanged - Development Security Settings

Current runtime: `DEBUG=True`, session cookies not Secure, CSRF cookies not Secure, no enforced HTTPS redirect or HSTS. Django `check --deploy` reported **security.W004, W008, W012, W016, W018**. These are expected for the loopback development instance, but unacceptable for a public deployment containing credentials.

Evidence: `backend/settings.py:10`, secure-cookie/HTTPS settings, and runtime inspection. A separate check with temporary production settings (`DJANGO_DEBUG=false`, a strong random secret, a restricted host and HTTPS trusted origin) reported **no issues**. The live configuration was not changed.

Recommended action: use production settings, HTTPS, a trusted reverse proxy and appropriate host/origin restrictions before exposure. Protect database and key backups and do not serve Vite or Django runserver publicly.

### F3: Medium Priority - Cryptography Dependency Advisories

Installed `cryptography`: **48.0.1**. The scanner reports three distinct advisories affecting X.509 certificate verification and PKCS7 decryption. This application uses AES-GCM and Fernet, not those affected APIs; **no AES-256-GCM weakness was demonstrated**. The dependency is still flagged and the manifest's `<49` constraint prevents installing the reported fixes.

Recommended action: verify upstream applicability, revise the version constraint and upgrade to a version covering all advisories (scanner lists 50.0.0 for the PKCS7 issue), then rerun crypto, migration and full regression tests.

### F4: Medium, Privileged - Unrestricted SMTP Destination

A user with `reminders:manage` can save `host=127.0.0.1` and an arbitrary valid port. A mocked connection check confirmed those values flow to Django's SMTP backend. No socket to an internal service was opened. Unprivileged viewers were denied configuration/test-mail access.

Evidence: `assets/email_config.py:46` and `assets/email_config.py:67`; test `test_privileged_smtp_settings_accept_loopback_destination`.

Impact: a compromised or untrusted reminder operator can initiate SMTP-shaped connections to internal destinations or an attacker-controlled mail server. This is a restricted server-side connection/SSRF risk, not an unauthenticated exploit. Internal SMTP relays may be intentional, so blanket private-address blocking may break valid deployments.

Recommended action: allowlist approved SMTP hosts and ports, enforce outbound network restrictions, restrict this permission, and account for DNS resolution/rebinding. Consider approval and audit trails for email destination changes.

### F5: Medium Hardening Gap - No Content Security Policy

Responses have no `Content-Security-Policy`. A browser test confirmed an HTML-like asset name rendered literally rather than creating an image element, so stored XSS was **not** demonstrated in that path. A CSP would add defense in depth.

Evidence: `test_headers_do_not_include_content_security_policy` and local HTTP probes. Recommended action: introduce a production CSP tailored to the React bundle and currently used Google Fonts/Unsplash resources, preferably in report-only mode before enforcement. External fonts and imagery also create external network dependencies.

### F6: Medium for Multi-Worker Deployment - Process-Local Throttling

The configured cache is `django.core.cache.backends.locmem.LocMemCache`. The auth throttle correctly returned 429 after 30 mocked failed attempts from one IP and permitted a separate test IP. Contrary to a preliminary review flag, it **is per IP** for anonymous requests in one process. However, counters are not shared across workers/process restarts, and DRF throttles are not a complete brute-force defense.

Evidence: runtime cache inspection, `backend/settings.py:83`, and test `test_login_throttle_is_per_ip_in_one_process`.

Recommended action: use a shared cache and edge rate limits for production, configure trusted proxy handling, and consider account-aware protections and monitoring. Distributed brute-force testing was not performed.

### F7: Medium Operational Gap - No Credential-Access Audit Trail

Credential retrieval is permission-protected, excludes secrets from asset lists and exports, and uses no-store responses. The current credential endpoint does not persist an audit event for retrieval or credential changes. Authorized plaintext retrieval is an intended feature, **not** a critical disclosure vulnerability by itself.

Evidence: `assets/views.py:159`. Recommended action: record actor, asset ID, timestamp and action without credential values; consider recent reauthentication for sensitive retrieval. No broad credential enumeration was performed.

## Dependency Scan Evidence

- `npm audit --json`: **0 known vulnerabilities**, metadata reports 117 dependencies total (production/development/optional trees have overlapping counts).
- GitHub advisory assessment of the five resolved direct npm packages: **0 known CVEs**. Artifact: `reports/npm-cve-assessment.json`.
- `pip-audit` against the installed virtual environment: **11 entries in 2 packages**, deduplicated to **8 advisory IDs**. Artifact: `reports/python-audit.json`. Scan included audit-tool dependencies; only the two application packages below were flagged. A scanner result is not proof of exploitability and cannot exclude unknown vulnerabilities.

| Package | Installed | Advisory | Related CVE | Scanner Fix |
| --- | --- | --- | --- | --- |
| cryptography | 48.0.1 | PYSEC-2026-3554 | CVE-2026-69248 | 49.0.0 |
| cryptography | 48.0.1 | PYSEC-2026-3552 | CVE-2026-69247 | 50.0.0 |
| cryptography | 48.0.1 | PYSEC-2026-3553 | CVE-2026-69249 | 49.0.0 |
| djangorestframework | 3.16.1 | PYSEC-2026-3827 | CVE-2026-73228 | 3.17.2 |
| djangorestframework | 3.16.1 | PYSEC-2026-3828 | CVE-2026-73229 | 3.17.2 |
| djangorestframework | 3.16.1 | CVE-2026-114138 | Same ID | 3.18.2 |
| djangorestframework | 3.16.1 | CVE-2026-114136 | Same ID | 3.18.2 |
| djangorestframework | 3.16.1 | CVE-2026-114137 | Same ID | 3.18.2 |

The AdminRenderer and TokenProxy advisories were not exercised because this app uses a JSON renderer and session authentication. Cryptography X.509/PKCS7 behavior was not exercised. Full upstream descriptions, aliases and fix versions are preserved in the raw Python report.

## Executed Checks

### Automated Functional, Security and Regression Tests

Baseline: **31 tests passed**. Eleven assessment tests were added and passed independently. Final canonical `npm test`: **42 tests passed, zero failures**, in 63.269 seconds. The canonical command includes all test modules, including the newly added assessment tests. Existing coverage exercises:

- Administrator setup, production setup-token protection, email login and password hashing.
- User/role creation, role permissions, deactivation and last-administrator safeguards.
- Asset create/update/delete, duplicate tags, calendar dates, date ordering and notification recipients.
- AES-256-GCM fresh nonces, authenticated tamper rejection, wrong-key failure and legacy migration.
- Owner/manager credential access, unassigned-user rejection and reassignment revocation.
- SMTP encryption, secret-free settings responses, invalid configuration and sanitized failed-mail responses.
- 30/15/10/5-day reminder thresholds, deduplication, catch-up, renewal resets, delivery failure retries, retired/expired exclusions and overlapping-job locks.
- Removal of identifying response headers, including real Waitress success/error responses.

New assessment checks cover hostile CSRF origins, malformed JSON, unsupported methods, a SQL-like login input, protected privilege fields, copied-session invalidation after logout, password-reset invalidation, immediate role permission changes, per-IP auth throttling, and the three recorded SMTP/CSP/body-limit gaps. **Gap tests assert the observed risky behavior**, so a green result does not mean these gaps are fixed. Convert those tests to enforce the desired behavior during remediation.

### Local HTTP Penetration Probes

Nine small unauthenticated GET requests were sent to the isolated `127.0.0.1:3031` target:

- `/api/assets`, `/api/users`, `/api/roles`, `/api/reminders/email`, `/api/assets/1/credentials`: **401**.
- `/.env`, `/data/django.sqlite3`, `/backend/settings.py`: **404**, no file contents served.
- `/api/health`: **200**.
- Responses disclose no `X-Powered-By` or Server version; an empty Server header remains. CSP is absent.

### Browser Functional and XSS Checks

Executed against a fresh isolated SQLite database with in-memory email and no reminder worker:

- First-account setup, asset creation with dates/owner/credentials: **PASS**.
- Custom-role and user creation; new-user default Viewer role: **PASS**.
- Asset edit and renewal-date changes; tag search: **PASS**.
- HTML-like asset name rendered as text with no injected image element: **PASS**.
- Credential Show/Hide after AES-GCM storage: **PASS**; password later auto-hid as designed.
- SMTP form available; manual reminder sending disabled without configuration: **PASS**.
- Logout/login as read-only custom-role user; no Add asset controls: **PASS**.
- Read-only user's users API and another owner's credential API: **403**.
- 390px mobile viewport: no page-wide horizontal overflow.
- CSV export: **UNVERIFIED**. The hidden browser produced no detectable download event. Review/download verification in a visible browser is still required.

The shared browser was hidden. Ordinary click-stability checks and animation-frame waits timed out. DOM click/native form submission and polling-based checks were used for the completed browser flows. Full visible-browser pointer/keyboard ergonomics and fresh visual screenshot review are not certified by this run. Production frontend build: **PASS**.

## Reproduce and Limitations

```powershell
npm test
node scripts/django.mjs test assets.tests.test_security_assessment
npm run build
node scripts/django.mjs check --deploy
npm audit --json
.\.venv\Scripts\python.exe -m pip_audit --format json --output reports/python-audit.json
```

The isolated test server is stopped after assessment. The live application is returned to its normal browser URL. No external production domain, proxy/firewall, Microsoft 365 tenant, actual SMTP acceptance/inbox delivery, unattended scheduled-task operation, load testing, race-condition stress test, comprehensive fuzzing, exploit-chain validation or recovery drill was tested. SQLite and encrypted data backups and key custody were not audited. Debug test output includes an intentional Waitress exception used by the existing header test; that is not an unexpected application failure. A missing staticfiles directory warning also appears; run collectstatic as part of deployment.

Next step: remediate F1 and review F3 dependency fixes, apply production hardening and outbound SMTP restrictions, then rerun this assessment and visible-browser export checks before deployment.

The final run additionally logged a Windows `WinError 10038` socket error from the Waitress header-test server during teardown after Django reported `OK`. The command exited successfully and no assertion failed. This is test-harness cleanup noise requiring a separate cleanup review, not a demonstrated production request failure.