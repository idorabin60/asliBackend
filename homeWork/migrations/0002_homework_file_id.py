# Generated by Django 4.0.10 on 2025-03-02 13:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('homeWork', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='homework',
            name='file_id',
            field=models.CharField(default='1', max_length=255, unique=True),
        ),
    ]
