-- EQ Market Scanner / Gear Finder
-- SQLite data model
-- Target: local personal tool for EverQuest market scanning and gear upgrades.

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- -----------------------------------------------------------------------------
-- Schema metadata / migrations
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Initial EQ Market Scanner schema');

-- -----------------------------------------------------------------------------
-- Items
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,

    external_item_id TEXT,
    name TEXT NOT NULL UNIQUE,
    normalized_name TEXT NOT NULL UNIQUE,

    item_type TEXT,
    slot TEXT,
    classes TEXT,
    races TEXT,

    ac INTEGER,
    hp INTEGER,
    mana INTEGER,
    endurance INTEGER,

    str INTEGER,
    sta INTEGER,
    agi INTEGER,
    dex INTEGER,
    wis INTEGER,
    int_stat INTEGER,
    cha INTEGER,

    sv_magic INTEGER,
    sv_fire INTEGER,
    sv_cold INTEGER,
    sv_poison INTEGER,
    sv_disease INTEGER,

    damage INTEGER,
    delay INTEGER,
    ratio REAL,

    haste INTEGER,
    click_effect TEXT,
    proc_effect TEXT,
    focus_effect TEXT,

    required_level INTEGER,
    recommended_level INTEGER,

    icon_id INTEGER,
    flags TEXT,

    source_primary TEXT,
    raw_payload TEXT,
    parser_version TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    last_imported_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_items_normalized_name
    ON items(normalized_name);

CREATE INDEX IF NOT EXISTS idx_items_slot
    ON items(slot);

CREATE INDEX IF NOT EXISTS idx_items_source_primary
    ON items(source_primary);

-- Sources/drops for known items.
CREATE TABLE IF NOT EXISTS item_sources (
    item_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    external_item_id TEXT,
    zone TEXT,
    npc_name TEXT,
    raid_group TEXT,
    last_checked_at TEXT,
    confidence TEXT,

    PRIMARY KEY (item_id, source_name, source_url),
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_item_sources_zone
    ON item_sources(zone);

CREATE INDEX IF NOT EXISTS idx_item_sources_npc_name
    ON item_sources(npc_name);

-- Items seen in logs but not resolved yet.
CREATE TABLE IF NOT EXISTS pending_items (
    normalized_name TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    seen_count INTEGER NOT NULL DEFAULT 1,
    last_raw_line TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_pending_items_status
    ON pending_items(status);

-- -----------------------------------------------------------------------------
-- Market listings and price intelligence
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS market_listings (
    listing_id INTEGER PRIMARY KEY AUTOINCREMENT,

    server TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    seller TEXT,

    item_name TEXT NOT NULL,
    normalized_item_name TEXT,
    item_id INTEGER,

    price_raw TEXT,
    price_pp INTEGER,
    price_krono REAL,

    raw_line TEXT,
    source TEXT NOT NULL,
    confidence TEXT,

    seen_hash TEXT UNIQUE,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    seen_count INTEGER NOT NULL DEFAULT 1,

    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_market_listings_server_timestamp
    ON market_listings(server, timestamp);

CREATE INDEX IF NOT EXISTS idx_market_listings_item_id
    ON market_listings(item_id);

CREATE INDEX IF NOT EXISTS idx_market_listings_normalized_item_name
    ON market_listings(normalized_item_name);

CREATE INDEX IF NOT EXISTS idx_market_listings_seller
    ON market_listings(seller);

CREATE TABLE IF NOT EXISTS market_prices (
    item_id INTEGER NOT NULL,
    server TEXT NOT NULL,

    median_pp INTEGER,
    p25_pp INTEGER,
    p75_pp INTEGER,
    avg_pp INTEGER,
    min_pp INTEGER,
    max_pp INTEGER,
    sample_size INTEGER,

    confidence TEXT,
    last_refresh_at TEXT,
    source TEXT,
    raw_payload TEXT,

    PRIMARY KEY (item_id, server),
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_market_prices_server
    ON market_prices(server);

-- Manual overrides are intentionally first-class because rare high-value items
-- often have sparse or misleading market samples.
CREATE TABLE IF NOT EXISTS manual_market_prices (
    item_id INTEGER NOT NULL,
    server TEXT NOT NULL,

    value_pp INTEGER,
    value_krono REAL,
    confidence TEXT NOT NULL DEFAULT 'manual',
    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (item_id, server),
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

-- Current Krono value cache per server.
CREATE TABLE IF NOT EXISTS krono_prices (
    server TEXT PRIMARY KEY,
    price_pp INTEGER NOT NULL,
    source TEXT NOT NULL,
    confidence TEXT,
    last_refresh_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Watchlist for critical items, independent from market_prices.
CREATE TABLE IF NOT EXISTS watchlist_items (
    watchlist_id INTEGER PRIMARY KEY AUTOINCREMENT,

    server TEXT NOT NULL,
    item_id INTEGER,
    item_name TEXT NOT NULL,
    normalized_item_name TEXT NOT NULL,

    alert_below_pp INTEGER,
    estimated_value_pp INTEGER,
    estimated_value_krono REAL,
    min_deal_score REAL,

    enabled INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,

    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_items_server_name
    ON watchlist_items(server, normalized_item_name);

CREATE INDEX IF NOT EXISTS idx_watchlist_items_enabled
    ON watchlist_items(enabled);

-- -----------------------------------------------------------------------------
-- Characters and gear finder
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS characters (
    character_name TEXT PRIMARY KEY,
    character_class TEXT NOT NULL,
    level INTEGER,
    server TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

-- slot_index handles duplicate slots: WRIST, FINGER, EAR, etc.
CREATE TABLE IF NOT EXISTS character_equipment (
    character_name TEXT NOT NULL,
    slot TEXT NOT NULL,
    slot_index INTEGER NOT NULL DEFAULT 1,

    item_id INTEGER,
    item_name TEXT,

    ac INTEGER,
    hp INTEGER,
    mana INTEGER,
    endurance INTEGER,
    notes TEXT,

    PRIMARY KEY (character_name, slot, slot_index),
    FOREIGN KEY (character_name) REFERENCES characters(character_name) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_character_equipment_item_id
    ON character_equipment(item_id);

CREATE TABLE IF NOT EXISTS scoring_profiles (
    profile_name TEXT PRIMARY KEY,
    character_name TEXT,
    profile_type TEXT NOT NULL,
    max_price_pp INTEGER,
    config_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,

    FOREIGN KEY (character_name) REFERENCES characters(character_name) ON DELETE SET NULL
);

-- Optional cached upgrade/deal evaluations for listings.
CREATE TABLE IF NOT EXISTS listing_scores (
    listing_id INTEGER NOT NULL,
    profile_name TEXT,

    deal_score REAL,
    upgrade_score REAL,
    alert_level TEXT,
    reason TEXT,

    evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (listing_id, profile_name),
    FOREIGN KEY (listing_id) REFERENCES market_listings(listing_id) ON DELETE CASCADE,
    FOREIGN KEY (profile_name) REFERENCES scoring_profiles(profile_name) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_listing_scores_alert_level
    ON listing_scores(alert_level);

-- -----------------------------------------------------------------------------
-- Alerts
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS alerts_sent (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,

    listing_id INTEGER,
    item_id INTEGER,
    server TEXT NOT NULL,

    alert_level TEXT NOT NULL,
    channel TEXT NOT NULL,
    message TEXT,
    status TEXT NOT NULL DEFAULT 'sent',
    error TEXT,

    sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (listing_id) REFERENCES market_listings(listing_id) ON DELETE SET NULL,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_sent_listing_id
    ON alerts_sent(listing_id);

CREATE INDEX IF NOT EXISTS idx_alerts_sent_server_sent_at
    ON alerts_sent(server, sent_at);

-- -----------------------------------------------------------------------------
-- Import runs / audit trail
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS import_runs (
    import_run_id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_name TEXT NOT NULL,
    source_url TEXT,
    zone TEXT,
    status TEXT NOT NULL,

    items_seen INTEGER NOT NULL DEFAULT 0,
    items_inserted INTEGER NOT NULL DEFAULT 0,
    items_updated INTEGER NOT NULL DEFAULT 0,
    error TEXT,

    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_import_runs_source_name
    ON import_runs(source_name);

COMMIT;
