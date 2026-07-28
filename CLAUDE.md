# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Running
- **Start application with Docker**: `docker-compose up --build`
- **Run backend locally** (requires dependencies installed): `uvicorn backend.app.main:app --reload`
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Frontend Build
- **Build Tailwind CSS**: `npx tailwindcss -i frontend/static/css/tailwind-input.css -o frontend/static/css/tailwind.min.css --minify`
- **Watch mode** (during development): `npx tailwindcss -i frontend/static/css/tailwind-input.css -o frontend/static/css/tailwind.min.css --watch`
- **Config**: `tailwind.config.js` (tokens mirror CSS custom properties in `base.html`)
- **Rebuild required** when adding new Tailwind utility classes not already in use

### Backend Development
- **Dependencies**: Install via `pip install -r requirements.txt`
- **Tests**: (Run tests with `pytest tests/ --ignore=tests/frontend` (169 tests).

### Deployment
- **Platform**: Coolify (self-hosted) at `coolify.eudaven.com`
- **Production URL**: served via Coolify-managed domain
- **Database**: Postgres auto-created on container start (`docker/ensure_db.py`); verified by `docker/verify_db.sh`

## Project Architecture

The project is a full-stack web application for bulk file renaming, containerized using Docker.

### High-Level Structure
- **Backend**: FastAPI (Python)
    - `backend/app/main.py`: Application entry point, setup for templates and static files.
    	- `backend/app/routes/`: Contains API routes and web endpoints (e.g., `auth.py`).
    	- `backend/app/database/`: Database models and session management.
    	- `backend/app/core/`: Core configuration and settings.
- **Frontend**: HTMX, Tailwind CSS, and Jinja2
    - `frontend/templates/`: Jinja2 HTML templates.
    - `frontend/static/`: CSS and other static assets.
- **Infrastructure**:
    - `docker/`: Docker configuration files.
    - `docker-compose.yml`: Orchestrates the backend, frontend, and PostgreSQL database.
    - `PostgreSQL`: Primary database for storing renaming tasks/history.
