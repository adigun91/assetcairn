# AssetCairn v1.0

## First release

AssetCairn is an IT asset lifecycle manager for tracking ownership, costs, expiry dates, renewals, and reminders.

### Highlights

- First-run organization workspace setup with administrator sign-in and role-based user management.
- Asset register for hardware, software, licenses, subscriptions, certificates, and other IT assets.
- Registration, expiry, and renewal dates with dashboard tracking and reminder thresholds at 30, 15, 10, and 5 days.
- Asset ownership, prices, renewal costs, hardware depreciation details, search, filters, and CSV export.
- AES-256-GCM encrypted asset login credentials with access controls and secret-free security audit events.
- Configurable SMTP reminders with an explicit destination host allowlist.
- Profile avatars, custom roles, Django session authentication, CSRF protection, and security headers.
- Production-oriented request body limits, Content Security Policy, secure cookie/HTTPS settings, and dependency updates.

### Requirements

- Python 3.12 or newer
- Node.js 22.12 or newer

### Validation

- 51 Django tests passed for this release.
- Production frontend build passed.
- npm and Python dependency audits reported no known vulnerabilities at release validation.

### Deployment notes

Configure `DJANGO_DEBUG=false`, a private `DJANGO_SECRET_KEY`, the deployment's allowed hosts and HTTPS origins, an approved `SMTP_ALLOWED_HOSTS`, and outbound SMTP network rules before production use. Configure Redis and edge rate limits when running multiple workers. Real SMTP delivery and external production infrastructure are not included in the local test validation.