<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white" />
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Raspberry%20Pi-lightgrey?style=for-the-badge" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" />
</p>

<h1 align="center">🔔 Cobrell — Smart School Bell Scheduler</h1>

<p align="center">
  <strong>A web-based automatic school bell system powered by Django.</strong><br/>
  Schedule bells, upload custom ringtones, manage exceptions for holidays — all from a beautiful dashboard.<br/>
  Runs on <b>Desktop</b>, <b>Linux Server</b>, or <b>Raspberry Pi</b> with 3.5 mm audio jack output.
</p>

---

## ✨ Features

| Feature | Description |
|---|---|
| 📅 **Bell Scheduling** | Create schedules per day & time. Group, edit, toggle, or delete them with ease. |
| 🎵 **Custom Ringtones** | Upload MP3, WAV, OGG, FLAC, AAC, WMA, or M4A files (up to 20 MB). Preview them directly from the dashboard. |
| 🚫 **Exception Management** | Set date-specific exceptions (holidays, exams, ceremonies) to skip certain bells. |
| 📊 **Dashboard & Calendar** | Live server clock, next-bell indicator, monthly calendar view with bell counts and exception markers. |
| 🔐 **Authentication** | First-run setup wizard creates an admin account. Login with session management & "Remember Me" support. |
| 🔊 **Audio Playback** | Uses `pygame` for audio; falls back to `afplay` (macOS), `aplay`/`mpg123`/`ffplay`/`vlc` (Linux). |
| 🍓 **Raspberry Pi Ready** | Auto-configures 3.5 mm audio jack output and volume. Includes a `systemd` service file for auto-start on boot. |
| 🔧 **Dependency Auto-Check** | `checkdeps` management command verifies Python packages and system audio tools, auto-installing what's missing. |

---

## 📋 Prerequisites

- **Python 3.10+**
- **pip** (Python package manager)
- **Audio output** — speakers or headphones connected via 3.5 mm jack (for Raspberry Pi) or default audio (for desktop)

### Additional for Raspberry Pi / Linux

- `alsa-utils` — for `aplay` and `amixer`
- `libsdl2-mixer-2.0-0` and `libsdl2-2.0-0` — required by `pygame`
- Optional: `mpg123`, `ffplay`, or `vlc` as audio fallback players

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/dareekun/cobrell.git
cd cobrell
```

### 2. Create & Activate Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `django` — web framework
- `pygame` — audio playback engine
- `mutagen` — audio metadata & duration detection

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Start the Development Server

```bash
python manage.py runserver
```

Open your browser at **http://127.0.0.1:8000**. On first visit you will be guided through the **admin account setup wizard**.

### 6. Start the Bell Scheduler

In a **separate terminal** (with the virtual environment activated):

```bash
python manage.py runscheduler
```

The scheduler runs in the background, checking every second if a bell should ring and playing the assigned audio file at the scheduled time.

> **Tip:** Use `--skip-deps` to skip the automatic dependency check:
> ```bash
> python manage.py runscheduler --skip-deps
> ```

---

## 🍓 Raspberry Pi Deployment

### Install System Dependencies

```bash
sudo apt update
sudo apt install -y alsa-utils libsdl2-mixer-2.0-0 libsdl2-2.0-0
```

### Set Up as a systemd Service (Auto-Start on Boot)

```bash
# Copy the service file
sudo cp cobrell-scheduler.service /etc/systemd/system/

# Edit paths if your project is not in /home/pi/cobrell
sudo nano /etc/systemd/system/cobrell-scheduler.service

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable cobrell-scheduler
sudo systemctl start cobrell-scheduler
```

### Useful Commands

```bash
sudo systemctl status cobrell-scheduler    # Check status
sudo journalctl -u cobrell-scheduler -f    # View live logs
sudo systemctl restart cobrell-scheduler   # Restart
```

---

## 📂 Project Structure

```
cobrell/
├── manage.py                    # Django management entry point
├── requirements.txt             # Python dependencies
├── cobrell-scheduler.service    # systemd service file for Raspberry Pi
│
├── cobrell/                     # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── accounts/                    # Authentication app
│   ├── views.py                 # Login, register, logout
│   ├── middleware.py             # First-run setup redirect
│   └── templates/accounts/      # Login & register pages
│
├── dashboard/                   # Main application
│   ├── models.py                # Musik, JadwalBel, Pengecualian
│   ├── views.py                 # Dashboard, CRUD, APIs
│   ├── scheduler.py             # Bell scheduler & audio playback
│   ├── deps.py                  # Dependency checker & auto-installer
│   ├── urls.py                  # URL routing
│   ├── templates/dashboard/     # HTML templates
│   └── management/commands/
│       ├── runscheduler.py      # `python manage.py runscheduler`
│       └── checkdeps.py         # `python manage.py checkdeps`
│
├── database/
│   └── db.sqlite3               # SQLite database
│
└── media/
    └── musik/                   # Uploaded audio files
```

---

## ⚙️ Management Commands

| Command | Description |
|---|---|
| `python manage.py runserver` | Start the Django web server |
| `python manage.py runscheduler` | Start the bell scheduler (auto-checks dependencies first) |
| `python manage.py runscheduler --skip-deps` | Start scheduler without dependency check |
| `python manage.py checkdeps` | Check & auto-install missing dependencies |
| `python manage.py checkdeps --dry-run` | Check dependencies without installing |
| `python manage.py migrate` | Apply database migrations |
| `python manage.py createsuperuser` | Create an admin user manually |

---

## 🛠️ Tech Stack

- **Backend:** Django 6.0 (Python)
- **Database:** SQLite
- **Audio:** pygame / system fallback players
- **Frontend:** Django Templates, CSS
- **Deployment:** systemd on Raspberry Pi / Linux

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).

---

<p align="center">
  Made with ❤️ for Indonesian schools
</p>
