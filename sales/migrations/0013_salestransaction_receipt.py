# Generated by Django 5.2 on 2025-04-21 21:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0012_salestransaction_discount_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='salestransaction',
            name='receipt',
            field=models.FileField(blank=True, null=True, upload_to='receipts/'),
        ),
    ]
