from django.db import migrations

ROLES = [
    ("admin", "Administrador"),
    ("director", "Diretor(a) Patrimonial"),
    ("inventory", "Inventariante"),
    ("user", "Usuário"),
    ("auditor", "Auditor"),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for code, name in ROLES:
        Role.objects.update_or_create(code=code, defaults={"name": name})


def unseed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code__in=[c for c, _ in ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_initial")]
    operations = [migrations.RunPython(seed_roles, unseed_roles)]
