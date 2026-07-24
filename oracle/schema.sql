-- oracle/schema.sql  (the contract; meta.schema_version gates compatibility)
CREATE TABLE meta (
  schema_version   INTEGER NOT NULL,
  generated_at     TEXT    NOT NULL,
  mpc_epoch        TEXT,
  window_start     TEXT    NOT NULL,
  window_end       TEXT    NOT NULL,
  skyfield_kernel  TEXT
);

CREATE TABLE comets (
  id                  TEXT PRIMARY KEY,
  designation         TEXT NOT NULL,
  name                TEXT,
  epoch_jd            REAL,
  perihelion_q_au     REAL NOT NULL,
  eccentricity        REAL NOT NULL,
  inclination_deg     REAL NOT NULL,
  arg_perihelion_deg  REAL NOT NULL,
  node_deg            REAL NOT NULL,
  -- mag_h/mag_k hold the comet total-magnitude params g,k
  -- (m = g + 5*log10(delta) + 2.5*k*log10(r)); NOT the asteroid H,G system.
  mag_h               REAL,
  mag_k               REAL
);

CREATE TABLE comet_ephemeris (
  comet_id       TEXT NOT NULL REFERENCES comets(id),
  sample_utc     TEXT NOT NULL,
  ra_deg         REAL NOT NULL,
  dec_deg        REAL NOT NULL,
  earth_dist_au  REAL NOT NULL,
  sun_dist_au    REAL NOT NULL,
  predicted_mag  REAL,
  constellation  TEXT,
  PRIMARY KEY (comet_id, sample_utc)
);
CREATE INDEX idx_ephem_time ON comet_ephemeris(sample_utc);
