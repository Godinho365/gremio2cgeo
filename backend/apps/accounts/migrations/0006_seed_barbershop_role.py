from django.db import migrations

ROLE = ("barbershop", "Administrador da Barbearia")


def seed(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.update_or_create(code=ROLE[0], defaults={"name": ROLE[1]})


def unseed(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code=ROLE[0]).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_user_birth_date_user_cpf_user_full_name_user_phone")]
    operations = [migrations.RunPython(seed, unseed)]
