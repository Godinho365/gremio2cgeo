from django.db import migrations

ROLE = ("barbershop_client", "Cliente da Barbearia")


def seed(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.update_or_create(code=ROLE[0], defaults={"name": ROLE[1]})


def unseed(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code=ROLE[0]).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_seed_barbershop_role")]
    operations = [migrations.RunPython(seed, unseed)]
