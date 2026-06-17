-- 001_create_organizations_and_reports.sql
--
-- Primer migration: tablas base para el modelo de datos de SyntaxTax.
--
-- Crea:
--   - organizations: clientes identificados por su GitHub Organization ID
--   - financial_reports: reportes financieros JSONB vinculados a una organización
--   - Índices de rendimiento
--   - Row Level Security (RLS) con políticas restrictivas
--
-- Aplicar desde el SQL Editor de Supabase o con el CLI de Supabase:
--   supabase db push
--   (o copiar/pegar este archivo en el SQL Editor del Dashboard)

-- Habilitar la extensión para generar UUIDs si no está activa
create extension if not exists "uuid-ossp";

-- 1. Crear tabla de Organizaciones (Clientes)
create table organizations (
    id uuid primary key default uuid_generate_v4(),
    github_organization_id bigint unique not null,
    name varchar(255) not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- 2. Crear tabla de Reportes Financieros
create table financial_reports (
    id uuid primary key default uuid_generate_v4(),
    organization_id uuid references organizations(id) on delete cascade not null,
    github_delivery_id varchar(255) unique not null,
    repository_name varchar(255) not null,
    report_data jsonb not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- 3. Índices de rendimiento (Claves para búsquedas rápidas)
create index idx_financial_reports_org_id on financial_reports(organization_id);
create index idx_financial_reports_delivery_id on financial_reports(github_delivery_id);
create index idx_financial_reports_data on financial_reports using gin (report_data);

-- 4. Configuración de seguridad (RLS)
alter table organizations enable row level security;
alter table financial_reports enable row level security;

create policy "Allow read access via service_role only"
    on organizations for select
    using (false);

create policy "Allow read access to reports via service_role only"
    on financial_reports for select
    using (false);
