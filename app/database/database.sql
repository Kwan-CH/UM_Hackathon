CREATE SCHEMA um_hackathon;

SET search_path TO um_hackathon;

CREATE TABLE ngos (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT,
  contact_person TEXT,
  phone TEXT,
  email TEXT,
  address TEXT,
  latitude NUMERIC(9,6),
  longitude NUMERIC(9,6),
  distance_km NUMERIC(10,2),
  capacity_daily INTEGER,
  capacity_current INTEGER,
  operating_hours TEXT,
  food_preferences TEXT,
  special_requirements TEXT
);

CREATE TABLE notifications (
  request_id UUID NOT NULL,
  session_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  restaurant_name TEXT,
  contact_number TEXT,
  food_items JSONB NOT NULL DEFAULT '[]'::jsonb,
  pickup_time TIMESTAMPTZ,
  expiry_time TIMESTAMPTZ,
  location TEXT,
  ngo_id TEXT NOT NULL REFERENCES ngos(id) ON UPDATE CASCADE ON DELETE RESTRICT,
  ngo_name TEXT,
  distance_km NUMERIC(10,2),
  ngo_status TEXT NOT NULL DEFAULT 'pending' CHECK (ngo_status IN ('pending', 'accept', 'reject')),
  accepted_ngo_id TEXT REFERENCES ngos(id) ON UPDATE CASCADE ON DELETE SET NULL,
  PRIMARY KEY (request_id, ngo_id)
);