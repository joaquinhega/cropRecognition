CREATE TABLE IF NOT EXISTS platform.parcel_index_months (
    parcel_id bigint NOT NULL REFERENCES platform.parcels (id) ON DELETE CASCADE,
    month date NOT NULL,
    campaign text NOT NULL,
    status text NOT NULL CHECK (status IN ('ok', 'cloudy', 'no_scene', 'no_pixels', 'error')),
    scene_id text,
    scene_collection text,
    scene_datetime timestamptz,
    scene_cloud_cover double precision,
    valid_share double precision,
    valid_pixels integer,
    parcel_pixels integer,
    candidates integer NOT NULL,
    indices jsonb,
    complete boolean NOT NULL,
    processed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (parcel_id, month)
);

CREATE TABLE IF NOT EXISTS platform.parcel_climate_months (
    parcel_id bigint NOT NULL REFERENCES platform.parcels (id) ON DELETE CASCADE,
    month date NOT NULL,
    campaign text NOT NULL,
    days integer NOT NULL,
    valid_days integer NOT NULL,
    weather jsonb NOT NULL,
    point geometry(Point, 4326) NOT NULL,
    item_id text NOT NULL,
    processed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (parcel_id, month)
);
