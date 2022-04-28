"""
JSON serializers for Part app
"""

import imghdr
from decimal import Decimal

from django.urls import reverse_lazy
from django.db import models, transaction
from django.db.models import ExpressionWrapper, F, Q, Func
from django.db.models import Subquery, OuterRef, FloatField

from django.db.models.functions import Coalesce
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers
from sql_util.utils import SubqueryCount, SubquerySum
from djmoney.contrib.django_rest_framework import MoneyField

from common.settings import currency_code_default, currency_code_mappings

from InvenTree.serializers import (DataFileUploadSerializer,
                                   DataFileExtractSerializer,
                                   InvenTreeAttachmentSerializerField,
                                   InvenTreeDecimalField,
                                   InvenTreeImageSerializerField,
                                   InvenTreeModelSerializer,
                                   InvenTreeAttachmentSerializer,
                                   InvenTreeMoneySerializer)

from InvenTree.status_codes import (BuildStatus,
                                    PurchaseOrderStatus,
                                    SalesOrderStatus)

from stock.models import StockItem

from .models import (BomItem, BomItemSubstitute,
                     Part, PartAttachment, PartCategory, PartRelated,
                     PartParameter, PartParameterTemplate, PartSellPriceBreak,
                     PartStar, PartTestTemplate, PartCategoryParameterTemplate,
                     PartInternalPriceBreak)


class CategorySerializer(InvenTreeModelSerializer):
    """ Serializer for PartCategory """

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

    def get_starred(self, category):
        """
        Return True if the category is directly "starred" by the current user
        """

        return category in self.context.get('starred_categories', [])

    url = serializers.CharField(source='get_absolute_url', read_only=True)

    parts = serializers.IntegerField(source='item_count', read_only=True)

    level = serializers.IntegerField(read_only=True)

    starred = serializers.SerializerMethodField()

    class Meta:
        model = PartCategory
        fields = [
            'pk',
            'name',
            'description',
            'default_location',
            'default_keywords',
            'level',
            'parent',
            'parts',
            'pathstring',
            'starred',
            'url',
        ]


class CategoryTree(InvenTreeModelSerializer):
    """
    Serializer for PartCategory tree
    """

    class Meta:
        model = PartCategory
        fields = [
            'pk',
            'name',
            'parent',
        ]


class PartAttachmentSerializer(InvenTreeAttachmentSerializer):
    """
    Serializer for the PartAttachment class
    """

    class Meta:
        model = PartAttachment

        fields = [
            'pk',
            'part',
            'attachment',
            'filename',
            'link',
            'comment',
            'upload_date',
        ]

        read_only_fields = [
            'upload_date',
        ]


class PartTestTemplateSerializer(InvenTreeModelSerializer):
    """
    Serializer for the PartTestTemplate class
    """

    key = serializers.CharField(read_only=True)

    class Meta:
        model = PartTestTemplate

        fields = [
            'pk',
            'key',
            'part',
            'test_name',
            'description',
            'required',
            'requires_value',
            'requires_attachment',
        ]


class PartSalePriceSerializer(InvenTreeModelSerializer):
    """
    Serializer for sale prices for Part model.
    """

    quantity = InvenTreeDecimalField()

    price = InvenTreeMoneySerializer(
        allow_null=True
    )

    price_currency = serializers.ChoiceField(
        choices=currency_code_mappings(),
        default=currency_code_default,
        label=_('Currency'),
        help_text=_('Purchase currency of this stock item'),
    )

    price_string = serializers.CharField(source='price', read_only=True)

    class Meta:
        model = PartSellPriceBreak
        fields = [
            'pk',
            'part',
            'quantity',
            'price',
            'price_currency',
            'price_string',
        ]


class PartInternalPriceSerializer(InvenTreeModelSerializer):
    """
    Serializer for internal prices for Part model.
    """

    quantity = InvenTreeDecimalField()

    price = InvenTreeMoneySerializer(
        allow_null=True
    )

    price_currency = serializers.ChoiceField(
        choices=currency_code_mappings(),
        default=currency_code_default,
        label=_('Currency'),
        help_text=_('Purchase currency of this stock item'),
    )

    price_string = serializers.CharField(source='price', read_only=True)

    class Meta:
        model = PartInternalPriceBreak
        fields = [
            'pk',
            'part',
            'quantity',
            'price',
            'price_currency',
            'price_string',
        ]


class PartThumbSerializer(serializers.Serializer):
    """
    Serializer for the 'image' field of the Part model.
    Used to serve and display existing Part images.
    """

    image = serializers.URLField(read_only=True)
    count = serializers.IntegerField(read_only=True)


class PartThumbSerializerUpdate(InvenTreeModelSerializer):
    """ Serializer for updating Part thumbnail """

    def validate_image(self, value):
        """
        Check that file is an image.
        """
        validate = imghdr.what(value)
        if not validate:
            raise serializers.ValidationError("File is not an image")
        return value

    image = InvenTreeAttachmentSerializerField(required=True)

    class Meta:
        model = Part
        fields = [
            'image',
        ]


class PartParameterTemplateSerializer(InvenTreeModelSerializer):
    """ JSON serializer for the PartParameterTemplate model """

    class Meta:
        model = PartParameterTemplate
        fields = [
            'pk',
            'name',
            'units',
        ]


class PartParameterSerializer(InvenTreeModelSerializer):
    """ JSON serializers for the PartParameter model """

    template_detail = PartParameterTemplateSerializer(source='template', many=False, read_only=True)

    class Meta:
        model = PartParameter
        fields = [
            'pk',
            'part',
            'template',
            'template_detail',
            'data'
        ]


class PartBriefSerializer(InvenTreeModelSerializer):
    """ Serializer for Part (brief detail) """

    thumbnail = serializers.CharField(source='get_thumbnail_url', read_only=True)

    stock = serializers.FloatField(source='total_stock')

    class Meta:
        model = Part
        fields = [
            'pk',
            'IPN',
            'default_location',
            'name',
            'revision',
            'full_name',
            'description',
            'thumbnail',
            'active',
            'assembly',
            'is_template',
            'purchaseable',
            'salable',
            'stock',
            'trackable',
            'virtual',
            'units',
        ]


class PartSerializer(InvenTreeModelSerializer):
    """ Serializer for complete detail information of a part.
    Used when displaying all details of a single component.
    """

    def get_api_url(self):
        return reverse_lazy('api-part-list')

    def __init__(self, *args, **kwargs):
        """
        Custom initialization method for PartSerializer,
        so that we can optionally pass extra fields based on the query.
        """

        self.starred_parts = kwargs.pop('starred_parts', [])

        category_detail = kwargs.pop('category_detail', False)

        parameters = kwargs.pop('parameters', False)

        super().__init__(*args, **kwargs)

        if category_detail is not True:
            self.fields.pop('category_detail')

        if parameters is not True:
            self.fields.pop('parameters')

    @staticmethod
    def annotate_queryset(queryset):
        """
        Add some extra annotations to the queryset,
        performing database queries as efficiently as possible,
        to reduce database trips.
        """

        # Annotate with the total 'in stock' quantity
        queryset = queryset.annotate(
            in_stock=Coalesce(
                SubquerySum('stock_items__quantity', filter=StockItem.IN_STOCK_FILTER),
                Decimal(0),
                output_field=models.DecimalField(),
            ),
        )

        # Annotate with the total number of stock items
        queryset = queryset.annotate(
            stock_item_count=SubqueryCount('stock_items')
        )

        # Annotate with the total variant stock quantity
        variant_query = StockItem.objects.filter(
            part__tree_id=OuterRef('tree_id'),
            part__lft__gt=OuterRef('lft'),
            part__rght__lt=OuterRef('rght'),
        ).filter(StockItem.IN_STOCK_FILTER)

        queryset = queryset.annotate(
            variant_stock=Coalesce(
                Subquery(
                    variant_query.annotate(
                        total=Func(F('quantity'), function='SUM', output_field=FloatField())
                    ).values('total')),
                0,
                output_field=FloatField(),
            )
        )

        # Filter to limit builds to "active"
        build_filter = Q(
            status__in=BuildStatus.ACTIVE_CODES
        )

        # Annotate with the total 'building' quantity
        queryset = queryset.annotate(
            building=Coalesce(
                SubquerySum('builds__quantity', filter=build_filter),
                Decimal(0),
                output_field=models.DecimalField(),
            )
        )

        # Filter to limit orders to "open"
        order_filter = Q(
            order__status__in=PurchaseOrderStatus.OPEN
        )

        # Annotate with the total 'on order' quantity
        queryset = queryset.annotate(
            ordering=Coalesce(
                SubquerySum('supplier_parts__purchase_order_line_items__quantity', filter=order_filter),
                Decimal(0),
                output_field=models.DecimalField(),
            ) - Coalesce(
                SubquerySum('supplier_parts__purchase_order_line_items__received', filter=order_filter),
                Decimal(0),
                output_field=models.DecimalField(),
            )
        )

        # Annotate with the number of 'suppliers'
        queryset = queryset.annotate(
            suppliers=Coalesce(
                SubqueryCount('supplier_parts'),
                Decimal(0),
                output_field=models.DecimalField(),
            ),
        )

        """
        Annotate with the number of stock items allocated to sales orders.
        This annotation is modeled on Part.sales_order_allocations() method:

        - Only look for "open" orders
        - Stock items have not been "shipped"
        """
        so_allocation_filter = Q(
            line__order__status__in=SalesOrderStatus.OPEN,  # LineItem points to an OPEN order
            shipment__shipment_date=None,  # Allocated item has *not* been shipped out
        )

        queryset = queryset.annotate(
            allocated_to_sales_orders=Coalesce(
                SubquerySum('stock_items__sales_order_allocations__quantity', filter=so_allocation_filter),
                Decimal(0),
                output_field=models.DecimalField(),
            )
        )

        """
        Annotate with the number of stock items allocated to build orders.
        This annotation is modeled on Part.build_order_allocations() method
        """
        bo_allocation_filter = Q(
            build__status__in=BuildStatus.ACTIVE_CODES,
        )

        queryset = queryset.annotate(
            allocated_to_build_orders=Coalesce(
                SubquerySum('stock_items__allocations__quantity', filter=bo_allocation_filter),
                Decimal(0),
                output_field=models.DecimalField(),
            )
        )

        # Annotate with the total 'available stock' quantity
        # This is the current stock, minus any allocations
        queryset = queryset.annotate(
            unallocated_stock=ExpressionWrapper(
                F('in_stock') - F('allocated_to_sales_orders') - F('allocated_to_build_orders'),
                output_field=models.DecimalField(),
            )
        )

        return queryset

    def get_starred(self, part):
        """
        Return "true" if the part is starred by the current user.
        """

        return part in self.starred_parts

    # Extra detail for the category
    category_detail = CategorySerializer(source='category', many=False, read_only=True)

    # Calculated fields
    allocated_to_build_orders = serializers.FloatField(read_only=True)
    allocated_to_sales_orders = serializers.FloatField(read_only=True)
    unallocated_stock = serializers.FloatField(read_only=True)
    building = serializers.FloatField(read_only=True)
    in_stock = serializers.FloatField(read_only=True)
    variant_stock = serializers.FloatField(read_only=True)
    ordering = serializers.FloatField(read_only=True)
    stock_item_count = serializers.IntegerField(read_only=True)
    suppliers = serializers.IntegerField(read_only=True)

    image = InvenTreeImageSerializerField(required=False, allow_null=True)
    thumbnail = serializers.CharField(source='get_thumbnail_url', read_only=True)
    starred = serializers.SerializerMethodField()

    # PrimaryKeyRelated fields (Note: enforcing field type here results in much faster queries, somehow...)
    category = serializers.PrimaryKeyRelatedField(queryset=PartCategory.objects.all())

    parameters = PartParameterSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Part
        partial = True
        fields = [
            'active',
            'allocated_to_build_orders',
            'allocated_to_sales_orders',
            'assembly',
            'category',
            'category_detail',
            'component',
            'default_expiry',
            'default_location',
            'default_supplier',
            'description',
            'full_name',
            'image',
            'in_stock',
            'variant_stock',
            'ordering',
            'building',
            'IPN',
            'is_template',
            'keywords',
            'link',
            'minimum_stock',
            'name',
            'notes',
            'parameters',
            'pk',
            'purchaseable',
            'revision',
            'salable',
            'starred',
            'stock_item_count',
            'suppliers',
            'thumbnail',
            'trackable',
            'unallocated_stock',
            'units',
            'variant_of',
            'virtual',
        ]


class PartRelationSerializer(InvenTreeModelSerializer):
    """
    Serializer for a PartRelated model
    """

    part_1_detail = PartSerializer(source='part_1', read_only=True, many=False)
    part_2_detail = PartSerializer(source='part_2', read_only=True, many=False)

    class Meta:
        model = PartRelated
        fields = [
            'pk',
            'part_1',
            'part_1_detail',
            'part_2',
            'part_2_detail',
        ]


class PartStarSerializer(InvenTreeModelSerializer):
    """ Serializer for a PartStar object """

    partname = serializers.CharField(source='part.full_name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = PartStar
        fields = [
            'pk',
            'part',
            'partname',
            'user',
            'username',
        ]


class BomItemSubstituteSerializer(InvenTreeModelSerializer):
    """
    Serializer for the BomItemSubstitute class
    """

    part_detail = PartBriefSerializer(source='part', read_only=True, many=False)

    class Meta:
        model = BomItemSubstitute
        fields = [
            'pk',
            'bom_item',
            'part',
            'part_detail',
        ]


class BomItemSerializer(InvenTreeModelSerializer):
    """
    Serializer for BomItem object
    """

    price_range = serializers.CharField(read_only=True)

    quantity = InvenTreeDecimalField(required=True)

    def validate_quantity(self, quantity):
        if quantity <= 0:
            raise serializers.ValidationError(_("Quantity must be greater than zero"))

        return quantity

    part = serializers.PrimaryKeyRelatedField(queryset=Part.objects.filter(assembly=True))

    substitutes = BomItemSubstituteSerializer(many=True, read_only=True)

    part_detail = PartBriefSerializer(source='part', many=False, read_only=True)

    sub_part = serializers.PrimaryKeyRelatedField(queryset=Part.objects.filter(component=True))

    sub_part_detail = PartBriefSerializer(source='sub_part', many=False, read_only=True)

    validated = serializers.BooleanField(read_only=True, source='is_line_valid')

    purchase_price_min = MoneyField(max_digits=19, decimal_places=4, read_only=True)

    purchase_price_max = MoneyField(max_digits=19, decimal_places=4, read_only=True)

    purchase_price_avg = serializers.SerializerMethodField()

    purchase_price_range = serializers.SerializerMethodField()

    # Annotated fields for available stock
    available_stock = serializers.FloatField(read_only=True)
    available_substitute_stock = serializers.FloatField(read_only=True)
    available_variant_stock = serializers.FloatField(read_only=True)

    def __init__(self, *args, **kwargs):
        # part_detail and sub_part_detail serializers are only included if requested.
        # This saves a bunch of database requests

        part_detail = kwargs.pop('part_detail', False)
        sub_part_detail = kwargs.pop('sub_part_detail', False)
        include_pricing = kwargs.pop('include_pricing', False)

        super(BomItemSerializer, self).__init__(*args, **kwargs)

        if part_detail is not True:
            self.fields.pop('part_detail')

        if sub_part_detail is not True:
            self.fields.pop('sub_part_detail')

        if not include_pricing:
            # Remove all pricing related fields
            self.fields.pop('price_range')
            self.fields.pop('purchase_price_min')
            self.fields.pop('purchase_price_max')
            self.fields.pop('purchase_price_avg')
            self.fields.pop('purchase_price_range')

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.prefetch_related('part')
        queryset = queryset.prefetch_related('part__category')
        queryset = queryset.prefetch_related('part__stock_items')

        queryset = queryset.prefetch_related('sub_part')
        queryset = queryset.prefetch_related('sub_part__category')

        queryset = queryset.prefetch_related(
            'sub_part__stock_items',
            'sub_part__stock_items__allocations',
            'sub_part__stock_items__sales_order_allocations',
        )

        queryset = queryset.prefetch_related(
            'substitutes',
            'substitutes__part__stock_items',
        )

        queryset = queryset.prefetch_related('sub_part__supplier_parts__pricebreaks')
        return queryset

    @staticmethod
    def annotate_queryset(queryset):
        """
        Annotate the BomItem queryset with extra information:

        Annotations:
            available_stock: The amount of stock available for the sub_part Part object
        """

        """
        Construct an "available stock" quantity:
        available_stock = total_stock - build_order_allocations - sales_order_allocations
        """

        build_order_filter = Q(build__status__in=BuildStatus.ACTIVE_CODES)
        sales_order_filter = Q(
            line__order__status__in=SalesOrderStatus.OPEN,
            shipment__shipment_date=None,
        )

        # Calculate "total stock" for the referenced sub_part
        # Calculate the "build_order_allocations" for the sub_part
        # Note that these fields are only aliased, not annotated
        queryset = queryset.alias(
            total_stock=Coalesce(
                SubquerySum(
                    'sub_part__stock_items__quantity',
                    filter=StockItem.IN_STOCK_FILTER
                ),
                Decimal(0),
                output_field=models.DecimalField(),
            ),
            allocated_to_sales_orders=Coalesce(
                SubquerySum(
                    'sub_part__stock_items__sales_order_allocations__quantity',
                    filter=sales_order_filter,
                ),
                Decimal(0),
                output_field=models.DecimalField(),
            ),
            allocated_to_build_orders=Coalesce(
                SubquerySum(
                    'sub_part__stock_items__allocations__quantity',
                    filter=build_order_filter,
                ),
                Decimal(0),
                output_field=models.DecimalField(),
            ),
        )

        # Calculate 'available_stock' based on previously annotated fields
        queryset = queryset.annotate(
            available_stock=ExpressionWrapper(
                F('total_stock') - F('allocated_to_sales_orders') - F('allocated_to_build_orders'),
                output_field=models.DecimalField(),
            )
        )

        # Extract similar information for any 'substitute' parts
        queryset = queryset.alias(
            substitute_stock=Coalesce(
                SubquerySum(
                    'substitutes__part__stock_items__quantity',
                    filter=StockItem.IN_STOCK_FILTER,
                ),
                Decimal(0),
                output_field=models.DecimalField(),
            ),
            substitute_build_allocations=Coalesce(
                SubquerySum(
                    'substitutes__part__stock_items__allocations__quantity',
                    filter=build_order_filter,
                ),
                Decimal(0),
                output_field=models.DecimalField(),
            ),
            substitute_sales_allocations=Coalesce(
                SubquerySum(
                    'substitutes__part__stock_items__sales_order_allocations__quantity',
                    filter=sales_order_filter,
                ),
                Decimal(0),
                output_field=models.DecimalField(),
            ),
        )

        # Calculate 'available_substitute_stock' field
        queryset = queryset.annotate(
            available_substitute_stock=ExpressionWrapper(
                F('substitute_stock') - F('substitute_build_allocations') - F('substitute_sales_allocations'),
                output_field=models.DecimalField(),
            )
        )

        # Annotate the queryset with 'available variant stock' information
        variant_stock_query = StockItem.objects.filter(
            part__tree_id=OuterRef('sub_part__tree_id'),
            part__lft__gt=OuterRef('sub_part__lft'),
            part__rght__lt=OuterRef('sub_part__rght'),
        ).filter(StockItem.IN_STOCK_FILTER)

        queryset = queryset.alias(
            variant_stock_total=Coalesce(
                Subquery(
                    variant_stock_query.annotate(
                        total=Func(F('quantity'), function='SUM', output_field=FloatField())
                    ).values('total')),
                0,
                output_field=FloatField()
            ),
            variant_stock_build_order_allocations=Coalesce(
                Subquery(
                    variant_stock_query.annotate(
                        total=Func(F('sales_order_allocations__quantity'), function='SUM', output_field=FloatField()),
                    ).values('total')),
                0,
                output_field=FloatField(),
            ),
            variant_stock_sales_order_allocations=Coalesce(
                Subquery(
                    variant_stock_query.annotate(
                        total=Func(F('allocations__quantity'), function='SUM', output_field=FloatField()),
                    ).values('total')),
                0,
                output_field=FloatField(),
            )
        )

        queryset = queryset.annotate(
            available_variant_stock=ExpressionWrapper(
                F('variant_stock_total') - F('variant_stock_build_order_allocations') - F('variant_stock_sales_order_allocations'),
                output_field=FloatField(),
            )
        )

        return queryset

    def get_purchase_price_range(self, obj):
        """ Return purchase price range """

        try:
            purchase_price_min = obj.purchase_price_min
        except AttributeError:
            return None

        try:
            purchase_price_max = obj.purchase_price_max
        except AttributeError:
            return None

        if purchase_price_min and not purchase_price_max:
            # Get price range
            purchase_price_range = str(purchase_price_max)
        elif not purchase_price_min and purchase_price_max:
            # Get price range
            purchase_price_range = str(purchase_price_max)
        elif purchase_price_min and purchase_price_max:
            # Get price range
            if purchase_price_min >= purchase_price_max:
                # If min > max: use min only
                purchase_price_range = str(purchase_price_min)
            else:
                purchase_price_range = str(purchase_price_min) + " - " + str(purchase_price_max)
        else:
            purchase_price_range = '-'

        return purchase_price_range

    def get_purchase_price_avg(self, obj):
        """ Return purchase price average """

        try:
            purchase_price_avg = obj.purchase_price_avg
        except AttributeError:
            return None

        if purchase_price_avg:
            # Get string representation of price average
            purchase_price_avg = str(purchase_price_avg)
        else:
            purchase_price_avg = '-'

        return purchase_price_avg

    class Meta:
        model = BomItem
        fields = [
            'allow_variants',
            'inherited',
            'note',
            'optional',
            'overage',
            'pk',
            'part',
            'part_detail',
            'purchase_price_avg',
            'purchase_price_max',
            'purchase_price_min',
            'purchase_price_range',
            'quantity',
            'reference',
            'sub_part',
            'sub_part_detail',
            'substitutes',
            'price_range',
            'validated',

            # Annotated fields describing available quantity
            'available_stock',
            'available_substitute_stock',
            'available_variant_stock',

        ]


class CategoryParameterTemplateSerializer(InvenTreeModelSerializer):
    """ Serializer for PartCategoryParameterTemplate """

    parameter_template = PartParameterTemplateSerializer(many=False,
                                                         read_only=True)

    category_detail = CategorySerializer(source='category', many=False, read_only=True)

    class Meta:
        model = PartCategoryParameterTemplate
        fields = [
            'pk',
            'category',
            'category_detail',
            'parameter_template',
            'default_value',
        ]


class PartCopyBOMSerializer(serializers.Serializer):
    """
    Serializer for copying a BOM from another part
    """

    class Meta:
        fields = [
            'part',
            'remove_existing',
            'copy_substitutes',
            'include_inherited',
            'skip_invalid',
        ]

    part = serializers.PrimaryKeyRelatedField(
        queryset=Part.objects.all(),
        many=False,
        required=True,
        allow_null=False,
        label=_('Part'),
        help_text=_('Select part to copy BOM from'),
    )

    def validate_part(self, part):
        """
        Check that a 'valid' part was selected
        """

        return part

    remove_existing = serializers.BooleanField(
        label=_('Remove Existing Data'),
        help_text=_('Remove existing BOM items before copying'),
        default=True,
    )

    include_inherited = serializers.BooleanField(
        label=_('Include Inherited'),
        help_text=_('Include BOM items which are inherited from templated parts'),
        default=False,
    )

    skip_invalid = serializers.BooleanField(
        label=_('Skip Invalid Rows'),
        help_text=_('Enable this option to skip invalid rows'),
        default=False,
    )

    copy_substitutes = serializers.BooleanField(
        label=_('Copy Substitute Parts'),
        help_text=_('Copy substitute parts when duplicate BOM items'),
        default=True,
    )

    def save(self):
        """
        Actually duplicate the BOM
        """

        base_part = self.context['part']

        data = self.validated_data

        base_part.copy_bom_from(
            data['part'],
            clear=data.get('remove_existing', True),
            skip_invalid=data.get('skip_invalid', False),
            include_inherited=data.get('include_inherited', False),
            copy_substitutes=data.get('copy_substitutes', True),
        )


class BomImportUploadSerializer(DataFileUploadSerializer):
    """
    Serializer for uploading a file and extracting data from it.
    """

    TARGET_MODEL = BomItem

    class Meta:
        fields = [
            'data_file',
            'part',
            'clear_existing_bom',
        ]

    part = serializers.PrimaryKeyRelatedField(
        queryset=Part.objects.all(),
        required=True,
        allow_null=False,
        many=False,
    )

    clear_existing_bom = serializers.BooleanField(
        label=_('Clear Existing BOM'),
        help_text=_('Delete existing BOM items before uploading')
    )

    def save(self):

        data = self.validated_data

        if data.get('clear_existing_bom', False):
            part = data['part']

            with transaction.atomic():
                part.bom_items.all().delete()


class BomImportExtractSerializer(DataFileExtractSerializer):
    """
    """

    TARGET_MODEL = BomItem

    def validate_extracted_columns(self):
        super().validate_extracted_columns()

        part_columns = ['part', 'part_name', 'part_ipn', 'part_id']

        if not any([col in self.columns for col in part_columns]):
            # At least one part column is required!
            raise serializers.ValidationError(_("No part column specified"))

    def process_row(self, row):

        # Skip any rows which are at a lower "level"
        level = row.get('level', None)

        if level is not None:
            try:
                level = int(level)
                if level != 1:
                    # Skip this row
                    return None
            except:
                pass

        # Attempt to extract a valid part based on the provided data
        part_id = row.get('part_id', row.get('part', None))
        part_name = row.get('part_name', row.get('part', None))
        part_ipn = row.get('part_ipn', None)

        part = None

        if part_id is not None:
            try:
                part = Part.objects.get(pk=part_id)
            except (ValueError, Part.DoesNotExist):
                pass

        # No direct match, where else can we look?
        if part is None and (part_name or part_ipn):
            queryset = Part.objects.all()

            if part_name:
                queryset = queryset.filter(name=part_name)

            if part_ipn:
                queryset = queryset.filter(IPN=part_ipn)

            if queryset.exists():
                if queryset.count() == 1:
                    part = queryset.first()
                else:
                    row['errors']['part'] = _('Multiple matching parts found')

        if part is None:
            row['errors']['part'] = _('No matching part found')
        else:
            if not part.component:
                row['errors']['part'] = _('Part is not designated as a component')

        # Update the 'part' value in the row
        row['part'] = part.pk if part is not None else None

        # Check the provided 'quantity' value
        quantity = row.get('quantity', None)

        if quantity is None:
            row['errors']['quantity'] = _('Quantity not provided')
        else:
            try:
                quantity = Decimal(quantity)

                if quantity <= 0:
                    row['errors']['quantity'] = _('Quantity must be greater than zero')
            except:
                row['errors']['quantity'] = _('Invalid quantity')

        return row


class BomImportSubmitSerializer(serializers.Serializer):
    """
    Serializer for uploading a BOM against a specified part.

    A "BOM" is a set of BomItem objects which are to be validated together as a set
    """

    items = BomItemSerializer(many=True, required=True)

    def validate(self, data):

        items = data['items']

        if len(items) == 0:
            raise serializers.ValidationError(_("At least one BOM item is required"))

        data = super().validate(data)

        return data

    def save(self):

        data = self.validated_data

        items = data['items']

        try:
            with transaction.atomic():

                for item in items:

                    part = item['part']
                    sub_part = item['sub_part']

                    # Ignore duplicate BOM items
                    if BomItem.objects.filter(part=part, sub_part=sub_part).exists():
                        continue

                    # Create a new BomItem object
                    BomItem.objects.create(**item)

        except Exception as e:
            raise serializers.ValidationError(detail=serializers.as_serializer_error(e))
