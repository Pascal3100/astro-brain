-- oracle/schema.sql  (the contract; meta.schema_version gates compatibility)
-- schema_version = 2 : base catalogue commune (all object families, one artifact)

CREATE TABLE meta (
  schema_version   INTEGER NOT NULL,   -- 2 ; a consumer refuses a version it does not know
  generated_at     TEXT    NOT NULL,   -- ISO-8601 UTC
  mpc_epoch        TEXT,               -- MPC elements epoch (comets); currently unset —
                                       --  per-comet epoch lives in comet_elements.epoch_jd
  window_start     TEXT    NOT NULL,   -- ephemeris window start (UTC)
  window_end       TEXT    NOT NULL,   -- ephemeris window end (UTC) ; ~60 rolling days
  skyfield_kernel  TEXT                -- "de421.bsp"
);

-- identity, common to EVERY catalogue object
CREATE TABLE objects (
  id           TEXT PRIMARY KEY,       -- stable id (packed MPC / "planet:mars" /
                                       --  "moon" / "sun" / "NGC1976" / "star:HIP32349")
  kind         TEXT NOT NULL,          -- comet | planet | moon | sun | dso | star
  name         TEXT,                   -- common name (nullable)
  designation  TEXT                    -- catalogue designation (nullable)
);

-- fixed objects: one position + static attributes (deep-sky AND stars)
CREATE TABLE fixed_object (
  object_id     TEXT PRIMARY KEY REFERENCES objects(id),
  ra_deg        REAL NOT NULL,         -- of-date JNow at generation
  dec_deg       REAL NOT NULL,
  apparent_mag  REAL,
  object_type   TEXT,                  -- galaxy / nebula / cluster / double-star / star / ...
  size_arcmin   REAL,                  -- apparent size (nullable, e.g. stars)
  constellation TEXT,
  messier       TEXT,                  -- "M42" if applicable (nullable)
  ngc_ic        TEXT                   -- OpenNGC primary designation: usually NGC/IC,
                                       --  occasionally M40/Mel/ESO/PGC… (opaque id, nullable)
);

-- ephemeral objects: precomputed samples (comets + planets + Moon + Sun)
CREATE TABLE ephemeris (
  object_id     TEXT NOT NULL REFERENCES objects(id),
  sample_utc    TEXT NOT NULL,         -- daily step across the window
  ra_deg        REAL NOT NULL,         -- of-date JNow
  dec_deg       REAL NOT NULL,
  earth_dist_au REAL,                  -- distance to Earth (nullable)
  sun_dist_au   REAL,                  -- distance to Sun (nullable: the Sun has none)
  apparent_mag  REAL,                  -- reliable planets/luminaries; estimate for comets
  illumination  REAL,                  -- illuminated fraction 0..1 (Moon/Venus/Mercury); NULL otherwise
  constellation TEXT,
  PRIMARY KEY (object_id, sample_utc)
);
CREATE INDEX idx_ephem_time ON ephemeris(sample_utc);

-- comet-specific extras (orbital elements)
CREATE TABLE comet_elements (
  object_id          TEXT PRIMARY KEY REFERENCES objects(id),
  epoch_jd           REAL,
  perihelion_q_au    REAL NOT NULL,
  eccentricity       REAL NOT NULL,
  inclination_deg    REAL NOT NULL,
  arg_perihelion_deg REAL NOT NULL,
  node_deg           REAL NOT NULL,
  -- mag_h/mag_k hold the comet total-magnitude params g,k
  -- (m = g + 5*log10(delta) + 2.5*k*log10(r)); NOT the asteroid H,G system.
  mag_h              REAL,
  mag_k              REAL
);
