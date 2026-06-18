# Database Migrations

This directory contains SQL migrations for the Supabase (PostgreSQL) schema.

## Conventions

- Files are named `NNN_description.sql`
- `NNN` is a zero-padded sequence number (001, 002, ...)
- Migrations are cumulative and **immutable**: once applied, do not edit them. New changes go in a new file.

## How to apply migrations

### Option 1: Supabase SQL Editor (recommended for development)

Open the SQL file, copy its contents, and paste into the Supabase Dashboard SQL Editor.

### Option 2: Supabase CLI

```bash
supabase db push
```

### Option 3: Direct psql

```bash
psql "$SUPABASE_DATABASE_URL" -f database/migrations/001_create_organizations_and_reports.sql
```

## Required environment variables

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Supabase project URL (e.g. `https://xxxxx.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | `service_role` key for backend operations |
| `SUPABASE_DATABASE_URL` | Direct PostgreSQL connection string (for psql) |

See `.env.example` in the project root.
