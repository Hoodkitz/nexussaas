"""DDL generation from blueprint."""
def generate_ddl(blueprint: dict) -> str:
    """Generate SQL DDL from blueprint entities."""
    lines = []
    for entity in blueprint.get("entities", []):
        name = entity.get("name", "unknown").lower()
        lines.append(f"CREATE TABLE {name} (")
        lines.append("  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),")
        for field in entity.get("fields", []):
            lines.append(f"  {field} TEXT,")
        lines.append("  tenant_id UUID NOT NULL,")
        lines.append("  created_at TIMESTAMPTZ DEFAULT now(),")
        lines.append(");")
        lines.append("")
    return "\n".join(lines)
