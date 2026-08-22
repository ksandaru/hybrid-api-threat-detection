# Demo Guide

A start-to-finish walkthrough that brings the whole system up in Docker and
demonstrates it detecting the three attacks it was built for — SQL injection,
brute force, and credential stuffing — with nothing installed on the machine
except Docker.

Everything below runs against **this project's own local API only**. The
"vulnerable" search endpoint builds an unsanitised query and returns it for
inspection but never executes it; the credential-stuffing pairs are synthetic.
No external system is ever contacted.

---

## 1. What you need

- **Docker Desktop** (Windows or macOS) or **Docker Engine + Compose** (Linux),
  version 24 or newer. This is the only prerequisite for the demo itself.
  - Windows/macOS: install Docker Desktop from docker.com, launch it, and wait
    for the whale icon to report "running".
  - Linux: `docker` and the `docker compose` plugin from your distribution.
- Verify it is working:

  ```bash
  docker --version
  docker compose version
  ```

- **The trained models must be present** in `ml/models/`. They are bind-mounted
  into the inference container rather than shipped in the image, and they are
  not in version control. Check:

  ```bash
  ls ml/models
  ```

  You should see `random_forest.pkl`, `xgboost.pkl`, `isolation_forest.pkl`,
  `scaler.pkl` and `feature_order.json`. If the directory is empty, produce them
  once (this needs the Python environment and the datasets; see the README) with:

  ```bash
  python ml/preprocess.py
  python ml/train.py
  ```

  On the demonstrator's own machine these already exist, so this step is
  normally just the `ls` check.

---

## 2. One-time setup: the demo configuration

Copy the demo environment file into place:

```bash
cp demo.env .env
```

On Windows PowerShell:

```powershell
copy demo.env .env
```

This turns on two settings the demo needs: `TRUST_PROXY=1` (so the simulator's
clients present distinct source addresses) and `DETECTION_TRACE=1` (so the
detection score is attached to every response). Compose reads `.env`
automatically on **every** command, which is what makes these settings stick —
a shell-exported variable would be silently dropped the moment the simulator
service starts the API as a dependency.

---

## 3. Bring the stack up

```bash
docker compose up -d --build
```

This builds and starts three services on a private network:

| Service | What it is |
|---|---|
| `db` | PostgreSQL — stores every inspected request as the evaluation record |
| `ml` | FastAPI inference service — the Random Forest, XGBoost and Isolation Forest |
| `api` | Node/Express API with the detection middleware in front of every route |

The first build takes a few minutes. The API waits for the other two to report
**healthy** before it starts, so once it is up the whole stack is ready. Watch
them reach healthy:

```bash
docker compose ps
```

Wait until all three show `(healthy)`. The inference service takes longest —
it loads ~46 MB of models — but is usually healthy within 20 seconds.

Confirm the API answers:

```bash
curl http://localhost:3000/health
```

Expected: `{"status":"ok","window":{"sources":0,"endpoints":0,"events":0}}`.

---

## 4. Demonstrate detection by hand

These commands show the system deciding, one request at a time. Each blocked
response carries the score that drove the decision and the rules that fired —
good for narrating a live demo.

### Benign traffic passes

```bash
curl "http://localhost:3000/api/search/vulnerable?q=laptop"
```

Returns `200` with search results. A normal query is allowed.

### SQL injection is blocked

```bash
curl "http://localhost:3000/api/search/vulnerable?q=%27%20UNION%20SELECT%20username%2C%20password%20FROM%20users%20--"
```

Returns `403` with a body naming the rules that fired
(`SQLI_UNION_SELECT` and others) and a score of `1.0`. That payload is
`' UNION SELECT username, password FROM users --`, percent-encoded for the
shell.

Try the obfuscated tautology that the original rules missed — it is now caught,
and the response shows the classifier contributed:

```bash
curl "http://localhost:3000/api/search/vulnerable?q=%2F%2A%2A%2FOR%2F%2A%2A%2F1%3D1"
```

(`/**/OR/**/1=1`) returns `403`. Look at the `X-Detection-Ml-Score` response
header to see the ML term's contribution:

```bash
curl -sD - -o /dev/null "http://localhost:3000/api/search/vulnerable?q=%2F%2A%2A%2FOR%2F%2A%2A%2F1%3D1" | grep -i x-detection
```

### A legitimate login is *not* blocked

```bash
curl -X POST http://localhost:3000/api/auth/register -H "Content-Type: application/json" -d "{\"username\":\"demo\",\"password\":\"demo-pass-123\"}"
curl -X POST http://localhost:3000/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"demo\",\"password\":\"demo-pass-123\"}"
```

Register returns `201`, login returns `200` with a token. This is the case the
Phase 8 fix repaired: the payload classifier is not applied to credential
bodies, so an ordinary login is no longer mistaken for an attack.

---

## 5. Demonstrate detection at scale

The simulator is a fourth container under the `sim` profile. It runs many
clients, each with a distinct source, and writes a labelled CSV per attack type.

**First, clear the detection window.** The manual requests you just sent in step
4 are still inside the API's 60-second behavioural window, and the simulator
refuses to measure against traffic it did not send. Restarting the API empties
the window instantly:

```bash
docker compose restart api
```

(If you skip this, the simulator does not fail — it just waits, printing
progress, until the window drains on its own within a minute.)

Then run every generator in order (benign traffic, then SQLi, brute force, and
credential stuffing), waiting for a clean detection window between each:

```bash
docker compose --profile sim run --rm sim
```

Expected summary (numbers are stable — the generators use fixed seeds):

```
benign:              114 requests,   2 blocked (1.8%)
sqli:                 26 requests,  26 blocked (100%)
brute_force:          31 requests,  26 blocked  — blocking began at attempt 5
credential_stuffing:  46 requests,  38 blocked  — blocking began at username 5
```

What each line demonstrates:

- **Benign 1.8%** — ordinary traffic is almost never blocked. (Rules-only would
  be 0%; the ~2 blocks are genuinely ambiguous searches like `logitech's mx
  master`, where an apostrophe is a real SQL-injection signal.)
- **SQLi 100%** — every injection family is caught, including the obfuscated
  ones the signature rules alone missed.
- **Brute force blocks at attempt 5** — a brute force cannot be identified from
  one failed login; the behavioural rule fires once the failure rate builds.
- **Credential stuffing blocks at username 5** — the rule triggers on the breadth
  of distinct usernames from one source, exactly its designed threshold.

Run a single generator instead of all four:

```bash
docker compose --profile sim run --rm sim python sqli_attack.py
```

(swap in `brute_force.py`, `credential_stuffing.py`, or `benign_traffic.py`).

---

## 6. Recalibrate the threshold on the generated traffic

This is the analysis that turned the raw traffic into the Phase 8 result. It
sweeps the decision threshold over the recorded scores and reports where the
false positives fall.

```bash
docker compose --profile sim run --rm sim python recalibrate_threshold.py
```

It prints the operating point at the current threshold and a recommendation,
and writes `evaluation/threshold_recalibration.md`. The per-endpoint table in
that report is the key evidence: the false positives concentrate on the auth
endpoints, which is why the fix was to scope the classifier to search traffic
rather than to move the threshold.

The per-request CSVs are on the host under `evaluation/traffic/`, one per
generator, with each request's label, score, and outcome.

---

## 7. Show the baseline configurations

The same stack runs as three of the four Phase 9 comparison configurations, by
changing one line in `.env` and recreating the API. No code changes.

Rules only (no classifier):

```bash
echo "DETECTION_MODE=rules" >> .env
docker compose up -d api
```

Detection off (the no-control baseline — everything is allowed and logged):

```bash
# edit .env: set DETECTION_MODE=off
docker compose up -d api
```

Return to the full hybrid by removing the `DETECTION_MODE` line (or setting it
to `hybrid`) and running `docker compose up -d api` again.

---

## 8. Inspect the evidence in the database

Every inspected request is stored with its feature vector and decision. The
database is Postgres, running in the `db` container. There are two ways in.

### One-off queries (fastest)

```bash
docker compose exec db psql -U detector -d api_threat_detection -c "SELECT decision, count(*) FROM request_log GROUP BY decision;"
```

```bash
docker compose exec db psql -U detector -d api_threat_detection -c "SELECT path, decision, features->>'sql_keyword_count' AS kw, features->>'requests_per_min_ip' AS rate FROM request_log WHERE decision='blocked' LIMIT 10;"
```

### An interactive session (to poke around freely)

```bash
docker compose exec -it db psql -U detector -d api_threat_detection
```

You now have a `psql` prompt inside the container. Useful commands once inside:

| Type this | It does |
|---|---|
| `\dt` | List the tables |
| `\d request_log` | Show the columns of `request_log` |
| `SELECT * FROM request_log ORDER BY created_at DESC LIMIT 5;` | Show the 5 most recent requests |
| `SELECT count(*) FROM request_log WHERE decision='blocked';` | Count how many were blocked |
| `\q` | Exit back to your normal terminal |

Every SQL command ends with a semicolon `;` — that's what tells Postgres "run it now".

### A visual, point-and-click option

If typing SQL isn't comfortable, any free Postgres GUI (DBeaver, TablePlus,
pgAdmin) can connect directly, because the database port is exposed to your
machine. Connection details:

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `api_threat_detection` |
| Username | `detector` |
| Password | `detector123` |

These are the local demo defaults from `docker-compose.yml` — fine here, not
something you'd ship to a real deployment.

---

## 9. Shipping this project to another laptop

The project folder on disk is large — the Python environment, datasets, and
build tools add up to a couple of gigabytes — but **almost none of that needs
to travel**. A Docker image already contains everything needed to *run* the
system: the code, the language runtime, all dependencies, baked in. The
several-hundred-MB-to-multi-GB folders on your machine (`ml/venv`, `datasets/`,
`api/node_modules`) exist only for *developing and training*, and the other
laptop doesn't need any of them just to run the demo.

What genuinely has to move is much smaller:

| Item | Size | Why it's needed |
|---|---|---|
| The `api` and `ml` Docker images | ~1.4 GB combined | The built application |
| `ml/models/*.pkl` (the trained models) | ~46 MB | Not baked into the image; bind-mounted at runtime |
| `docker-compose.yml`, `demo.env`, `db/init/` | a few KB | Tells Docker how to start everything |

The images go through Docker Hub (like GitHub, but for containers instead of
code). The small files go however is easiest — email, USB stick, a shared
drive, or `git clone` if the repo is on GitHub.

### On this laptop (the one with everything built)

**1. Create a free Docker Hub account** at hub.docker.com if you don't have
one, then sign in from the terminal:

```bash
docker login
```

**2. Tell Docker your Hub username**, so the images build with the right name.
Create a `.env` entry (or just set it for this session):

```bash
export DOCKERHUB_USER=your-dockerhub-username
```

On Windows PowerShell: `$env:DOCKERHUB_USER = "your-dockerhub-username"`

**3. Build and push the two images that make up the system:**

```bash
docker compose build api ml
docker compose push api ml
```

This uploads roughly 400 MB–1 GB compressed, depending on your connection —
noticeably less than 2 GB because Docker compresses each layer, and layers
common to many images (the base Python or Node install) are things Docker Hub
often already has.

By default this creates **public** repositories on Docker Hub, visible to
anyone. If this needs to stay private, create the repository on hub.docker.com
first and mark it private before pushing — Docker Hub's free tier includes one
private repository.

**4. Package the small files.** Zip up just these:

```bash
zip -r shipping-kit.zip docker-compose.yml demo.env db/init ml/models -x "ml/models/.gitkeep"
```

On Windows PowerShell:

```powershell
Compress-Archive -Path docker-compose.yml, demo.env, db\init, ml\models -DestinationPath shipping-kit.zip
```

That zip should be small — under 100 MB, dominated by the 46 MB of models.
Send it to the other laptop however is convenient.

### On the other laptop

**1. Install Docker Desktop** (see step 1 of this guide).

**2. Unzip the shipping kit** into a new folder, and open a terminal there.

**3. Set the same Docker Hub username** (so it knows whose images to pull):

```bash
export DOCKERHUB_USER=your-dockerhub-username
```

**4. Copy the demo config into place:**

```bash
cp demo.env .env
```

**5. Pull the images and start the stack:**

```bash
docker compose pull api ml
docker compose up -d
```

Because this laptop has no `api/` or `ml/` source folders — only the
`docker-compose.yml` and the pulled images — Compose has no choice but to use
what it pulled. There's nothing to accidentally rebuild from.

**6. Confirm it's healthy**, then follow this guide from step 3 onward exactly
as before:

```bash
docker compose ps
curl http://localhost:3000/health
```

If the attack simulator is also wanted on the other laptop, push and pull the
`sim` image the same way (`docker compose build sim` / `push sim` /
`pull sim`), since it isn't included in the 400 MB–1 GB estimate above.

---

## 10. Shut down

Stop the services, keeping the database volume:

```bash
docker compose --profile sim down
```

Remove the database volume as well, so the next start re-creates the schema
from scratch (useful to prove reproducibility):

```bash
docker compose --profile sim down -v
```

---

## Troubleshooting

- **`ml` never becomes healthy** — `ml/models/` is empty or incomplete. See
  step 1.
- **The API blocks ordinary logins, or every attack is blocked at attempt 1** —
  `.env` is missing or `TRUST_PROXY` is not set, so the simulator's clients are
  collapsing into one source. Confirm `.env` exists (step 2) and re-run
  `docker compose up -d api`.
- **`recalibrate_threshold.py` reports rows without a score** — the traffic was
  generated with `DETECTION_TRACE` off. Confirm `.env` has `DETECTION_TRACE=1`
  and regenerate.
- **A generator refuses to start, citing a dirty window** — a previous run's
  traffic is still inside the 60-second detection window. Wait a minute, or
  `docker compose restart api`, then re-run.
- **Port already in use** — another process holds 3000, 8000, or 5432. Override
  in `.env`, e.g. `API_PORT=3001`, and use that port.
- **`docker compose pull` fails with "denied" or "not found"** — either
  `DOCKERHUB_USER` isn't set to match the account the images were pushed to, or
  the Hub repository is private and this machine isn't logged in. Run
  `docker login` and confirm `echo $DOCKERHUB_USER` matches the pushing account.
- **On the other laptop, `docker compose up` tries to build instead of using the
  pulled image** — this only happens if the `api/` or `ml/` source folders were
  copied over as well. Use only the shipping-kit files from step 9; without a
  source folder to build from, Compose has nothing to build and must use the
  pulled image.
