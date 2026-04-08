CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    stripe_customer_id TEXT,
    credit_balance INTEGER NOT NULL DEFAULT 0,
    active_plan TEXT NOT NULL DEFAULT 'free',
    plan_status TEXT NOT NULL DEFAULT 'inactive',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_collections (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    format_template TEXT NOT NULL DEFAULT 'ARTIST_TITLE_PRODUCERS_MIX_VERSION',
    delimiter TEXT NOT NULL DEFAULT 'underscore',
    case_style TEXT NOT NULL DEFAULT 'keep',
    safe_cleanup BOOLEAN NOT NULL DEFAULT TRUE,
    total_size_bytes BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'uploaded',
    download_count INTEGER NOT NULL DEFAULT 0,
    preview_generated_at TIMESTAMP WITH TIME ZONE,
    downloaded_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    collection_id INTEGER REFERENCES file_collections(id) ON DELETE CASCADE,
    external_id TEXT UNIQUE NOT NULL,
    original_path TEXT NOT NULL,
    current_path TEXT NOT NULL,
    file_size BIGINT,
    extension TEXT,
    extracted_json TEXT,
    resolved_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    collection_id INTEGER REFERENCES file_collections(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    details_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payment_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_checkout_session_id TEXT UNIQUE NOT NULL,
    stripe_customer_id TEXT,
    stripe_price_id TEXT,
    plan_key TEXT NOT NULL,
    amount_cents INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'usd',
    credits INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
