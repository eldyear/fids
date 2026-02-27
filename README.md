# FIDS - Flight Information Display System

[![Django 5.1](https://img.shields.io/badge/Django-5.1-green)](https://www.djangoproject.com/)
[![Go 1.21+](https://img.shields.io/badge/Go-1.21+-cyan)](https://golang.org/)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED)](https://www.docker.com/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791)](https://www.postgresql.org/)

A professional-grade Airport Flight Information Display System (FIDS). Features a hybrid **Django + Go** architecture, automated billing, BCBP boarding pass parsing, and full containerization.

## Key Features

- **Flight Management** – Real-time tracking and synchronization of airport flight data.
- **Billing System** – Automated invoicing, service tracking, and financial reporting.
- **BCBP Processing** – High-performance parsing of Bar-Coded Boarding Passes.
- **Baggage Control** – Integrated module for tracking and handling passenger luggage.
- **Scalable REST API** – Full-featured API for 3rd party airport service integrations.
- **Admin Dashboard** – Intuitive management interface built with Django Admin.
- **Enterprise DevOps** – Fully containerized with Docker, Nginx, and Gunicorn.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────┐
│                    Nginx (Reverse Proxy)                │
└──────┬──────────────────────────────────────┬───────────┘
       ▼                                      ▼
┌──────────────────┐              ┌──────────────────────┐
│  Django Backend  │              │   Go Display System  │
│  (REST API, Web) │              │ (High-Performance)   │
└────────┬─────────┘              └──────────┬───────────┘
         └─────────────┬────────────────────┘
                       ▼
            ┌──────────────────────┐
            │     PostgreSQL 16    │
            └──────────────────────┘
```

## Tech Stack

- **Backend:** Python 3.11 (Django 5.1, DRF), Go 1.21 (Display Engine)
- **Libraries:** Pandas (Data), Pillow (Image processing), ReportLab (PDF generation)
- **Database:** PostgreSQL 16
- **Infrastructure:** Docker, Docker Compose, Nginx, Gunicorn

## Project Structure

- **app/** — Core flight management and scheduling logic
- **billing/** — Invoicing workflows and financial services
- **scanner_app/** — Boarding pass parsing (Standard & Improved logic)
- **fids_go_v2.1/** — High-concurrency Go engine for display screens
- **nginx/** — Routing, security, and reverse proxy configuration

## Quick Start (Docker)

**Setup Environment:**
```bash
git clone <your-repo-url>
cp .env.example .env
```

**Launch Infrastructure:**
```bash
docker-compose up -d --build
```

**Initialize System:**
```bash
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

The system will be live at `http://localhost`.

## API Endpoints

| Resource | Method | Description |
|----------|--------|-------------|
| `/api/flights/` | GET/POST | Manage flight schedules and real-time data |
| `/api/billing/invoices/` | GET/POST | Process service billing and payments |
| `/api/scanner/parse/` | POST | High-speed BCBP data extraction |

## 🔧 Maintenance & DevOps

- **Real-time Logs:** `docker-compose logs -f backend`
- **Database Backups:** `docker-compose exec db pg_dump -U postgres oss_db > backup.sql`
- **Ready for Production:** Includes optimized static file handling and secure Nginx routing

---

**Version:** 2.1.0

**Status:** Production Ready

Developed by eldyear — Specialized in High-Performance Infrastructure & Automation.
