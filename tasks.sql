-- Enable extension for UUIDs
create extension if not exists pgcrypto;

create table tasks (
  id uuid primary key default gen_random_uuid(),
  source_company text not null,
  task_description text not null,
  tags text[],
  mentions text[], -- Added for @mentions
  bracket_category text, -- Added for [bracket category]
  status text check (status in ('Todo', 'In Progress', 'Done')) default 'Todo',
  priority text check (priority in ('High', 'Normal', 'Low')) default 'Normal',
  created_at timestamp with time zone default now(),
  due_date timestamp with time zone null,
  owner text null,
  hall text null,
  category text null
);

-- Indexes
create index idx_tasks_status on tasks(status);
create index idx_tasks_priority on tasks(priority);
create index idx_tasks_tags on tasks using gin(tags);
create index idx_tasks_mentions on tasks using gin(mentions);

