import os

from supabase import Client, create_client

_url: str | None = None
_key: str | None = None
_client: Client | None = None


def get_client() -> Client:
    global _client, _url, _key
    if _client is None:
        _url = os.getenv("SUPABASE_URL", "")
        _key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not _url or not _key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
            )
        _client = create_client(_url, _key)
    return _client


def upsert_organization(github_org_id: int, name: str) -> str:
    client = get_client()
    result = (
        client.table("organizations")
        .upsert(
            {"github_organization_id": github_org_id, "name": name},
            on_conflict="github_organization_id",
        )
        .execute()
    )
    return result.data[0]["id"]


def save_report(
    organization_id: str,
    delivery_id: str,
    repo_name: str,
    report_data: dict,
) -> None:
    client = get_client()
    client.table("financial_reports").insert(
        {
            "organization_id": organization_id,
            "github_delivery_id": delivery_id,
            "repository_name": repo_name,
            "report_data": report_data,
        }
    ).execute()


def get_report_by_delivery_id(delivery_id: str) -> dict | None:
    client = get_client()
    result = (
        client.table("financial_reports")
        .select("*")
        .eq("github_delivery_id", delivery_id)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]


def get_latest_reports_by_org(github_org_id: int) -> list[dict]:
    client = get_client()
    org_result = (
        client.table("organizations")
        .select("id")
        .eq("github_organization_id", github_org_id)
        .execute()
    )
    if not org_result.data:
        return []

    org_uuid = org_result.data[0]["id"]
    reports_result = (
        client.table("financial_reports")
        .select("*")
        .eq("organization_id", org_uuid)
        .order("created_at", desc=True)
        .execute()
    )

    seen: set[str] = set()
    latest: list[dict] = []
    for r in reports_result.data:
        repo = r["repository_name"]
        if repo not in seen:
            seen.add(repo)
            latest.append(r)
    return latest
