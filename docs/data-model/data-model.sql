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
    -- Canonical EverQuest item ID. This is stable across EQ item databases
    -- and must be supplied by importers/enrichers, not generated locally.
    item_id INTEGER PRIMARY KEY,

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
    hp_regen INTEGER,
    mana_regen INTEGER,
    endurance_regen INTEGER,

    -- Lucy RAW base attribute fields.
    astr INTEGER,
    asta INTEGER,
    aagi INTEGER,
    adex INTEGER,
    awis INTEGER,
    aint INTEGER,
    acha INTEGER,

    -- Lucy RAW heroic attribute fields.
    heroic_str INTEGER,
    heroic_sta INTEGER,
    heroic_agi INTEGER,
    heroic_dex INTEGER,
    heroic_wis INTEGER,
    heroic_int INTEGER,
    heroic_cha INTEGER,

    sv_magic INTEGER,
    sv_fire INTEGER,
    sv_cold INTEGER,
    sv_poison INTEGER,
    sv_disease INTEGER,

    damage INTEGER,
    delay INTEGER,
    ratio REAL,

    haste INTEGER,

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

-- Loot/source information for known items.
-- data_source is where the information came from: raidloot, eqresource, lucy,
-- allakhazam, manual, etc.
-- content_type is the in-game content category: raid, group, quest, crafted,
-- vendor, world_drop, unknown, etc.
CREATE TABLE IF NOT EXISTS item_sources (
    item_id INTEGER NOT NULL,
    data_source TEXT NOT NULL,
    source_url TEXT,
    external_item_id TEXT,

    content_type TEXT,
    zone TEXT,
    source_area TEXT,
    npc_name TEXT,

    last_checked_at TEXT,
    confidence TEXT,

    PRIMARY KEY (item_id, data_source, source_url),
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_item_sources_zone
    ON item_sources(zone);

CREATE INDEX IF NOT EXISTS idx_item_sources_npc_name
    ON item_sources(npc_name);

CREATE INDEX IF NOT EXISTS idx_item_sources_content_type
    ON item_sources(content_type);

-- Spell/effect definitions referenced by item click/proc/worn/focus effects.
-- Lucy/Allakhazam RAW exposes item spell links as spellid0..spellidN with
-- effecttype0..effecttypeN. The spell itself has id, attrib/base/max/calc slots.
-- Item effect variants and player-cast spells keep their distinct spell IDs.
CREATE TABLE IF NOT EXISTS spells (
    spell_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,

    spell_type TEXT,
    target_type TEXT,
    skill TEXT,
    resist_type TEXT,

    mana_cost INTEGER,
    endurance_cost INTEGER,
    cast_time_ms INTEGER,
    recast_time_ms INTEGER,
    recovery_time_ms INTEGER,
    duration_ticks INTEGER,
    duration_formula INTEGER,
    range_value REAL,
    aoe_range_value REAL,

    source_server TEXT NOT NULL DEFAULT 'Live',
    source_primary TEXT,
    raw_payload TEXT,
    parser_version TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    last_imported_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_spells_normalized_name
    ON spells(normalized_name);

CREATE TABLE IF NOT EXISTS spell_effect_slots (
    spell_id INTEGER NOT NULL,
    slot_index INTEGER NOT NULL,

    effect_attribute_id INTEGER,
    base_value INTEGER,
    max_value INTEGER,
    calc_id INTEGER,
    description TEXT,

    PRIMARY KEY (spell_id, slot_index),
    FOREIGN KEY (spell_id) REFERENCES spells(spell_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS item_effects (
    item_id INTEGER NOT NULL,
    effect_slot INTEGER NOT NULL,

    -- spell_id is the exact Lucy/EQ spell referenced by spellidN.
    -- trigger_type is inferred from effecttypeN/detail text when known:
    -- click, proc, worn, focus, any_slot_can_equip, unknown.
    spell_id INTEGER NOT NULL,
    trigger_type TEXT,
    effect_type_raw INTEGER,

    cast_time_ms INTEGER,
    required_level INTEGER,
    effective_level INTEGER,
    proc_rate INTEGER,
    charges INTEGER,
    description TEXT,

    PRIMARY KEY (item_id, effect_slot),
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE,
    FOREIGN KEY (spell_id) REFERENCES spells(spell_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_item_effects_spell_id
    ON item_effects(spell_id);

CREATE INDEX IF NOT EXISTS idx_item_effects_trigger_type
    ON item_effects(trigger_type);

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
    price_amount REAL,
    price_currency TEXT,
    price_pp INTEGER,
    krono_price_pp_used INTEGER,

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

-- Manual market price overrides are intentionally first-class because rare
-- high-value items often have sparse or misleading market samples.
-- price_currency is usually 'pp' or 'krono'. Krono values are converted to PP
-- at scoring time using krono_prices.
CREATE TABLE IF NOT EXISTS market_prices_override (
    item_id INTEGER NOT NULL,
    server TEXT NOT NULL,

    price_amount REAL NOT NULL,
    price_currency TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
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
    estimated_price_amount REAL,
    estimated_price_currency TEXT,
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
    hp_regen INTEGER,
    mana_regen INTEGER,
    endurance_regen INTEGER,

    astr INTEGER,
    asta INTEGER,
    aagi INTEGER,
    adex INTEGER,
    awis INTEGER,
    aint INTEGER,
    acha INTEGER,

    heroic_str INTEGER,
    heroic_sta INTEGER,
    heroic_agi INTEGER,
    heroic_dex INTEGER,
    heroic_wis INTEGER,
    heroic_int INTEGER,
    heroic_cha INTEGER,

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

-- Cursor state for incremental local log imports. The offset is Python's text
-- stream cookie, not necessarily a raw byte count, but it is safe to pass back
-- to seek() for the same file/encoding.
CREATE TABLE IF NOT EXISTS log_import_state (
    log_path TEXT NOT NULL,
    server TEXT NOT NULL,
    file_size INTEGER,
    file_mtime REAL,
    last_position INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (log_path, server)
);

COMMIT;
