"""Code generation from blueprint (stub)."""
def generate_backend(blueprint: dict) -> dict:
    """Generate backend code skeleton from blueprint."""
    name = blueprint.get("name", "app")
    return {
        "files": {
            f"apps/{name}/main.py": f"# {name} - auto-generated\nfrom fastapi import FastAPI\napp = FastAPI(title='{name}')\n",
            f"apps/{name}/models.py": "# auto-generated models\n",
            f"apps/{name}/routes.py": "# auto-generated routes\n",
        },
        "status": "generated",
    }
