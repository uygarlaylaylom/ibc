-- Table: companies
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booth_number TEXT,
    company_name TEXT NOT NULL,
    segment TEXT,
    description TEXT,
    website TEXT,
    primary_domain TEXT,
    visited BOOLEAN DEFAULT FALSE,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: notes
CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    type TEXT CHECK (type IN ('meeting', 'email', 'manual')),
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: attachments
CREATE TABLE IF NOT EXISTS attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    file_type TEXT CHECK (file_type IN ('image', 'document')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create a storage bucket for attachments (Run this in the Supabase SQL Editor if needed, or create manually in Storage UI)
-- insert into storage.buckets (id, name, public) values ('attachments', 'attachments', true);

-- Enable Row Level Security (Required by Supabase if using Anon keys directly from client)
-- NOTE: For this internal team tool, we will allow all authenticated OR anon access for simplicity. 
-- You can tighten these policies later in production.

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE attachments ENABLE ROW LEVEL SECURITY;

-- Allow public read/write access (Since this is a private dashboard URL, we'll keep RLS simple for the prototype)
CREATE POLICY "Allow public all on companies" ON companies FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow public all on notes" ON notes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow public all on attachments" ON attachments FOR ALL USING (true) WITH CHECK (true);

-- Allow public access to the storage bucket
-- CREATE POLICY "Give public access to attachments" ON storage.objects FOR ALL USING (bucket_id = 'attachments') WITH CHECK (bucket_id = 'attachments');
