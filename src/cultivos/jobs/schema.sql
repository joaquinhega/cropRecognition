CREATE TABLE IF NOT EXISTS platform.jobs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind text NOT NULL,
    parcel_id bigint REFERENCES platform.parcels (id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed')),
    step text,
    progress_done integer NOT NULL DEFAULT 0,
    progress_total integer NOT NULL DEFAULT 0,
    attempts integer NOT NULL DEFAULT 0,
    result jsonb,
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    heartbeat_at timestamptz,
    finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS jobs_queue_idx ON platform.jobs (status, id);
CREATE INDEX IF NOT EXISTS jobs_parcel_idx ON platform.jobs (parcel_id, id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_one_active_per_parcel
    ON platform.jobs (kind, parcel_id) WHERE status IN ('queued', 'running');
