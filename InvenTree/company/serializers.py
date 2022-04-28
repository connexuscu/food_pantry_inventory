"""
JSON serializers for Company app
"""

from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers

from sql_util.utils import SubqueryCount

from InvenTree.serializers import InvenTreeDecimalField
from InvenTree.serializers import InvenTreeImageSerializerField
from InvenTree.serializers import InvenTreeModelSerializer
from InvenTree.serializers import InvenTreeMoneySerializer

from part.serializers import PartBriefSerializer

from .models import Company
from .models import ManufacturerPart, ManufacturerPartParameter
from .models import SupplierPart, SupplierPriceBreak

from common.settings import currency_code_default, currency_code_mappings


class CompanyBriefSerializer(InvenTreeModelSerializer):
    """ Serializer for Company object (limited detail) """

    url = serializers.CharField(source='get_absolute_url', read_only=True)

    image = serializers.CharField(source='get_thumbnail_url', read_only=True)

    class Meta:
        model = Company
        fields = [
            'pk',
            'url',
            'name',
            'description',
            'image',
        ]


class CompanySerializer(InvenTreeModelSerializer):
    """ Serializer for Company object (full detail) """

    @staticmethod
    def annotate_queryset(queryset):

        # Add count of parts manufactured
        queryset = queryset.annotate(
            parts_manufactured=SubqueryCount('manufactured_parts')
        )

        queryset = queryset.annotate(
            parts_supplied=SubqueryCount('supplied_parts')
        )

        return queryset

    url = serializers.CharField(source='get_absolute_url', read_only=True)

    image = InvenTreeImageSerializerField(required=False, allow_null=True)

    parts_supplied = serializers.IntegerField(read_only=True)
    parts_manufactured = serializers.IntegerField(read_only=True)

    currency = serializers.ChoiceField(
        choices=currency_code_mappings(),
        initial=currency_code_default,
        help_text=_('Default currency used for this supplier'),
        label=_('Currency Code'),
        required=True,
    )

    class Meta:
        model = Company
        fields = [
            'pk',
            'url',
            'name',
            'description',
            'website',
            'name',
            'phone',
            'address',
            'email',
            'currency',
            'contact',
            'link',
            'image',
            'is_customer',
            'is_manufacturer',
            'is_supplier',
            'notes',
            'parts_supplied',
            'parts_manufactured',
        ]


class ManufacturerPartSerializer(InvenTreeModelSerializer):
    """
    Serializer for ManufacturerPart object
    """

    part_detail = PartBriefSerializer(source='part', many=False, read_only=True)

    manufacturer_detail = CompanyBriefSerializer(source='manufacturer', many=False, read_only=True)

    pretty_name = serializers.CharField(read_only=True)

    def __init__(self, *args, **kwargs):

        part_detail = kwargs.pop('part_detail', True)
        manufacturer_detail = kwargs.pop('manufacturer_detail', True)
        prettify = kwargs.pop('pretty', False)

        super(ManufacturerPartSerializer, self).__init__(*args, **kwargs)

        if part_detail is not True:
            self.fields.pop('part_detail')

        if manufacturer_detail is not True:
            self.fields.pop('manufacturer_detail')

        if prettify is not True:
            self.fields.pop('pretty_name')

    manufacturer = serializers.PrimaryKeyRelatedField(queryset=Company.objects.filter(is_manufacturer=True))

    class Meta:
        model = ManufacturerPart
        fields = [
            'pk',
            'part',
            'part_detail',
            'pretty_name',
            'manufacturer',
            'manufacturer_detail',
            'description',
            'MPN',
            'link',
        ]


class ManufacturerPartParameterSerializer(InvenTreeModelSerializer):
    """
    Serializer for the ManufacturerPartParameter model
    """

    manufacturer_part_detail = ManufacturerPartSerializer(source='manufacturer_part', many=False, read_only=True)

    def __init__(self, *args, **kwargs):

        man_detail = kwargs.pop('manufacturer_part_detail', False)

        super(ManufacturerPartParameterSerializer, self).__init__(*args, **kwargs)

        if not man_detail:
            self.fields.pop('manufacturer_part_detail')

    class Meta:
        model = ManufacturerPartParameter

        fields = [
            'pk',
            'manufacturer_part',
            'manufacturer_part_detail',
            'name',
            'value',
            'units',
        ]


class SupplierPartSerializer(InvenTreeModelSerializer):
    """ Serializer for SupplierPart object """

    part_detail = PartBriefSerializer(source='part', many=False, read_only=True)

    supplier_detail = CompanyBriefSerializer(source='supplier', many=False, read_only=True)

    manufacturer_detail = CompanyBriefSerializer(source='manufacturer_part.manufacturer', many=False, read_only=True)

    pretty_name = serializers.CharField(read_only=True)

    def __init__(self, *args, **kwargs):

        part_detail = kwargs.pop('part_detail', True)
        supplier_detail = kwargs.pop('supplier_detail', True)
        manufacturer_detail = kwargs.pop('manufacturer_detail', True)

        prettify = kwargs.pop('pretty', False)

        super(SupplierPartSerializer, self).__init__(*args, **kwargs)

        if part_detail is not True:
            self.fields.pop('part_detail')

        if supplier_detail is not True:
            self.fields.pop('supplier_detail')

        if manufacturer_detail is not True:
            self.fields.pop('manufacturer_detail')

        if prettify is not True:
            self.fields.pop('pretty_name')

    supplier = serializers.PrimaryKeyRelatedField(queryset=Company.objects.filter(is_supplier=True))

    manufacturer = serializers.CharField(read_only=True)

    MPN = serializers.CharField(read_only=True)

    manufacturer_part_detail = ManufacturerPartSerializer(source='manufacturer_part', read_only=True)

    class Meta:
        model = SupplierPart
        fields = [
            'description',
            'link',
            'manufacturer',
            'manufacturer_detail',
            'manufacturer_part',
            'manufacturer_part_detail',
            'MPN',
            'note',
            'pk',
            'packaging',
            'part',
            'part_detail',
            'pretty_name',
            'SKU',
            'supplier',
            'supplier_detail',
        ]

    def create(self, validated_data):
        """ Extract manufacturer data and process ManufacturerPart """

        # Create SupplierPart
        supplier_part = super().create(validated_data)

        # Get ManufacturerPart raw data (unvalidated)
        manufacturer = self.initial_data.get('manufacturer', None)
        MPN = self.initial_data.get('MPN', None)

        if manufacturer and MPN:
            kwargs = {
                'manufacturer': manufacturer,
                'MPN': MPN,
            }
            supplier_part.save(**kwargs)

        return supplier_part


class SupplierPriceBreakSerializer(InvenTreeModelSerializer):
    """ Serializer for SupplierPriceBreak object """

    quantity = InvenTreeDecimalField()

    price = InvenTreeMoneySerializer(
        allow_null=True,
        required=True,
        label=_('Price'),
    )

    price_currency = serializers.ChoiceField(
        choices=currency_code_mappings(),
        default=currency_code_default,
        label=_('Currency'),
    )

    class Meta:
        model = SupplierPriceBreak
        fields = [
            'pk',
            'part',
            'quantity',
            'price',
            'price_currency',
            'updated',
        ]
