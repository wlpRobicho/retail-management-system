# Generated by Django 5.2 on 2025-04-19 22:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0005_alter_salesitem_quantity'),
    ]

    operations = [
        migrations.AlterField(
            model_name='salelog',
            name='quantity',
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
    ]
