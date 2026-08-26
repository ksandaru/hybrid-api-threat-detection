# Quick Start — From a Brand-New Windows Laptop

This is for someone who has **never touched this project before** and needs
to get it running from scratch, with nothing installed. Follow every step in
order — none of it needs typing more than a few words at a time, and most of
the demonstration only needs a web browser.

**What you'll end up seeing:** a real website, protected by a security system
that watches every request. A normal search works. A hacking attempt gets
blocked automatically, with the reason shown on screen.

**Time needed:** about 15 minutes, most of it spent waiting for a one-time
download.

---

## What you need before starting

- A Windows 10 or 11 laptop.
- The file **`shipping-kit.zip`** (about 44 MB) — get this from whoever sent
  you this guide, the same way you'd receive any file (email, USB stick,
  shared drive).
- An internet connection, for step 1 and step 4 only. Nothing after that needs
  the internet.
- Nothing else. Not Python, not any programming tools — genuinely nothing else.

---

## Step 1 — Install Docker Desktop

Docker Desktop is the one piece of software that makes everything else in
this guide work — it's free.

1. Go to **docker.com/products/docker-desktop** and download it for Windows.
2. Run the installer. Accept the defaults. If it asks to restart your
   computer, let it.
3. After it opens, wait until you see a little whale icon in the bottom-right
   corner of your screen (near the clock), and it says **"Docker Desktop is
   running"**. This can take a minute or two the first time.

If it asks you to enable something called "WSL" during installation, click
yes/accept — that's expected and part of a normal install.

---

## Step 2 — Get the project files ready

1. Find `shipping-kit.zip` (check your Downloads folder).
2. Right-click it → **Extract All...** → choose somewhere easy to find, like
   your Desktop → click **Extract**.
3. You'll now have a folder called `shipping-kit` with a few files in it.
   Open that folder in File Explorer.

---

## Step 3 — Open a terminal inside that folder

This is a trick that avoids typing any folder paths:

1. In the File Explorer window, click once on the empty address bar at the
   top (where the folder path is shown).
2. Type `cmd` and press **Enter**.

A black terminal window opens, already "inside" the right folder. Every
command below goes into this window.

---

## Step 4 — Download and start everything

Type each of these on its own line, pressing Enter after each, and wait for
it to finish before typing the next one:

```bash
docker compose pull
```

This downloads the application — about 1.4 GB, so it can take a few minutes
depending on your internet speed. You'll see progress bars.

```bash
docker compose up -d
```

This starts everything. Takes about 20-30 seconds.

---

## Step 5 — Check it's actually running

```bash
docker compose ps
```

You should see three lines, one each for `db`, `ml`, and `api`, and each
should say **`healthy`** in the Status column. If one says `starting`, wait 10
seconds and run the same command again.

---

## Step 6 — Watch it work (just your web browser — no typing)

Open your normal web browser (Edge, Chrome, whichever) and visit these three
addresses one at a time, by typing or pasting them into the address bar:

**1. Confirm it's alive:**
```
http://localhost:3000/health
```
You should see a small block of text starting `{"status":"ok"...`.

**2. A normal, everyday search — allowed through:**
```
http://localhost:3000/api/search/vulnerable?q=laptop
```
Shows a normal search result for "laptop".

**3. A real hacking attempt — automatically blocked:**
```
http://localhost:3000/api/search/vulnerable?q=%27%20UNION%20SELECT%20username%2C%20password%20FROM%20users%20--
```
This is a classic attack that tries to steal every username and password from
the database. Instead of running it, the page shows
`"error":"request blocked by threat detection"` along with a confidence score
and the exact reasons it was flagged.

**That comparison — the same website, one request allowed and one blocked —
is the entire point of this project.**

---

## Step 7 (optional) — Prove it doesn't block real customers

The system needs to be smart enough not to block ordinary logins just because
they contain unusual-looking text. In the same black terminal window from
step 3:

```bash
curl -X POST http://localhost:3000/api/auth/register -H "Content-Type: application/json" -d "{\"username\":\"demo\",\"password\":\"demo-pass-123\"}"
```

```bash
curl -X POST http://localhost:3000/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"demo\",\"password\":\"demo-pass-123\"}"
```

The first creates an account (look for `"username":"demo"`), the second logs
in successfully (look for a long `"token":"..."` — that's proof it worked, not
gotten blocked).

---

## When you're finished

Back in the terminal window:

```bash
docker compose down
```

This stops everything cleanly. Nothing is lost — running `docker compose up -d`
again later brings it straight back.

---

## If something goes wrong

- **`docker compose ps` shows `ml` stuck on "starting" for a long time, or it
  never turns "healthy"** — give it up to a minute; it's loading a large file
  the first time. Still stuck after that? Close this terminal, reopen one the
  same way (step 3), and run `docker compose up -d` again.
- **A red error mentioning "port is already allocated"** — something else on
  this laptop is already using that address. Nothing else to install; just
  ask whoever gave you this project for help.
- **Anything else** — take a screenshot of the terminal window and send it to
  whoever gave you this kit. They have a longer troubleshooting guide
  (`DEMO_GUIDE.md`) covering less common problems in detail.
