````markdown
# InvenTree Warranty Plugin (inventree-warranty-1)

An InvenTree plugin which imports **SafetyCulture (iAuditor)** audit data into InvenTree and derives **warranty-related fields** (e.g. audit date, warranty expiry, identifiers) so you can search, filter, and manage records inside the InvenTree admin UI.

> Repo: `huangderek02/inventree-warranty-1`  
> Plugin key / slug: `warranty` (as used in InvenTree Plugin Settings)

---

## What it does

- Pulls SafetyCulture audits for a configured **Template ID**
- Stores audits as **SafetyCultureRecord** rows in the database
- Extracts and stores fields such as:
  - `audit_id`
  - `sc_modified_at`
  - `unit_sn`, `model_number`
  - `audit_date`, `warranty_expiry`
  - (optional/if present in your template) other identifiers like `ums_sn`, `tm_device_id`
- Provides an **Admin page** for SafetyCulture records with a **Refresh** action to re-sync
- Supports **incremental syncing** using a saved cursor (`SC_SYNC_CURSOR`) to avoid re-fetching everything every time

---

## Requirements

- InvenTree running (commonly via Docker Compose)
- A SafetyCulture API token with access to the audits/template
- The SafetyCulture Template ID you want to sync
- (Recommended) HTTPS/reverse proxy in front of InvenTree if exposed to the internet

---

## Installation (Docker Compose / standard InvenTree)

### 1) Put the plugin into the InvenTree plugins directory

On your server where InvenTree runs:

```bash
cd /opt/inventree-d1

# ensure the plugins folder exists
mkdir -p inventree-data/plugins

# clone into the plugins folder
cd inventree-data/plugins
git clone https://github.com/huangderek02/inventree-warranty-1 warranty
````

> If you prefer a specific tag/commit, `git checkout <tag-or-sha>` inside the `warranty` folder.

### 2) Restart InvenTree

```bash
cd /opt/inventree-d1
docker compose restart inventree-server inventree-worker
```

### 3) Enable the plugin in the InvenTree UI

1. Go to **Admin** → **Plugins**
2. Find **warranty**
3. Enable / activate it

### 4) Apply database migrations (if required)

If the plugin ships Django migrations, run:

```bash
cd /opt/inventree-d1
docker compose exec -T inventree-server sh -lc '
  cd /home/inventree/src/backend/InvenTree &&
  python3 manage.py migrate
'
```

---

## Configuration (Plugin Settings)

In InvenTree admin:

**Admin → Plugin Settings → warranty**

Set the following keys (names may appear exactly like these in Plugin Settings):

| Key              | Example                        | Notes                                      |
| ---------------- | ------------------------------ | ------------------------------------------ |
| `SC_BASE_URL`    | `https://api.safetyculture.io` | Usually the default SafetyCulture API host |
| `SC_TOKEN`       | `...`                          | Your SafetyCulture API token               |
| `SC_TEMPLATE_ID` | `...`                          | The template to pull audits from           |
| `SC_SYNC_CURSOR` | *(auto)*                       | Managed by the plugin for incremental sync |

> Tip: `SC_SYNC_CURSOR` is an internal cursor (ISO-8601) used to pull only audits modified after the last sync.
> If you want a **true full re-import**, clear or ignore the cursor (see below).

---

## Usage

### Admin UI: SafetyCulture Records

Open:

**Admin → Warranty → SafetyCulture records**

From this page you can:

* View imported records
* Search/filter/sort
* Use the **Refresh** action (button/link) to sync from SafetyCulture again

### Re-import behavior (important)

If you **delete a record** in the admin and then click **Refresh**, whether it comes back depends on the sync mode:

* **Incremental sync** (uses `SC_SYNC_CURSOR`) will only fetch audits *newer than the cursor*.
  ✅ Great for daily updates
  ❌ Will *not* re-fetch older audits you deleted

* **Full sync** (ignores/clears cursor) will walk forward from an old timestamp and can restore deleted audits.
  ✅ Restores missing items
  ❌ Slower (pulls more data)

If your goal is: **“Refresh should restore anything deleted”**, configure Refresh to run a **full sync** first (or clear the cursor before it runs).

---

## Manual sync commands

### Run an incremental sync (fast)

```bash
cd /opt/inventree-d1
docker compose exec -T inventree-server sh -lc '
  cd /home/inventree/src/backend/InvenTree &&
  python3 manage.py shell -c "
from warranty import admin as wa
print(wa.run_sc_sync(incremental=True, print_each=False, verify_only=False))
"
'
```

### Run a full sync (restores missing/deleted older audits)

```bash
cd /opt/inventree-d1
docker compose exec -T inventree-server sh -lc '
  cd /home/inventree/src/backend/InvenTree &&
  python3 manage.py shell -c "
from warranty import admin as wa
print(wa.run_sc_sync(incremental=False, print_each=False, verify_only=False))
"
'
```

---

## Logging: processed vs added

To make troubleshooting easier, the sync should log a summary like:

* how many records were **processed** (checked)
* how many were **added** (created)
* how many were **updated**
* how many were **skipped**
* how many **errors**
* what the new cursor is (if incremental)

Recommended log format:

```
SC sync summary: incremental=<...> processed=<...> added=<...> updated=<...> skipped=<...> errors=<...> cursor=<...>
```

If you are patching code to add this:

* Ensure `logger = logging.getLogger(__name__)` exists at module scope
* Log after the `out`/result dict is created, not before

---

## Daily background sync (recommended patterns)

There are multiple ways to run the sync daily:

### Option A — Host cron calling manage.py (simple)

Create a cron entry on the host (example: 3:10am daily):

```cron
10 3 * * * cd /opt/inventree-d1 && docker compose exec -T inventree-server sh -lc 'cd /home/inventree/src/backend/InvenTree && python3 manage.py shell -c "from warranty import admin as wa; wa.run_sc_sync(incremental=True, print_each=False, verify_only=False)"' >/dev/null 2>&1
```

### Option B — Celery beat / scheduled tasks (advanced)

If your InvenTree deployment already uses scheduled Celery tasks, integrate the plugin sync as a periodic task that calls:

```python
wa.run_sc_sync(incremental=True, print_each=False, verify_only=False)
```

This keeps scheduling inside the application stack instead of relying on host cron.

---

## Troubleshooting

### “NoReverseMatch / warranty_sc_refresh_and_verify not found”

* Usually means the admin URL name used in the template does not match what `get_urls()` registers.
* Confirm the template uses:

  ```django
  {% url 'admin:warranty_sc_refresh_and_verify' %}
  ```

  (quotes matter), and that the admin class registers:

  ```python
  path("refresh_and_verify/", ..., name="warranty_sc_refresh_and_verify")
  ```

### “ModuleNotFoundError: No module named 'plugin'”

* This happens when importing plugin code outside the InvenTree Django environment.
* Always run sync commands via:

  ```bash
  python3 manage.py shell ...
  ```

  from the InvenTree backend directory.

### Refresh doesn’t restore deleted audits

* Your refresh is running incremental sync only.
* Run a full sync (incremental=False) OR clear the cursor, then refresh.

---

## Development notes

* Keep all SafetyCulture API access behind well-defined helper functions.
* Prefer idempotent imports:

  * `update_or_create` keyed by `audit_id`
* Avoid “silent failure”:

  * log API errors and parsing exceptions
  * surface a summary in logs after each run

---

## License

Add your chosen license (MIT/Apache-2.0/etc.) in `LICENSE`.

```
::contentReference[oaicite:0]{index=0}
```
