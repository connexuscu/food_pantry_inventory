# Generated by Django 3.2.5 on 2021-10-13 10:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('part', '0072_bomitemsubstitute'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='bomitemsubstitute',
            options={'verbose_name': 'BOM Item Substitute'},
        ),
        migrations.AlterUniqueTogether(
            name='bomitemsubstitute',
            unique_together={('part', 'bom_item')},
        ),
    ]
