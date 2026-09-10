-- Schema for the request log.
--
-- api/db/pool.js wrote to this table well before anything created it, back
-- when the stack had no database. The write path fails soft, so its
-- absence degraded analysis rather than detection.
--
-- Nothing on the request path reads from this table. It exists so the
-- evaluation can reconstruct what the detector saw and decided.

CREATE TABLE IF NOT EXISTS request_log (
    id          BIGSERIAL PRIMARY KEY,
    method      TEXT        NOT NULL,
    path        TEXT        NOT NULL,
    ip          TEXT,
    features    JSONB,
    decision    TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The evaluation queries this by time window, by decision, and by source
-- when reconstructing an attack sequence.
CREATE INDEX IF NOT EXISTS request_log_created_at_idx ON request_log (created_at);
CREATE INDEX IF NOT EXISTS request_log_decision_idx   ON request_log (decision);
CREATE INDEX IF NOT EXISTS request_log_ip_idx         ON request_log (ip);

-- Individual features are queried directly when analysing which signal drove a
-- decision, so the JSONB column is indexed for containment lookups.
CREATE INDEX IF NOT EXISTS request_log_features_idx   ON request_log USING GIN (features);
