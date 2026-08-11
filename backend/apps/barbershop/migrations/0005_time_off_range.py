"""Folga vira período: `date` passa a ser `start_date`, e ganha `end_date`.

Escrita à mão para não perder as folgas já cadastradas: renomeia o campo (o
valor vem junto) e preenche o fim com o mesmo dia — folga de um dia é um
período com início e fim iguais.
"""

from django.db import migrations, models
import django.db.models.expressions


def fill_end_date(apps, schema_editor):
    BarberTimeOff = apps.get_model("barbershop", "BarberTimeOff")
    BarberTimeOff.objects.update(end_date=models.F("start_date"))


def clear_end_date(apps, schema_editor):
    """Na volta, um período de vários dias vira só o dia de início."""


class Migration(migrations.Migration):
    dependencies = [("barbershop", "0004_appointment_paid_with_credit")]

    operations = [
        migrations.RemoveConstraint(
            model_name="barbertimeoff",
            name="uq_time_off_per_day",
        ),
        migrations.RenameField(
            model_name="barbertimeoff",
            old_name="date",
            new_name="start_date",
        ),
        # Nasce nulo para as linhas existentes serem preenchidas antes de fechar.
        migrations.AddField(
            model_name="barbertimeoff",
            name="end_date",
            field=models.DateField(null=True),
        ),
        migrations.RunPython(fill_end_date, clear_end_date),
        migrations.AlterField(
            model_name="barbertimeoff",
            name="end_date",
            field=models.DateField(),
        ),
        migrations.AlterModelOptions(
            name="barbertimeoff",
            options={"ordering": ["start_date"]},
        ),
        migrations.AddConstraint(
            model_name="barbertimeoff",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    end_date__gte=django.db.models.expressions.F("start_date")
                ),
                name="ck_time_off_range",
            ),
        ),
    ]
