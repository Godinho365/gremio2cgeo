from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_creditentry"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="method",
            field=models.CharField(
                choices=[
                    ("pix", "Pix"),
                    ("dinheiro", "Dinheiro"),
                    ("transferencia", "Transferência"),
                ],
                default="pix",
                max_length=20,
            ),
        ),
    ]
