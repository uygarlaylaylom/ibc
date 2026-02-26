-- ==============================================================================
-- IBS 2026 İstihbarat Merkezi v2.0 - Phase 1 Migration Script
-- ==============================================================================

-- 1. Create the Unified Activities Table
CREATE TABLE IF NOT EXISTS activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    type TEXT CHECK (type IN ('note', 'email', 'task', 'meeting')) DEFAULT 'note',
    content TEXT NOT NULL,
    
    -- Task specific fields
    status TEXT CHECK (status IN ('Todo', 'In Progress', 'Done')) DEFAULT 'Todo',
    priority TEXT CHECK (priority IN ('High', 'Normal', 'Low')) DEFAULT 'Normal',
    due_date TIMESTAMP WITH TIME ZONE NULL,
    
    -- Parsed metadata (for both notes and tasks)
    tags TEXT[] DEFAULT '{}',
    mentions TEXT[] DEFAULT '{}',
    bracket_category TEXT,
    
    owner TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Migrate existing 'notes' to 'activities'
INSERT INTO activities (id, company_id, type, content, created_at)
SELECT 
    id, 
    company_id, 
    CASE WHEN type = 'manual' THEN 'note' ELSE type END as type, 
    content, 
    created_at
FROM notes;

-- 3. Migrate existing 'tasks' to 'activities'
-- Note: 'tasks' table used 'source_company' as text, so we JOIN with companies to get company_id
INSERT INTO activities (id, company_id, type, content, tags, mentions, bracket_category, status, priority, due_date, owner, created_at)
SELECT 
    t.id,
    c.id as company_id,
    'task' as type,
    t.task_description as content,
    t.tags,
    t.mentions,
    t.bracket_category,
    t.status,
    t.priority,
    t.due_date,
    t.owner,
    t.created_at
FROM tasks t
LEFT JOIN companies c ON t.source_company = c.company_name
WHERE c.id IS NOT NULL; -- Only migrate tasks that have a matching company

-- 4. Enable RLS and Create Policy
ALTER TABLE activities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public all on activities" ON activities FOR ALL USING (true) WITH CHECK (true);

-- 5. Rename old tables to prevent accidental usage (Optional but recommended)
-- ALTER TABLE notes RENAME TO old_notes;
-- ALTER TABLE tasks RENAME TO old_tasks;

-- 6. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_activities_company_id ON activities(company_id);
CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(type);
CREATE INDEX IF NOT EXISTS idx_activities_status ON activities(status);
