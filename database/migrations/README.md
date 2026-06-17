# Migraciones de Base de Datos

Este directorio contiene las migraciones SQL para el esquema de Supabase (PostgreSQL).

## Convención

- Los archivos se nombran con el formato `NNN_descripcion.sql`
- `NNN` es un número de secuencia de 3 dígitos (001, 002, ...)
- Las migraciones son acumulativas e inmutables: una vez aplicadas, **no se editan**. Los cambios nuevos van en un archivo nuevo.

## Cómo aplicar migraciones

### Opción 1: SQL Editor de Supabase (recomendado para desarrollo)

Abrir el archivo SQL, copiar su contenido y pegarlo en el SQL Editor del Dashboard de Supabase.

### Opción 2: CLI de Supabase

```bash
supabase db push
```

### Opción 3: psql directo

```bash
psql "$SUPABASE_DATABASE_URL" -f database/migrations/001_create_organizations_and_reports.sql
```

## Variables de entorno necesarias

| Variable | Descripción |
|---|---|
| `SUPABASE_URL` | URL del proyecto Supabase (ej. `https://xxxxx.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Clave `service_role` para operaciones desde el backend |
| `SUPABASE_DATABASE_URL` | Connection string directo a PostgreSQL (para psql) |

Ver `.env.example` en la raíz del proyecto.
