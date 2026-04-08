# PxNN it - Authenticated Bulk File Renaming Application

## Overview
PxNN it is a modern, web-based bulk file renaming application using FastAPI, PostgreSQL, HTMX, and Jinja2.
The app now supports:

- User registration and sign-in
- Per-user dashboards with isolated batch, export, activity, and payment history
- Credit-based Stripe checkout for paid exports

## Setup and Running

1.  **Prerequisites**:
    *   Docker and Docker Compose installed.

2.  **Start the Application**:
    ```bash
    docker-compose up --build
    ```

3.  **Access the App**:
    *   Open [http://localhost:8000](http://localhost:8000) in your browser.

4.  **API Documentation**:
    *   [http://localhost:8000/docs](http://localhost:8000/docs)

## Environment

The app can run with Docker defaults, or locally with a `.env` file. Stripe checkout is optional until you want to enable billing.

- `DATABASE_URL`
- `JWT_SECRET`
- `APP_URL`
- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_SINGLE_EXPORT_PRICE_ID`
- `STRIPE_CREATOR_PACK_PRICE_ID`
- `STRIPE_LABEL_PACK_PRICE_ID`

## Architecture
*   **Backend**: FastAPI (Python)
*   **Frontend**: HTMX, Tailwind CSS, Jinja2
*   **Database**: PostgreSQL
*   **Orchestration**: Docker Compose
