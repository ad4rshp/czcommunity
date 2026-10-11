# 🛋️ ChillZone Community

<p align="center">
  <img src="static/img/chillzone_logo.svg" alt="ChillZone Logo" width="120" height="120" />
</p>

<p align="center">
  <strong>A modern, privacy-focused real-time community hub built for seamless conversation, voice hangouts, and collaboration.</strong>
</p>

<p align="center">
  <a href="#about">About</a> •
  <a href="#features">Features</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#deployment">Deployment</a> •
  <a href="#license--attribution">License</a>
</p>

---

## 📖 About ChillZone

**ChillZone** is an all-in-one community and communication platform designed from the ground up to offer a sleek, customizable, and authentic space for gamers, creators, students, and teams. Built with Django and asynchronous WebSockets, ChillZone provides real-time chat, crystal-clear voice lounges, deep role management, and an engaging social layer without bloat or tracking.

Whether you are hosting a gaming clan, building a developer hub, or hanging out with close friends, ChillZone delivers a warm, polished sunset-aesthetic interface with state-of-the-art responsiveness across mobile and desktop.

---

## ✨ Features

### 💬 Real-Time Messaging & Channels
- **Instant Messaging**: Powered by Django Channels + Daphne ASGI with sub-millisecond real-time message broadcasting.
- **Advanced Syntax Search**: Filter messages effortlessly using syntax operators like `from:@user`, `in:#channel`, `has:image`, `has:file`, and sort by newest or oldest.
- **Inbox & Notifications**: Centralized inbox drawer with separate tabs for direct mentions (`@username`) and unread channel pings with live counters.
- **Rich Media & Attachments**: File upload handling with drag-and-drop, image previews, and code snippet formatting.
- **Channel Categories & Permissions**: Organize text, announcement, and voice lounges with category hierarchy and granular permission overrides (Allow / Inherit / Deny).

### 🎙️ Voice Lounges (WebRTC)
- **Zero-Friction Audio**: Jump into voice channels directly within the browser without external desktop clients.
- **HD Voice Quality**: High-fidelity sound (64kbps+ configurable bitrate).
- **Audio Controls**: Live microphone toggle, deafen controls, voice ping indicators, and speaking ring animations.

### 🛡️ Roles & Community Administration
- **Hierarchical Roles**: Create custom roles with tailored colors, separate member list hoisting, and mention permissions.
- **Member & Role Overrides**: Fine-tune access per channel for specific roles or individual members.
- **Audit Logs**: Track moderation actions, channel creations, member role assignments, and permission changes.

### 👤 Profiles & Social Hub
- **Customizable Profiles**: Bio, custom banner, avatar uploads, and status indicators (Online, Idle, Do Not Disturb, Invisible).
- **Cute Avatar Generator**: Dynamic procedural default avatars featuring ChillZone's signature cyber-mascot eyes in 6 vibrant color palettes.
- **Friends & Direct Messages (DMs)**: Send friend requests, accept/decline, and chat in private one-on-one direct message threads.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Django 5.x
- **Asynchronous / WebSockets**: Django Channels, Daphne (ASGI), Redis Channel Layer
- **Database**: SQLite (Local Dev) / PostgreSQL (Production)
- **Frontend**: HTML5, Vanilla CSS (Warm Sunset Glassmorphic Theme), Alpine.js, Phosphor Icons
- **WebRTC**: Real-time peer audio streaming
- **Deployment**: Daphne ASGI systemd service, Nginx reverse proxy

---

## 🚀 Getting Started (Local Development)

### 1. Prerequisites
Ensure you have the following installed:
- [Python 3.10+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/)
- [Redis](https://redis.io/) *(Optional for local fallback; required for multi-worker WebSockets)*

### 2. Clone the Repository
```bash
git clone https://github.com/ad4rshp/czcommunity.git
cd czcommunity
```

### 3. Create a Virtual Environment
```bash
# On Windows (PowerShell)
python -m venv venv
.\venv\Scripts\activate

# On Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Run Database Migrations
```bash
python manage.py migrate
```

### 6. Create a Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 7. Run the Development Server
```bash
python manage.py runserver
```

Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 🌐 Production Deployment

Production configuration files are pre-configured in the [`deploy/`](deploy/) directory:

- **Daphne Service (`deploy/daphne.service`)**: Manages the ASGI server process under `systemd`.
- **Nginx Config (`deploy/nginx.conf`)**: Handles reverse proxying, static file delivery, HTTP/HTTPS redirection, and WebSocket upgrades (`Upgrade $http_upgrade`).

### Recommended Production Environment Variables
Set these in your production server `.env` or system environment:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | Strong random secret key | `your-secure-50-character-secret` |
| `DJANGO_DEBUG` | Set to `False` in production | `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated domain names | `chillzone.example.com,www.chillzone.example.com` |
| `SECURE_SSL_REDIRECT` | Enforces HTTPS | `True` |
| `USE_S3` | Set to `True` for AWS S3 file storage | `True` *(Optional)* |

---

## 👤 Author

**Adarsh Pandey** ([@ad4rshp](https://github.com/ad4rshp))  
Sole creator, architect, and developer of the ChillZone platform.

---

## 📄 License & Attribution

Copyright &copy; 2026 **Adarsh Pandey**.

This project is open for personal use, learning, and modification under the condition that **proper attribution and credit are prominently preserved** to the author (**Adarsh Pandey** - [@ad4rshp](https://github.com/ad4rshp)). Re-hosting or distributing modified versions without explicit credit to the original creator is prohibited.

<p align="center">
  Crafted with ❤️ by <strong>Adarsh Pandey</strong> for <strong>ChillZone</strong>.
</p>
