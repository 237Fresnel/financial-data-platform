CREATE TABLE raw.transactions (
    batch_id                TEXT NOT NULL,
    source_row              INTEGER NOT NULL,
    transaction_id          TEXT,
    account_id              TEXT,
    counterparty_account_id TEXT,
    amount                  TEXT,
    currency                TEXT,
    transaction_type        TEXT,
    country                 TEXT,
    transaction_timestamp   TEXT,
    source_file             TEXT NOT NULL,
    ingested_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, source_row)
);

CREATE TABLE raw.customers (
    customer_id TEXT, country TEXT, segment TEXT, created_at TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE raw.accounts (
    account_id TEXT, customer_id TEXT, currency TEXT, status TEXT, created_at TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE raw.load_log (
    batch_id    TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    row_count   INTEGER NOT NULL,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);