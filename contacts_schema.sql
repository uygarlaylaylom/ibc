-- Table: contacts
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    title TEXT,
    email TEXT,
    phone TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS and allow public access for the prototype
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public all on contacts" ON contacts FOR ALL USING (true) WITH CHECK (true);
