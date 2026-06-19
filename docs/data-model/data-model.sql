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

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (2, 'Allow duplicate item display names; item_id is canonical');

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (3, 'Add market listing review/discard status');

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (4, 'Add persistent market listing discard rules');

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (5, 'Add per-server item interest preferences');

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (6, 'Add character inventory dump imports and current inventory state');

-- -----------------------------------------------------------------------------
-- Items
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS items (
    -- Canonical EverQuest item ID. This is stable across EQ item databases
    -- and must be supplied by importers/enrichers, not generated locally.
    item_id INTEGER PRIMARY KEY,

    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,

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

-- Manual or automated listing review state. The raw market_listings row is kept
-- immutable for audit/re-import purposes; consumers can hide discarded/suspect
-- rows via this overlay and restore them by setting status back to active.
CREATE TABLE IF NOT EXISTS market_listing_reviews (
    listing_id INTEGER PRIMARY KEY,

    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'discarded', 'suspect')),
    reason_code TEXT,
    note TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (listing_id) REFERENCES market_listings(listing_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_market_listing_reviews_status
    ON market_listing_reviews(status);

CREATE INDEX IF NOT EXISTS idx_market_listing_reviews_reason
    ON market_listing_reviews(reason_code);

-- Persistent discard rules for repeated noisy listings. Rules match the review
-- overlay by server + seller + item_id + seen price. They never delete raw
-- market_listings rows; they only create/update market_listing_reviews rows.
CREATE TABLE IF NOT EXISTS market_listing_discard_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,

    enabled INTEGER NOT NULL DEFAULT 1,
    server TEXT NOT NULL,
    seller TEXT,
    item_id INTEGER NOT NULL,

    price_currency TEXT,
    price_amount REAL,
    price_pp INTEGER,

    reason_code TEXT,
    note TEXT,
    source_listing_id INTEGER,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    disabled_at TEXT,

    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE,
    FOREIGN KEY (source_listing_id) REFERENCES market_listings(listing_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_market_listing_discard_rules_enabled
    ON market_listing_discard_rules(enabled, server, seller, item_id, price_currency, price_amount, price_pp);

CREATE INDEX IF NOT EXISTS idx_market_listing_discard_rules_source_listing
    ON market_listing_discard_rules(source_listing_id);

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

-- Per-server item interest preferences. These are user intent signals, not
-- listing reviews: wanted items can be highlighted, ignored items are hidden
-- from tracking queues by default while raw listings remain stored.
CREATE TABLE IF NOT EXISTS item_preferences (
    preference_id INTEGER PRIMARY KEY AUTOINCREMENT,

    server TEXT NOT NULL,
    preference_key_kind TEXT NOT NULL CHECK (preference_key_kind IN ('item_id', 'name')),
    preference_key TEXT NOT NULL,

    item_id INTEGER,
    item_name TEXT NOT NULL,
    normalized_item_name TEXT NOT NULL,

    status TEXT NOT NULL CHECK (status IN ('wanted', 'ignored')),
    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (server, preference_key_kind, preference_key),
    CHECK (
        (preference_key_kind = 'item_id' AND item_id IS NOT NULL)
        OR preference_key_kind = 'name'
    ),
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_item_preferences_server_status
    ON item_preferences(server, status);

CREATE INDEX IF NOT EXISTS idx_item_preferences_item_id
    ON item_preferences(item_id);

CREATE INDEX IF NOT EXISTS idx_item_preferences_name
    ON item_preferences(server, normalized_item_name);

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

CREATE TABLE IF NOT EXISTS inventory_imports (
    inventory_import_id INTEGER PRIMARY KEY AUTOINCREMENT,

    character_name TEXT NOT NULL,
    server TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    source_size_bytes INTEGER,
    parser_version TEXT NOT NULL,

    rows_seen INTEGER NOT NULL DEFAULT 0,
    rows_imported INTEGER NOT NULL DEFAULT 0,
    equipment_items_imported INTEGER NOT NULL DEFAULT 0,
    inventory_items_imported INTEGER NOT NULL DEFAULT 0,
    starter_items_seen INTEGER NOT NULL DEFAULT 0,
    empty_rows_skipped INTEGER NOT NULL DEFAULT 0,

    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed', 'failed')),
    error TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (character_name) REFERENCES characters(character_name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_inventory_imports_character_imported
    ON inventory_imports(character_name, imported_at);

CREATE INDEX IF NOT EXISTS idx_inventory_imports_server_character
    ON inventory_imports(server, character_name);

CREATE INDEX IF NOT EXISTS idx_inventory_imports_source_hash
    ON inventory_imports(source_hash);

-- slot_index handles duplicate slots: WRIST, FINGER, EAR, etc.
CREATE TABLE IF NOT EXISTS character_equipment (
    character_name TEXT NOT NULL,
    slot TEXT NOT NULL,
    slot_index INTEGER NOT NULL DEFAULT 1,

    item_id INTEGER,
    item_name TEXT,
    raw_item_name TEXT,
    normalized_item_name TEXT,

    inventory_import_id INTEGER,
    server TEXT,
    raw_location TEXT,
    quantity INTEGER NOT NULL DEFAULT 1,
    slots TEXT,
    is_starter_item INTEGER NOT NULL DEFAULT 0,
    is_augment INTEGER NOT NULL DEFAULT 0,
    augment_parent_location TEXT,

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
    FOREIGN KEY (inventory_import_id) REFERENCES inventory_imports(inventory_import_id) ON DELETE SET NULL,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_character_equipment_item_id
    ON character_equipment(item_id);

CREATE INDEX IF NOT EXISTS idx_character_equipment_import_id
    ON character_equipment(inventory_import_id);

CREATE TABLE IF NOT EXISTS character_inventory_items (
    inventory_item_id INTEGER PRIMARY KEY AUTOINCREMENT,

    character_name TEXT NOT NULL,
    server TEXT NOT NULL,
    inventory_import_id INTEGER NOT NULL,

    area TEXT NOT NULL CHECK (area IN ('carried', 'bank', 'shared_bank', 'equipped')),
    raw_location TEXT NOT NULL,
    parent_location TEXT,
    location_index INTEGER,
    location_slot_index INTEGER,

    item_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    raw_item_name TEXT NOT NULL,
    normalized_item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    slots TEXT,

    is_container INTEGER NOT NULL DEFAULT 0,
    is_starter_item INTEGER NOT NULL DEFAULT 0,
    is_augment INTEGER NOT NULL DEFAULT 0,
    augment_parent_location TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (character_name) REFERENCES characters(character_name) ON DELETE CASCADE,
    FOREIGN KEY (inventory_import_id) REFERENCES inventory_imports(inventory_import_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_character_inventory_items_character_area
    ON character_inventory_items(character_name, area);

CREATE INDEX IF NOT EXISTS idx_character_inventory_items_server_character
    ON character_inventory_items(server, character_name);

CREATE INDEX IF NOT EXISTS idx_character_inventory_items_item_id
    ON character_inventory_items(item_id);

CREATE INDEX IF NOT EXISTS idx_character_inventory_items_import_id
    ON character_inventory_items(inventory_import_id);

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
-- Local app settings
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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

-- Parser/interface diagnostics for auction log lines that could not become a
-- fully usable market listing. Repeated sightings upsert by raw line + reason
-- to keep the interface actionable without unbounded duplicate rows.
CREATE TABLE IF NOT EXISTS log_parse_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    server TEXT NOT NULL,
    log_path TEXT,

    timestamp TEXT,
    timestamp_raw TEXT,
    seller TEXT,

    raw_line TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    reason TEXT NOT NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    seen_count INTEGER NOT NULL DEFAULT 1,

    UNIQUE(server, log_path, raw_line, reason_code)
);

CREATE INDEX IF NOT EXISTS idx_log_parse_issues_server_seen
    ON log_parse_issues(server, last_seen_at);

CREATE INDEX IF NOT EXISTS idx_log_parse_issues_reason
    ON log_parse_issues(reason_code);

COMMIT;
