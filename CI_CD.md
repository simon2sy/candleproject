# CI/CD Setup — Automated Deployment

Push to `main` → CI runs tests → **if green, the server deploys itself.**

This replaces the old manual routine:

```bash
cd /home2/nismitac/candleproject
source /home2/nismitac/virtualenv/candleproject/3.13/bin/activate
git pull origin main
```

---

## 🔴 First: revoke the leaked token

A GitHub Personal Access Token was pasted into a chat message in plaintext:

GitHub Token: YOUR_GITHUB_TOKEN

**Revoke it immediately:** <https://github.com/settings/tokens> → select the
token → **Delete**.

Treat it as public — chat logs, CI output and third-party scanners harvest
`ghp_` strings within minutes. Create a new one only if you still need it, with
the narrowest possible scope and a short expiry.

> **Important:** your server's `git pull origin main` currently authenticates with
> this same token. Revoking it will break manual deploys until you complete
> **Step 3 (server deploy key)** below. The new setup never uses a token.

---

## How the pipeline works

```
git push origin main
        │
        ▼
  ┌─────────────┐   lint (ruff)          ┌──────────────┐
  │  CI: lint   ├────────────────────────►│              │
  ├─────────────┤   tests on 3.12 + 3.13 │              │
  │  CI: test   ├────────────────────────►│  all green?  │
  ├─────────────┤   check --deploy        │              │
  │ CI: security├────────────────────────►└──────┬───────┘
  └─────────────┘   dependency audit              │ yes
                                                ▼
                                     ┌──────────────────────┐
                                     │  Deploy (SSH → cPanel)│
                                     │  pull → pip → migrate │
                                     │  → collectstatic     │
                                     │  → check → restart   │
                                     └──────────┬───────────┘
                                                ▼
                                       GET /readyz/ must pass
```

A broken commit can never reach production — deployment is gated on CI.

### Files

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | Lint, tests, Django deploy checks, dependency audit |
| `.github/workflows/deploy.yml` | SSH release to the cPanel server |
| `deploy/deploy.sh` | Release script executed on the server |
| `pyproject.toml` | Ruff + coverage configuration |

---

## Step 1 — Create a GitHub deploy key

A **deploy key** is scoped to this one repository and cannot touch your account.

```bash
# On your machine
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/candle_deploy
```

Two files are created. `candle_deploy` (private) goes to GitHub;
`candle_deploy.pub` (public) goes on the server.

## Step 2 — Add repository secrets and variables

Go to <https://github.com/simon2sy/candleproject/settings/secrets/actions>.

### Secrets (Settings → Secrets → Actions → New repository secret)

| Secret | Value |
|---|---|
| `DEPLOY_SSH_KEY` | Contents of `~/.ssh/candle_deploy` **without** the `.pub` suffix |
| `DEPLOY_KNOWN_HOSTS` | Output of `ssh-keyscan -p PORT HOST` (see below) |

### Variables (Settings → Secrets and variables → Actions → Variables tab)

| Variable | Value |
|---|---|
| `DEPLOY_HOST` | Your server hostname or IP |
| `DEPLOY_PORT` | SSH port, e.g. `2222` (cPanel often uses a non-22 port) |
| `DEPLOY_USER` | Your cPanel username |
| `DEPLOY_APP_DIR` | `/home2/nismitac/candleproject` |
| `DEPLOY_VENV_ACTIVATE` | `/home2/nismitac/virtualenv/candleproject/3.13/bin/activate` |
| `SITE_URL` | `https://nismitacraftstudio.com` |

> Paths are **variables**, not secrets — they are not sensitive, and keeping them
> out of the workflow file means one repo can target staging or production.

Generate `DEPLOY_KNOWN_HOSTS` from your machine:

```bash
ssh-keyscan -p 2222 your.server.host
```

Pinning the host key prevents a man-in-the-middle from intercepting the deploy.

## Step 3 — Authorise the server to pull from GitHub

Run this in your cPanel terminal (the one you normally deploy from):

```bash
cd /home2/nismitac/candleproject

# 1. Allow the deploy key
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "github-actions-deploy" >> ~/.ssh/allowed_signers
echo "<paste contents of candle_deploy.pub here>" >> ~/.ssh/allowed_signers
chmod 600 ~/.ssh/allowed_signers

# 2. Point origin at SSH instead of HTTPS-with-token
git remote set-url origin git@github.com:simon2sy/candleproject.git

# 3. Confirm SSH access to GitHub works from the server
ssh -T git@github.com
```

If step 3 prompts for a password, add the key to your **account SSH keys** first
(<https://github.com/settings/keys>). A repository deploy key alone cannot
authenticate a `git fetch`.

## Step 4 — Restart the cPanel app once

```bash
chmod +x /home2/nismitac/candleproject/deploy/deploy.sh
```

Then in **cPanel → Setup Python App**, click **Restart** so Passenger picks up
the new `deploy/` directory.

## Step 5 — First run

```bash
git add -A
git commit -m "ci: add GitHub Actions CI and automatic cPanel deployment"
git push origin main
```

Watch the run at <https://github.com/simon2sy/candleproject/actions>.

---

## What `deploy.sh` does on the server

Every step is fail-fast, so a failure leaves the previous release serving traffic:

1. Verifies `manage.py`, the virtualenv and `.env` all exist
2. `git fetch` → refuses if the working tree is dirty → `git reset --hard origin/main`
3. `pip install -r requirements.txt`
4. `migrate --noinput`
5. `collectstatic --noinput --clear` and prune old files
6. `check --deploy`
7. Imports the WSGI app as a smoke test (catches syntax errors before restart)
8. `touch tmp/restart.txt` → Passenger reloads
9. Polls `/healthz/` for up to 30 seconds and fails if the app never comes back

---

## Manual deploy (when you need to bypass CI)

Actions → **Deploy to Production** → **Run workflow**. It still runs the same
script, so it is safe and audited.

Or, from the cPanel terminal:

```bash
cd /home2/nismitac/candleproject
git pull origin main
source /home2/nismitac/virtualenv/candleproject/3.13/bin/activate
bash deploy/deploy.sh   # full release: migrate, collectstatic, restart
```

---

## Adding an environment (staging)

`deploy.yml` already uses a `production` GitHub Environment. To require manual
approval before any release: **Settings → Environments → production →
Deployment protection rule** → add required reviewers.

For staging, duplicate the workflow with `branches: [staging]` and point it at a
separate set of variables.

---

## Local development with the same tooling

```powershell
python -m pip install -r requirements.txt ruff
ruff check .                 # same lint gate as CI
ruff check . --fix           # auto-fix
ruff format .                # formatting (not yet applied repo-wide)
python manage.py test tests storefront
```

---

## Troubleshooting

**Deploy job fails at "Configure SSH"**
The key or known-hosts secret is wrong. Confirm with:
`ssh -T -p PORT -i ~/.ssh/candle_deploy USER@HOST`

**`Permission denied (publickey)` during deploy**
The server's SSH does not accept the key. Check cPanel SSH access is enabled
for your account.

**`Working tree is dirty`**
Something on the server modified tracked files — often a stray `db.sqlite3` or
an editor artefact. Run `git status` there and commit or discard the change.

**Migration fails**
The release aborts before Passenger restarts, so the site keeps serving the
previous release. Read the error, fix it, push to `main`.

**CI fails on `makemigrations --check`**
A model changed without a migration. Run `python manage.py makemigrations` and
commit the result.

**CI fails on lint after an auto-fix**
`ruff check . --fix` is safe and commit the result.

**Site 500s after deploy**
Check the cPanel error log and `logs/django.log`. To roll back:

```bash
cd /home2/nismitac/candleproject
git reset --hard <previous-good-sha>
source /home2/nismitac/virtualenv/candleproject/3.13/bin/activate
python manage.py migrate --noinput
python manage.py collectstatic --noinput
touch tmp/restart.txt
```

> **Take regular database backups.** `migrate` is not reversible on its own.