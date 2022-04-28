# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from import_export.admin import ImportExportModelAdmin

from import_export.resources import ModelResource
from import_export.fields import Field

from .models import PurchaseOrder, PurchaseOrderLineItem
from .models import SalesOrder, SalesOrderLineItem
from .models import SalesOrderShipment, SalesOrderAllocation


class PurchaseOrderLineItemInlineAdmin(admin.StackedInline):
    model = PurchaseOrderLineItem
    extra = 0


class PurchaseOrderAdmin(ImportExportModelAdmin):

    exclude = [
        'reference_int',
    ]

    list_display = (
        'reference',
        'supplier',
        'status',
        'description',
        'creation_date'
    )

    search_fields = [
        'reference',
        'supplier__name',
        'description',
    ]

    inlines = [
        PurchaseOrderLineItemInlineAdmin
    ]

    autocomplete_fields = ('supplier',)


class SalesOrderAdmin(ImportExportModelAdmin):

    exclude = [
        'reference_int',
    ]

    list_display = (
        'reference',
        'customer',
        'status',
        'description',
        'creation_date',
    )

    search_fields = [
        'reference',
        'customer__name',
        'description',
    ]

    autocomplete_fields = ('customer',)


class POLineItemResource(ModelResource):
    """ Class for managing import / export of POLineItem data """

    part_name = Field(attribute='part__part__name', readonly=True)

    manufacturer = Field(attribute='part__manufacturer', readonly=True)

    MPN = Field(attribute='part__MPN', readonly=True)

    SKU = Field(attribute='part__SKU', readonly=True)

    class Meta:
        model = PurchaseOrderLineItem
        skip_unchanged = True
        report_skipped = False
        clean_model_instances = True


class SOLineItemResource(ModelResource):
    """
    Class for managing import / export of SOLineItem data
    """

    part_name = Field(attribute='part__name', readonly=True)

    IPN = Field(attribute='part__IPN', readonly=True)

    description = Field(attribute='part__description', readonly=True)

    fulfilled = Field(attribute='fulfilled_quantity', readonly=True)

    def dehydrate_sale_price(self, item):
        """
        Return a string value of the 'sale_price' field, rather than the 'Money' object.
        Ref: https://github.com/inventree/InvenTree/issues/2207
        """

        if item.sale_price:
            return str(item.sale_price)
        else:
            return ''

    class Meta:
        model = SalesOrderLineItem
        skip_unchanged = True
        report_skipped = False
        clean_model_instances = True


class PurchaseOrderLineItemAdmin(ImportExportModelAdmin):

    resource_class = POLineItemResource

    list_display = (
        'order',
        'part',
        'quantity',
        'reference'
    )

    search_fields = ('reference',)

    autocomplete_fields = ('order', 'part', 'destination',)


class SalesOrderLineItemAdmin(ImportExportModelAdmin):

    resource_class = SOLineItemResource

    list_display = (
        'order',
        'part',
        'quantity',
        'reference'
    )

    search_fields = [
        'part__name',
        'order__reference',
        'order__customer__name',
        'reference',
    ]

    autocomplete_fields = ('order', 'part',)


class SalesOrderShipmentAdmin(ImportExportModelAdmin):

    list_display = [
        'order',
        'shipment_date',
        'reference',
    ]

    search_fields = [
        'reference',
        'order__reference',
        'order__customer__name',
    ]

    autocomplete_fields = ('order',)


class SalesOrderAllocationAdmin(ImportExportModelAdmin):

    list_display = (
        'line',
        'item',
        'quantity'
    )

    autocomplete_fields = ('line', 'shipment', 'item',)


admin.site.register(PurchaseOrder, PurchaseOrderAdmin)
admin.site.register(PurchaseOrderLineItem, PurchaseOrderLineItemAdmin)

admin.site.register(SalesOrder, SalesOrderAdmin)
admin.site.register(SalesOrderLineItem, SalesOrderLineItemAdmin)

admin.site.register(SalesOrderShipment, SalesOrderShipmentAdmin)
admin.site.register(SalesOrderAllocation, SalesOrderAllocationAdmin)
