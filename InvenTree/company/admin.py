# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from import_export.admin import ImportExportModelAdmin
from import_export.resources import ModelResource
from import_export.fields import Field
import import_export.widgets as widgets

from .models import Company
from .models import SupplierPart
from .models import SupplierPriceBreak
from .models import ManufacturerPart, ManufacturerPartParameter

from part.models import Part


class CompanyResource(ModelResource):
    """ Class for managing Company data import/export """

    class Meta:
        model = Company
        skip_unchanged = True
        report_skipped = False
        clean_model_instances = True


class CompanyAdmin(ImportExportModelAdmin):

    resource_class = CompanyResource

    list_display = ('name', 'website', 'contact')

    search_fields = [
        'name',
        'description',
    ]


class SupplierPartResource(ModelResource):
    """
    Class for managing SupplierPart data import/export
    """

    part = Field(attribute='part', widget=widgets.ForeignKeyWidget(Part))

    part_name = Field(attribute='part__full_name', readonly=True)

    supplier = Field(attribute='supplier', widget=widgets.ForeignKeyWidget(Company))

    supplier_name = Field(attribute='supplier__name', readonly=True)

    class Meta:
        model = SupplierPart
        skip_unchanged = True
        report_skipped = True
        clean_model_instances = True


class SupplierPartAdmin(ImportExportModelAdmin):

    resource_class = SupplierPartResource

    list_display = ('part', 'supplier', 'SKU')

    search_fields = [
        'company__name',
        'part__name',
        'MPN',
        'SKU',
    ]

    autocomplete_fields = ('part', 'supplier', 'manufacturer_part',)


class ManufacturerPartResource(ModelResource):
    """
    Class for managing ManufacturerPart data import/export
    """

    part = Field(attribute='part', widget=widgets.ForeignKeyWidget(Part))

    part_name = Field(attribute='part__full_name', readonly=True)

    manufacturer = Field(attribute='manufacturer', widget=widgets.ForeignKeyWidget(Company))

    manufacturer_name = Field(attribute='manufacturer__name', readonly=True)

    class Meta:
        model = ManufacturerPart
        skip_unchanged = True
        report_skipped = True
        clean_model_instances = True


class ManufacturerPartAdmin(ImportExportModelAdmin):
    """
    Admin class for ManufacturerPart model
    """

    resource_class = ManufacturerPartResource

    list_display = ('part', 'manufacturer', 'MPN')

    search_fields = [
        'manufacturer__name',
        'part__name',
        'MPN',
    ]

    autocomplete_fields = ('part', 'manufacturer',)


class ManufacturerPartParameterResource(ModelResource):
    """
    Class for managing ManufacturerPartParameter data import/export
    """

    class Meta:
        model = ManufacturerPartParameter
        skip_unchanged = True
        report_skipped = True
        clean_model_instance = True


class ManufacturerPartParameterAdmin(ImportExportModelAdmin):
    """
    Admin class for ManufacturerPartParameter model
    """

    resource_class = ManufacturerPartParameterResource

    list_display = ('manufacturer_part', 'name', 'value')

    search_fields = [
        'manufacturer_part__manufacturer__name',
        'name',
        'value'
    ]

    autocomplete_fields = ('manufacturer_part',)


class SupplierPriceBreakResource(ModelResource):
    """ Class for managing SupplierPriceBreak data import/export """

    part = Field(attribute='part', widget=widgets.ForeignKeyWidget(SupplierPart))

    supplier_id = Field(attribute='part__supplier__pk', readonly=True)

    supplier_name = Field(attribute='part__supplier__name', readonly=True)

    part_name = Field(attribute='part__part__full_name', readonly=True)

    SKU = Field(attribute='part__SKU', readonly=True)

    MPN = Field(attribute='part__MPN', readonly=True)

    class Meta:
        model = SupplierPriceBreak
        skip_unchanged = True
        report_skipped = False
        clean_model_instances = True


class SupplierPriceBreakAdmin(ImportExportModelAdmin):

    resource_class = SupplierPriceBreakResource

    list_display = ('part', 'quantity', 'price')

    autocomplete_fields = ('part',)


admin.site.register(Company, CompanyAdmin)
admin.site.register(SupplierPart, SupplierPartAdmin)
admin.site.register(SupplierPriceBreak, SupplierPriceBreakAdmin)

admin.site.register(ManufacturerPart, ManufacturerPartAdmin)
admin.site.register(ManufacturerPartParameter, ManufacturerPartParameterAdmin)
