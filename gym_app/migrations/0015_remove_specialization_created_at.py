# Generated by Django 5.1.4 on 2025-01-20 09:17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("gym_app", "0014_alter_specialization_created_at"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="specialization",
            name="created_at",
        ),
    ]
