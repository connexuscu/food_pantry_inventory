# Generated by Django 3.2.4 on 2021-09-02 00:42

from django.db import migrations
import django.db.models.deletion
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0065_auto_20210701_0509'),
        ('order', '0049_alter_purchaseorderlineitem_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchaseorderlineitem',
            name='destination',
            field=mptt.fields.TreeForeignKey(blank=True, help_text='Where does the Purchaser want this item to be stored?', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='po_lines', to='stock.stocklocation', verbose_name='Destination'),
        ),
    ]
