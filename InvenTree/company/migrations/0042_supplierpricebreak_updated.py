# Generated by Django 3.2.12 on 2022-03-14 22:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0041_alter_company_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplierpricebreak',
            name='updated',
            field=models.DateTimeField(auto_now=True, null=True, verbose_name='last updated'),
        ),
    ]
