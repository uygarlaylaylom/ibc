-- Add tags array column to companies
ALTER TABLE companies ADD COLUMN tags TEXT[] DEFAULT '{}';

-- Allow deleting notes
CREATE POLICY "Allow public delete on notes" ON notes FOR DELETE USING (true);
