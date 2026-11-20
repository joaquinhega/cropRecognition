CREATE SCHEMA IF NOT EXISTS platform;

CREATE TABLE IF NOT EXISTS platform.parcels (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    geom geometry(Polygon, 4326) NOT NULL,
    area_ha double precision NOT NULL,
    below_minimum boolean NOT NULL,
    origin text NOT NULL CHECK (origin IN ('drawn', 'file')),
    source_file text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS parcels_geom_idx ON platform.parcels USING gist (geom);
