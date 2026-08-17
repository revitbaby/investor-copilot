"""账本 SQLite schema（ADR-0014：事务/外键/唯一约束保一致性）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings (
    id          INTEGER PRIMARY KEY,
    asset_type  TEXT NOT NULL CHECK (asset_type IN ('stock', 'fund', 'cash')),
    market      TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    quantity    REAL NOT NULL CHECK (quantity >= 0),
    currency    TEXT NOT NULL CHECK (currency IN ('CNY', 'HKD', 'USD')),
    cost_basis  REAL,
    updated_on  TEXT NOT NULL,
    UNIQUE (asset_type, market, symbol)
);

CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY,
    holding_id      INTEGER NOT NULL REFERENCES holdings (id),
    occurred_on     TEXT NOT NULL,
    delta_quantity  REAL NOT NULL,
    quantity_after  REAL NOT NULL,
    note            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS fund_xray (
    id          INTEGER PRIMARY KEY,
    fund_code   TEXT NOT NULL,
    data_as_of  TEXT NOT NULL,
    bucket      TEXT NOT NULL,
    weight      REAL NOT NULL CHECK (weight >= 0),
    UNIQUE (fund_code, data_as_of, bucket)
);

CREATE TABLE IF NOT EXISTS theme_map (
    id           INTEGER PRIMARY KEY,
    asset_type   TEXT NOT NULL CHECK (asset_type IN ('stock', 'fund')),
    market       TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    theme        TEXT NOT NULL,
    is_satellite INTEGER NOT NULL DEFAULT 0,
    UNIQUE (asset_type, market, symbol, theme)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id         INTEGER PRIMARY KEY,
    week_id    TEXT NOT NULL UNIQUE,
    as_of      TEXT NOT NULL,
    total_cny  REAL NOT NULL,
    stale      INTEGER NOT NULL DEFAULT 0,
    payload    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS last_prices (
    asset_type TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    price      REAL NOT NULL,
    currency   TEXT NOT NULL,
    quoted_on  TEXT NOT NULL,
    PRIMARY KEY (asset_type, symbol)
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
