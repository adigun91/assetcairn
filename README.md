# AssetCairn

IT asset lifecycle management for tracking ownership, costs, expiry dates, renewals, and reminders.

A React interface with a **Django 5.2 LTS backend**, Django REST Framework, SQLite, Django session authentication, and Django email delivery. No Express backend is used.

## Features

- First-run administrator setup and email/password login.
- User creation, role assignment, account deactivation, password changes, and password resets by administrators.
- Self-service profile page: users can upload or remove a profile photo; name, email, and role are read-only there.
- Built-in Administrator, Asset Manager, and Viewer roles, plus custom permission-based roles.
- Asset creation, editing, retirement, deletion, search, filters, and CSV export.
- Asset detail pages with asset price and expected renewal price columns for every category.
- Hardware-only depreciation setup: acquisition cost, salvage value, useful life in months, method, and depreciation start date.
- Separate registration, expiry, and expected renewal dates, with owner and notification email fields.
- Expiry dashboard and email reminders at **30, 15, 10, and 5 days** before expiry.
- Persisted reminder delivery history, retries on eligible checks, and a database lease to prevent overlapping runs.

## Quick Start (Windows)

Open **My profile** from the top-right avatar. Choose a JPEG, PNG, or WebP image up to 5 MB and save it. The server validates and re-encodes the upload to a normalized JPEG thumbnail. Users cannot change their email address on the profile page; administrators can manage account details through user administration.

Requires Python 3.12 or newer and Node.js 22.12 or newer. Python 3.14.5 is configured in this workspace.

The local virtual environment and dependencies have already been installed. From the project directory:

```powershell
npm run dev
```

The launcher applies Django migrations, starts Django, starts the reminder worker, and starts Vite. Open the frontend URL printed by the launcher, normally **http://localhost:5173**. It chooses another local port if that port is occupied.

On first use, create your administrator account using an organization email address. Common personal email providers such as Gmail, Yahoo, Outlook, iCloud, and Proton are rejected during initial setup; custom organization domains are accepted. This blocks common consumer mailboxes but does not independently verify company registration or domain ownership. There is no default password. Then add users, assign roles, and register assets. New users default to the Viewer role. Passwords require at least 12 characters and must pass Django password validation.

For a fresh installation:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
npm run dev
```

## Asset Login Credentials

On the Asset register, choose **Add asset** and fill in the **Login credentials** section with an optional username, password, and HTTP/HTTPS login URL. Assign the asset using **Assigned owner**. Existing assets have a **Login credentials** column with a key button; the same dialog is available from **Edit asset > Manage login credentials**.

Each asset's name and row open its detail page. The detail page shows its lifecycle, owner, prices, notes, login-credential status, and saved hardware depreciation details. The register includes **Asset price** and **Renewal price** columns for all categories. The existing annual running cost remains a separate field.

When **Hardware** is selected, optional depreciation fields appear: acquisition cost, salvage value, useful life (months), depreciation method (straight-line or double-declining balance), and start date. If any depreciation value is entered, acquisition cost, useful life, method, and start date are required. Salvage defaults to zero. Salvage cannot exceed acquisition cost, and changing the category away from Hardware clears depreciation details. Depreciation figures are stored as asset details; the current dashboard does not calculate a book value or accumulated depreciation.

Asset managers can add, replace, or remove credentials. The currently assigned user can view them, but cannot change them unless their role also grants Manage assets. Other viewers cannot retrieve them. Reassigning an asset revokes the previous owner's access immediately on subsequent requests.

Asset credentials are encrypted together using **AES-256-GCM**, with a fresh random 96-bit nonce for every write and authenticated tamper detection. A purpose-specific 256-bit key is derived from the Django secret using HKDF-SHA-256. These passwords are reversibly encrypted, not hashed, so authorized users can retrieve them. Application sign-in passwords remain hashed by Django.

Migration 0005 converts existing Fernet asset credentials to AES-256-GCM without changing their values. Preserve the original Django secret with secure backups: losing or replacing it makes existing credentials unreadable. This protects database-only exposure, not a compromised application server. Use HTTPS for deployment and grant Manage assets only to trusted staff. Historical database backups may still contain the previous encryption format; handle and retire those backups according to your retention policy.

Passwords are masked by default, revealed only on demand, and hidden again after 30 seconds or when the dialog closes. Leaving the replacement-password option unchecked preserves the saved password. Credential values are excluded from normal asset responses, CSV exports, and reminder emails. Credential responses are marked no-store. To delete credentials, select **Remove all saved login credentials** and confirm with **Remove credentials**.

## Email Configuration

Open **Reminders > Email configuration** with a role that has Manage reminders permission. Enter the SMTP server, port, encryption, sender email, username, and provider password or app password. Click **Save email settings**, then enter a test recipient and click **Send test email**. Check the recipient's inbox and spam folder. Saved settings are used by both manual checks and the reminder worker without a restart.

SMTP settings are encrypted in the database with Fernet using a key derived from the Django secret. The password is never returned by the API. Preserve and securely back up the original Django secret; replacing it makes saved SMTP settings unreadable until you restore the secret or save new settings. Restrict Manage reminders permission to trusted operators because it permits configuring outbound SMTP connections. Saved settings override environment defaults. Neither saving settings nor the SMTP configured indicator proves delivery; the test-email action checks mail-server acceptance.

Alternatively, create a local `.env` using the keys in `.env.example`, then set your provider's values privately:

```dotenv
SMTP_HOST=smtp.your-provider.example
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=your-smtp-account
SMTP_PASS=your-smtp-password
SMTP_FROM=assets@your-company.example
```

These are placeholders, not working credentials. Never commit credentials. Use port 587 with `SMTP_SECURE=false` for STARTTLS or port 465 with `SMTP_SECURE=true` for implicit TLS, according to your provider. Some Microsoft 365 tenants disable basic SMTP authentication; use an approved SMTP relay if your tenant requires it.

For deployment, set `SMTP_ALLOWED_HOSTS` to a comma-separated allowlist of administrator-approved SMTP hostnames. The default allows only `SMTP_HOST`; a saved SMTP destination outside the allowlist is rejected. Private relay addresses work only when explicitly allowlisted. Also restrict outbound network access at the host or firewall so an approved DNS name cannot be used to reach unintended internal services. SMTP destination changes and asset credential views/changes are recorded in the `SecurityAuditEvent` table; secret values are never stored in audit metadata.

Restart the app and reminder worker after changing environment defaults. Real email delivery requires valid SMTP settings and has not been tested against your provider.

Each eligible asset sends to its active owner and its additional notification address, deduplicated case-insensitively. An active asset needs at least one of these recipients. Deactivating an owner removes that owner's address from subsequent sends; keep an additional IT address for continuity.

## Reminder Schedule

`npm run dev` and `npm start` both start a separate Django reminder worker. It checks on startup and then daily at **08:00 UTC**, while running. Dates use UTC calendar days.

Run an immediate check with the Reminders screen or:

```powershell
npm run reminders
```

To use Windows Task Scheduler independently of the web app:

```powershell
.\scripts\Register-ReminderTask.ps1
```

The registration script creates a limited-privilege daily task for your current Windows account at the local equivalent of 08:00 UTC. It runs while your account is signed in and catches up when available. Re-register after daylight-saving time changes. For unattended delivery while signed out, deploy on an always-on server or configure a scheduler under a dedicated service account directly in Windows. No scheduled task is registered automatically.

On Linux, schedule the command using cron or a service timer; for example, in a UTC-configured scheduler:

```cron
0 8 * * * cd /path/to/project && /path/to/project/.venv/bin/python manage.py send_reminders
```

If a scheduled day is missed, the next check sends only the current most urgent applicable threshold instead of sending all missed emails. For example, 14 days remaining uses the 15-day reminder. Sent reminders are stored per asset, expiry date, threshold, and recipient. Changing the expiry date starts a new reminder cycle. Failed deliveries are retried on the next eligible check. Expired and retired assets are excluded; an unsent 5-day reminder can catch up on the expiry day.

SMTP and the database cannot participate in one transaction: a process crash after SMTP accepts a message but before the delivery record is saved can result in a duplicate on retry. "Sent" means the email backend accepted the message, not that the recipient opened it or that delivery is guaranteed.

## Commands

```powershell
npm test
npm run build
npm run migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
npm start
```

`npm test` runs the Django API and reminder tests against an isolated test database with an in-memory email backend. `npm start` serves the built React app using Waitress and runs the reminder worker. Its default local URL is http://localhost:3001. Node launch scripts only orchestrate processes; Django handles all backend requests.

## Deployment and Data

### HTTP Response Headers

The outermost Django middleware removes `X-Powered-By`, `X-AspNet-Version`, and `X-AspNetMvc-Version`, and sets `Server` to an empty value to prevent the development WSGI server from adding its Python/version banner. The production launcher also passes `--ident=` to Waitress to suppress its default identification, including on server-generated errors. An empty `Server` header may remain on application responses; it contains no server name or version.

A reverse proxy or hosting platform can add its own headers after Django responds. Configure that layer separately if deployed behind IIS, nginx, Apache, or a load balancer, and check the public URL's response headers after deployment. Header suppression reduces fingerprinting but does not replace patching, HTTPS, or secure production configuration.

SQLite data is stored in `data/django.sqlite3`. The obsolete Node backend has been removed. Any old Node database is left untouched and is not automatically imported into Django.

For deployment, set `DJANGO_DEBUG=false`, a strong `DJANGO_SECRET_KEY`, your actual `DJANGO_ALLOWED_HOSTS`, HTTPS `CSRF_TRUSTED_ORIGINS`, and an approved `SMTP_ALLOWED_HOSTS`. `npm start` refuses to start unless debug is disabled and a private secret is set. Set a private `SETUP_TOKEN` before creating the first administrator. Serve behind an HTTPS reverse proxy and only enable `TRUST_PROXY=1` when that proxy reliably replaces incoming forwarding headers. Production cookies are HTTPS-only; the Django app adds a Content Security Policy for the bundled UI and its required font/image hosts. Set `HOST=0.0.0.0` only when intentionally exposing the service behind your firewall/proxy. Run migrations, build, and collect static files before starting Waitress.

JSON API request bodies default to a 10 MiB limit, configurable with `MAX_REQUEST_BODY_SIZE`. For multiple Waitress workers or hosts, configure a shared Redis cache using `REDIS_URL`; otherwise login throttling uses process-local memory and does not coordinate across workers. Add equivalent rate limits at the reverse proxy or hosting edge. Do not expose the Vite development server (`npm run dev`) to a network; its file-serving rules block backend/data paths, but production traffic must use the built frontend served by Django/Waitress.

Back up SQLite consistently using SQLite's backup facilities or while the application is stopped. Also preserve the configured Django secret to keep sessions valid. Use local server storage rather than an actively synchronized OneDrive database directory for production. This initial implementation is designed for one Django deployment with a local SQLite database; use PostgreSQL and a distributed job system before scaling to multiple hosts.