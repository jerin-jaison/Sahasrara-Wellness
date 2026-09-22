# 🌿 Sahasrara Wellness — Hostinger VPS Deployment Guide

> **Stack:** Django 5.1 · PostgreSQL · Gunicorn · Nginx · WhiteNoise · Ubuntu (Hostinger VPS)

---

## 📋 What You'll Need Before Starting

- A **Hostinger KVM VPS** plan (minimum KVM 1 — 1 vCPU, 4 GB RAM recommended)
- Your domain `sahasrarawellness.com` already pointed to Hostinger (or you will do it in Step 1)
- SSH access (Hostinger provides this in the hPanel > VPS > SSH Access section)
- Your project code pushed to GitHub (already done ✅)
- All your `.env` values ready (SECRET_KEY, RAZORPAY keys, DB credentials, EMAIL, etc.)

---

## STEP 1 — Buy a Hostinger VPS Plan & Set Up SSH

### 1.1 Purchase VPS
1. Go to [hostinger.com](https://hostinger.com) → **VPS Hosting** → pick **KVM 1** or higher.
2. During checkout, choose **Ubuntu 22.04** as the operating system.
3. After purchase, go to **hPanel → VPS** section.

### 1.2 Get Your Server IP
1. In hPanel, click on your VPS → you'll see the **IPv4 address** (e.g., `123.45.67.89`).
2. Note this IP — you'll use it everywhere.

### 1.3 Connect via SSH (from your Windows PC)
Open **PowerShell** or **Windows Terminal**:
```bash
ssh root@123.45.67.89
```
Hostinger will have sent you the root password by email, OR you can set an SSH key in hPanel.

> **Tip:** You can also use [PuTTY](https://putty.org/) for SSH if you prefer a GUI.

---

## STEP 2 — Point Your Domain to Hostinger

### If your domain is registered at Hostinger:
1. hPanel → **Domains** → Click your domain → **DNS / Nameservers**
2. Add an **A Record**:
   - Host: `@` → Value: your VPS IP
   - Host: `www` → Value: your VPS IP

### If your domain is registered elsewhere (e.g., GoDaddy, Namecheap):
1. Log into that registrar → DNS settings
2. Change the nameservers to Hostinger's:
   - `ns1.dns-parking.com`
   - `ns2.dns-parking.com`
   
   OR just add A records pointing `@` and `www` to your VPS IP.

> ⏳ DNS changes take 15 minutes to 48 hours to propagate.

---

## STEP 3 — Initial Server Setup

Run these commands **as root** after SSH-ing in:

### 3.1 Update the system
```bash
apt update && apt upgrade -y
```

### 3.2 Create a dedicated user (never run your app as root)
```bash
adduser sahasrara
# Enter a strong password when prompted, press Enter for the rest
usermod -aG sudo sahasrara
su - sahasrara
```

From this point forward, all commands run as the `sahasrara` user.

### 3.3 Install required packages
```bash
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib nginx git curl ufw certbot python3-certbot-nginx
```

---

## STEP 4 — Set Up PostgreSQL Database

```bash
sudo -u postgres psql
```

Inside the PostgreSQL shell:
```sql
CREATE DATABASE sahasrara_db;
CREATE USER sahasrara_user WITH PASSWORD 'YourStrongDBPassword123!';
ALTER ROLE sahasrara_user SET client_encoding TO 'utf8';
ALTER ROLE sahasrara_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE sahasrara_user SET timezone TO 'Asia/Kolkata';
GRANT ALL PRIVILEGES ON DATABASE sahasrara_db TO sahasrara_user;
\q
```

> 📝 Note down: DB name = `sahasrara_db`, user = `sahasrara_user`, password = your chosen password.

---

## STEP 5 — Clone Your Project from GitHub

```bash
cd /home/sahasrara
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git sahasrara_wellness
cd sahasrara_wellness
```

Replace `YOUR_USERNAME/YOUR_REPO_NAME` with your actual GitHub repository path.

### If your repo is private:
You'll need a GitHub Personal Access Token. In GitHub go to:  
**Settings → Developer Settings → Personal Access Tokens → Tokens (classic) → Generate new token**

Then clone using:
```bash
git clone https://YOUR_TOKEN@github.com/YOUR_USERNAME/YOUR_REPO_NAME.git sahasrara_wellness
```

---

## STEP 6 — Create Python Virtual Environment & Install Dependencies

```bash
cd /home/sahasrara/sahasrara_wellness
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements/production.txt
```

---

## STEP 7 — Create the `.env` File on the Server

```bash
nano /home/sahasrara/sahasrara_wellness/.env
```

Paste the following, replacing all placeholder values:

```ini
# ── Django Core ──────────────────────────────────────────────────────────────
SECRET_KEY=your-very-long-random-secret-key-here
DJANGO_SETTINGS_MODULE=sahasrara.settings.production
DEBUG=False

# ── Allowed Hosts & Site URL ──────────────────────────────────────────────────
ALLOWED_HOSTS=sahasrarawellness.com,www.sahasrarawellness.com
SITE_URL=https://www.sahasrarawellness.com
CSRF_TRUSTED_ORIGINS=https://sahasrarawellness.com,https://www.sahasrarawellness.com

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgres://sahasrara_user:YourStrongDBPassword123!@localhost:5432/sahasrara_db

# ── Email (Resend SMTP) ───────────────────────────────────────────────────────
EMAIL_HOST=smtp.resend.com
EMAIL_PORT=587
EMAIL_HOST_USER=resend
EMAIL_HOST_PASSWORD=your-resend-api-key
DEFAULT_FROM_EMAIL=bookings@sahasrarawellness.com

# ── Razorpay ──────────────────────────────────────────────────────────────────
RAZORPAY_KEY_ID=rzp_live_XXXXXXXXXXXX
RAZORPAY_KEY_SECRET=your-razorpay-secret
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret

# ── Admin URL ─────────────────────────────────────────────────────────────────
ADMIN_URL=your-secret-admin-path/
```

Save and exit: `Ctrl+X` → `Y` → `Enter`

### Generate a secure SECRET_KEY:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Copy the output and paste it as the `SECRET_KEY` value in your `.env`.

---

## STEP 8 — Update `production.py` for Hostinger

Your current `production.py` still references Render. Update it:

```bash
nano /home/sahasrara/sahasrara_wellness/sahasrara/settings/production.py
```

Replace the entire file with:

```python
from .base import *

DEBUG = False

ALLOWED_HOSTS += ['www.sahasrarawellness.com', 'sahasrarawellness.com']
SITE_URL = 'https://www.sahasrarawellness.com'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# Nginx handles SSL at the proxy level
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Essential for Razorpay cross-domain POST callbacks preserving session
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
```

> **Key change:** Removed `sahasrara-wellness.onrender.com` from ALLOWED_HOSTS.

After editing on the server, also update the same file in your local project and commit it to GitHub.

---

## STEP 9 — Run Django Setup Commands

Make sure your virtual environment is activated:
```bash
source /home/sahasrara/sahasrara_wellness/venv/bin/activate
cd /home/sahasrara/sahasrara_wellness
```

```bash
# Set the settings module
export DJANGO_SETTINGS_MODULE=sahasrara.settings.production

# Run database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create your superuser (admin account)
python manage.py createsuperuser
```

---

## STEP 10 — Configure Gunicorn

### 10.1 Test Gunicorn works first
```bash
gunicorn --bind 0.0.0.0:8000 sahasrara.wsgi:application
```
If it starts without errors, press `Ctrl+C` to stop it.

### 10.2 Create a Gunicorn systemd service file
```bash
sudo nano /etc/systemd/system/gunicorn_sahasrara.service
```

Paste this:
```ini
[Unit]
Description=Gunicorn daemon for Sahasrara Wellness
After=network.target

[Service]
User=sahasrara
Group=www-data
WorkingDirectory=/home/sahasrara/sahasrara_wellness
EnvironmentFile=/home/sahasrara/sahasrara_wellness/.env
Environment="DJANGO_SETTINGS_MODULE=sahasrara.settings.production"
ExecStart=/home/sahasrara/sahasrara_wellness/venv/bin/gunicorn \
    --access-logfile /var/log/gunicorn/sahasrara_access.log \
    --error-logfile /var/log/gunicorn/sahasrara_error.log \
    --workers 3 \
    --bind unix:/run/gunicorn_sahasrara.sock \
    sahasrara.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 10.3 Create log directory & start service
```bash
sudo mkdir -p /var/log/gunicorn
sudo chown sahasrara:sahasrara /var/log/gunicorn

sudo systemctl daemon-reload
sudo systemctl start gunicorn_sahasrara
sudo systemctl enable gunicorn_sahasrara
sudo systemctl status gunicorn_sahasrara
```

You should see `Active: active (running)` in green. ✅

---

## STEP 11 — Configure Nginx

### 11.1 Create Nginx config for your site
```bash
sudo nano /etc/nginx/sites-available/sahasrara_wellness
```

Paste this (replace the domain):
```nginx
server {
    listen 80;
    server_name sahasrarawellness.com www.sahasrarawellness.com;

    # Static files served directly by Nginx
    location /static/ {
        alias /home/sahasrara/sahasrara_wellness/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /home/sahasrara/sahasrara_wellness/media/;
        expires 7d;
    }

    # Everything else goes to Gunicorn
    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn_sahasrara.sock;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
        client_max_body_size 20M;
    }
}
```

### 11.2 Enable the site & test config
```bash
sudo ln -s /etc/nginx/sites-available/sahasrara_wellness /etc/nginx/sites-enabled/
sudo nginx -t
```
You should see `syntax is ok` and `test is successful`.

```bash
sudo systemctl restart nginx
```

### 11.3 Set correct permissions so Nginx can access your files
```bash
sudo usermod -aG sahasrara www-data
chmod 755 /home/sahasrara
```

---

## STEP 12 — Set Up SSL Certificate (HTTPS) with Let's Encrypt

```bash
sudo certbot --nginx -d sahasrarawellness.com -d www.sahasrarawellness.com
```

Follow the prompts:
- Enter your **email address**
- Agree to terms of service → `A`
- When asked about redirecting HTTP to HTTPS → choose `2` (redirect — recommended)

Certbot will automatically update your Nginx config to use HTTPS. ✅

### Test auto-renewal:
```bash
sudo certbot renew --dry-run
```

---

## STEP 13 — Configure Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

You should see SSH, HTTP (80), and HTTPS (443) allowed.

---

## STEP 14 — Update Razorpay Webhook URL

In your **Razorpay Dashboard**:
1. Go to **Settings → Webhooks**
2. Edit your existing webhook URL from:
   - `https://sahasrara-wellness.onrender.com/payments/webhook/`
3. Change it to:
   - `https://www.sahasrarawellness.com/payments/webhook/`
4. Save changes.

---

## STEP 15 — Verify Everything is Working

Visit each of these in your browser:
- `http://sahasrarawellness.com` — should redirect to HTTPS ✅
- `https://www.sahasrarawellness.com` — home page loads ✅
- `https://www.sahasrarawellness.com/your-secret-admin-path/` — admin login ✅
- Test a booking flow end-to-end ✅
- Test email (make a booking and check if confirmation email arrives) ✅

---

## 🔄 How to Deploy Code Updates in the Future

Every time you push new code to GitHub, do this on the server:

```bash
su - sahasrara
cd /home/sahasrara/sahasrara_wellness
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=sahasrara.settings.production

git pull origin master
pip install -r requirements/production.txt
python manage.py migrate
python manage.py collectstatic --noinput

sudo systemctl restart gunicorn_sahasrara
```

---

## 🛠️ Useful Commands for Troubleshooting

| Problem | Command |
|---|---|
| View Gunicorn logs | `sudo journalctl -u gunicorn_sahasrara -n 50` |
| View Gunicorn error log | `tail -f /var/log/gunicorn/sahasrara_error.log` |
| View Nginx error log | `sudo tail -f /var/log/nginx/error.log` |
| Restart Gunicorn | `sudo systemctl restart gunicorn_sahasrara` |
| Restart Nginx | `sudo systemctl restart nginx` |
| Check Gunicorn status | `sudo systemctl status gunicorn_sahasrara` |
| Test Nginx config | `sudo nginx -t` |
| Open Django shell | `python manage.py shell` |
| Check running socket | `ls -la /run/gunicorn_sahasrara.sock` |

---

## 📦 Complete File Structure on the Server

```
/home/sahasrara/
└── sahasrara_wellness/       ← Your project root
    ├── .env                  ← Environment variables (NEVER commit this)
    ├── manage.py
    ├── venv/                 ← Python virtual environment
    ├── staticfiles/          ← Collected static files (served by Nginx)
    ├── media/                ← User-uploaded media files
    ├── apps/
    ├── sahasrara/
    └── templates/

/etc/nginx/sites-available/
└── sahasrara_wellness        ← Nginx config

/etc/systemd/system/
└── gunicorn_sahasrara.service  ← Gunicorn service

/var/log/gunicorn/
├── sahasrara_access.log
└── sahasrara_error.log
```

---

## ⚠️ Important Security Reminders

1. **Never** commit your `.env` file to GitHub (it's in `.gitignore` ✅ already).
2. Keep your `SECRET_KEY` secret and unique — rotate it if ever exposed.
3. The `ADMIN_URL` in your `.env` hides the admin panel from bots — keep it non-obvious.
4. Regularly run `sudo apt update && sudo apt upgrade -y` to keep the server patched.
5. Set up automatic security updates: `sudo apt install unattended-upgrades -y`

---

## 💡 Hostinger-Specific Tips

- **hPanel → VPS → Backups** — Enable automatic weekly backups (very important!).
- **hPanel → VPS → Snapshot** — Take a snapshot before any major changes.
- Hostinger's KVM VPS supports **root SSH access** by default — remember to switch to the `sahasrara` user for day-to-day use.
- If you ever run out of memory, you can add a **swap file**:
  ```bash
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```
