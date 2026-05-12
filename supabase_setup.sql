-- ══════════════════════════════════════════════════════════════════════════════
-- SignCollect — Supabase Setup Script
-- Run this in the Supabase SQL Editor (supabase.com → your project → SQL Editor)
-- ══════════════════════════════════════════════════════════════════════════════

-- 1. Enable UUID generation (already enabled on Supabase by default)
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ── Table: documents ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
  id           UUID  DEFAULT gen_random_uuid() PRIMARY KEY,
  title        TEXT  NOT NULL,
  file_name    TEXT  NOT NULL,
  storage_path TEXT  NOT NULL,          -- e.g. "<doc_id>/original.pdf"
  status       TEXT  NOT NULL DEFAULT 'pending',  -- pending | partial | complete
  created_at   TIMESTAMPTZ DEFAULT NOW()
);


-- ── Table: signers ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signers (
  id           UUID  DEFAULT gen_random_uuid() PRIMARY KEY,
  document_id  UUID  NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  name         TEXT  NOT NULL,
  email        TEXT  NOT NULL DEFAULT '',
  role         TEXT  NOT NULL DEFAULT '',
  order_index  INT   NOT NULL DEFAULT 0,
  status       TEXT  NOT NULL DEFAULT 'pending',   -- pending | signed
  signed_at    TIMESTAMPTZ,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);


-- ── Table: signatures ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signatures (
  id              UUID  DEFAULT gen_random_uuid() PRIMARY KEY,
  document_id     UUID  NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  signer_id       UUID  NOT NULL REFERENCES signers(id)   ON DELETE CASCADE,
  signature_image TEXT  NOT NULL,           -- base64-encoded PNG of drawn signature
  page_number     INT   NOT NULL DEFAULT 1,
  x_position      FLOAT NOT NULL DEFAULT 0.7,   -- fraction of page width (0–1)
  y_position      FLOAT NOT NULL DEFAULT 0.05,  -- fraction of page height (0–1)
  width_percent   FLOAT NOT NULL DEFAULT 0.25,  -- sig width as fraction of page width
  signer_name     TEXT,
  signer_role     TEXT,
  signed_at       TIMESTAMPTZ DEFAULT NOW(),
  created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_signers_document   ON signers(document_id);
CREATE INDEX IF NOT EXISTS idx_signatures_document ON signatures(document_id);
CREATE INDEX IF NOT EXISTS idx_signatures_signer   ON signatures(signer_id);


-- ── Row Level Security ────────────────────────────────────────────────────────
-- For MVP: allow all reads and writes via the anon key.
-- In production: restrict writes to authenticated users / service role.

ALTER TABLE documents  ENABLE ROW LEVEL SECURITY;
ALTER TABLE signers    ENABLE ROW LEVEL SECURITY;
ALTER TABLE signatures ENABLE ROW LEVEL SECURITY;

-- Allow anonymous read + write (MVP — tighten in production)
CREATE POLICY "anon_all_documents"  ON documents  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_signers"    ON signers    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_signatures" ON signatures FOR ALL USING (true) WITH CHECK (true);


-- ── Storage bucket ────────────────────────────────────────────────────────────
-- Run this in the Storage section of the Supabase dashboard, OR use the SQL below.
-- Dashboard path: Storage → New Bucket → name "pdf-documents" → Public: OFF

INSERT INTO storage.buckets (id, name, public)
VALUES ('pdf-documents', 'pdf-documents', false)
ON CONFLICT (id) DO NOTHING;

-- Allow anon to read and upload (MVP)
CREATE POLICY "anon_upload_pdfs"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'pdf-documents');

CREATE POLICY "anon_read_pdfs"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'pdf-documents');

CREATE POLICY "anon_update_pdfs"
  ON storage.objects FOR UPDATE
  USING (bucket_id = 'pdf-documents');
