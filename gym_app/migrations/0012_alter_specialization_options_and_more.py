# Generated by Django 5.1.4 on 2025-01-20 08:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gym_app", "0011_alter_specialization_options_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="specialization",
            options={"ordering": ["name"]},
        ),
        migrations.RemoveField(
            model_name="specialization",
            name="updated_at",
        ),
        migrations.AlterField(
            model_name="specialization",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
