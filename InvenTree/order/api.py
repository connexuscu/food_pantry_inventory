"""
JSON API for the Order app
"""

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url, include
from django.db.models import Q, F

from django_filters import rest_framework as rest_filters
from rest_framework import generics
from rest_framework import filters, status
from rest_framework.response import Response

from company.models import SupplierPart

from InvenTree.filters import InvenTreeOrderingFilter
from InvenTree.helpers import str2bool, DownloadFile
from InvenTree.api import AttachmentMixin
from InvenTree.status_codes import PurchaseOrderStatus, SalesOrderStatus

from order.admin import POLineItemResource
import order.models as models
import order.serializers as serializers
from part.models import Part
from users.models import Owner


class POFilter(rest_filters.FilterSet):
    """
    Custom API filters for the POList endpoint
    """

    assigned_to_me = rest_filters.BooleanFilter(label='assigned_to_me', method='filter_assigned_to_me')

    def filter_assigned_to_me(self, queryset, name, value):
        """
        Filter by orders which are assigned to the current user
        """

        value = str2bool(value)

        # Work out who "me" is!
        owners = Owner.get_owners_matching_user(self.request.user)

        if value:
            queryset = queryset.filter(responsible__in=owners)
        else:
            queryset = queryset.exclude(responsible__in=owners)

        return queryset

    class Meta:
        model = models.PurchaseOrder
        fields = [
            'supplier',
        ]


class POList(generics.ListCreateAPIView):
    """ API endpoint for accessing a list of PurchaseOrder objects

    - GET: Return list of PO objects (with filters)
    - POST: Create a new PurchaseOrder object
    """

    queryset = models.PurchaseOrder.objects.all()
    serializer_class = serializers.POSerializer
    filterset_class = POFilter

    def create(self, request, *args, **kwargs):
        """
        Save user information on create
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = serializer.save()
        item.created_by = request.user
        item.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_serializer(self, *args, **kwargs):

        try:
            kwargs['supplier_detail'] = str2bool(self.request.query_params.get('supplier_detail', False))
        except AttributeError:
            pass

        # Ensure the request context is passed through
        kwargs['context'] = self.get_serializer_context()

        return self.serializer_class(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):

        queryset = super().get_queryset(*args, **kwargs)

        queryset = queryset.prefetch_related(
            'supplier',
            'lines',
        )

        queryset = serializers.POSerializer.annotate_queryset(queryset)

        return queryset

    def filter_queryset(self, queryset):

        # Perform basic filtering
        queryset = super().filter_queryset(queryset)

        params = self.request.query_params

        # Filter by 'outstanding' status
        outstanding = params.get('outstanding', None)

        if outstanding is not None:
            outstanding = str2bool(outstanding)

            if outstanding:
                queryset = queryset.filter(status__in=PurchaseOrderStatus.OPEN)
            else:
                queryset = queryset.exclude(status__in=PurchaseOrderStatus.OPEN)

        # Filter by 'overdue' status
        overdue = params.get('overdue', None)

        if overdue is not None:
            overdue = str2bool(overdue)

            if overdue:
                queryset = queryset.filter(models.PurchaseOrder.OVERDUE_FILTER)
            else:
                queryset = queryset.exclude(models.PurchaseOrder.OVERDUE_FILTER)

        # Special filtering for 'status' field
        status = params.get('status', None)

        if status is not None:
            # First attempt to filter by integer value
            queryset = queryset.filter(status=status)

        # Attempt to filter by part
        part = params.get('part', None)

        if part is not None:
            try:
                part = Part.objects.get(pk=part)
                queryset = queryset.filter(id__in=[p.id for p in part.purchase_orders()])
            except (Part.DoesNotExist, ValueError):
                pass

        # Attempt to filter by supplier part
        supplier_part = params.get('supplier_part', None)

        if supplier_part is not None:
            try:
                supplier_part = SupplierPart.objects.get(pk=supplier_part)
                queryset = queryset.filter(id__in=[p.id for p in supplier_part.purchase_orders()])
            except (ValueError, SupplierPart.DoesNotExist):
                pass

        # Filter by 'date range'
        min_date = params.get('min_date', None)
        max_date = params.get('max_date', None)

        if min_date is not None and max_date is not None:
            queryset = models.PurchaseOrder.filterByDate(queryset, min_date, max_date)

        return queryset

    filter_backends = [
        rest_filters.DjangoFilterBackend,
        filters.SearchFilter,
        InvenTreeOrderingFilter,
    ]

    ordering_field_aliases = {
        'reference': ['reference_int', 'reference'],
    }

    search_fields = [
        'reference',
        'supplier__name',
        'supplier_reference',
        'description',
    ]

    ordering_fields = [
        'creation_date',
        'reference',
        'supplier__name',
        'target_date',
        'line_items',
        'status',
    ]

    ordering = '-creation_date'


class PODetail(generics.RetrieveUpdateDestroyAPIView):
    """ API endpoint for detail view of a PurchaseOrder object """

    queryset = models.PurchaseOrder.objects.all()
    serializer_class = serializers.POSerializer

    def get_serializer(self, *args, **kwargs):

        try:
            kwargs['supplier_detail'] = str2bool(self.request.query_params.get('supplier_detail', False))
        except AttributeError:
            pass

        # Ensure the request context is passed through
        kwargs['context'] = self.get_serializer_context()

        return self.serializer_class(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):

        queryset = super().get_queryset(*args, **kwargs)

        queryset = queryset.prefetch_related(
            'supplier',
            'lines',
        )

        queryset = serializers.POSerializer.annotate_queryset(queryset)

        return queryset


class POReceive(generics.CreateAPIView):
    """
    API endpoint to receive stock items against a purchase order.

    - The purchase order is specified in the URL.
    - Items to receive are specified as a list called "items" with the following options:
        - supplier_part: pk value of the supplier part
        - quantity: quantity to receive
        - status: stock item status
        - location: destination for stock item (optional)
    - A global location can also be specified
    """

    queryset = models.PurchaseOrderLineItem.objects.none()

    serializer_class = serializers.POReceiveSerializer

    def get_serializer_context(self):

        context = super().get_serializer_context()

        # Pass the purchase order through to the serializer for validation
        try:
            context['order'] = models.PurchaseOrder.objects.get(pk=self.kwargs.get('pk', None))
        except:
            pass

        context['request'] = self.request

        return context


class POLineItemFilter(rest_filters.FilterSet):
    """
    Custom filters for the POLineItemList endpoint
    """

    class Meta:
        model = models.PurchaseOrderLineItem
        fields = [
            'order',
            'part',
        ]

    pending = rest_filters.BooleanFilter(label='pending', method='filter_pending')

    def filter_pending(self, queryset, name, value):
        """
        Filter by "pending" status (order status = pending)
        """

        value = str2bool(value)

        if value:
            queryset = queryset.filter(order__status__in=PurchaseOrderStatus.OPEN)
        else:
            queryset = queryset.exclude(order__status__in=PurchaseOrderStatus.OPEN)

        return queryset

    order_status = rest_filters.NumberFilter(label='order_status', field_name='order__status')

    received = rest_filters.BooleanFilter(label='received', method='filter_received')

    def filter_received(self, queryset, name, value):
        """
        Filter by lines which are "received" (or "not" received)

        A line is considered "received" when received >= quantity
        """

        value = str2bool(value)

        q = Q(received__gte=F('quantity'))

        if value:
            queryset = queryset.filter(q)
        else:
            # Only count "pending" orders
            queryset = queryset.exclude(q).filter(order__status__in=PurchaseOrderStatus.OPEN)

        return queryset


class POLineItemList(generics.ListCreateAPIView):
    """ API endpoint for accessing a list of POLineItem objects

    - GET: Return a list of PO Line Item objects
    - POST: Create a new PurchaseOrderLineItem object
    """

    queryset = models.PurchaseOrderLineItem.objects.all()
    serializer_class = serializers.POLineItemSerializer
    filterset_class = POLineItemFilter

    def get_queryset(self, *args, **kwargs):

        queryset = super().get_queryset(*args, **kwargs)

        queryset = serializers.POLineItemSerializer.annotate_queryset(queryset)

        return queryset

    def get_serializer(self, *args, **kwargs):

        try:
            kwargs['part_detail'] = str2bool(self.request.query_params.get('part_detail', False))
            kwargs['order_detail'] = str2bool(self.request.query_params.get('order_detail', False))
        except AttributeError:
            pass

        kwargs['context'] = self.get_serializer_context()

        return self.serializer_class(*args, **kwargs)

    def filter_queryset(self, queryset):
        """
        Additional filtering options
        """

        params = self.request.query_params

        queryset = super().filter_queryset(queryset)

        base_part = params.get('base_part', None)

        if base_part:
            try:
                base_part = Part.objects.get(pk=base_part)

                queryset = queryset.filter(part__part=base_part)

            except (ValueError, Part.DoesNotExist):
                pass

        return queryset

    def list(self, request, *args, **kwargs):

        queryset = self.filter_queryset(self.get_queryset())

        # Check if we wish to export the queried data to a file
        export_format = request.query_params.get('export', None)

        if export_format:
            export_format = str(export_format).strip().lower()

            if export_format in ['csv', 'tsv', 'xls', 'xlsx']:
                dataset = POLineItemResource().export(queryset=queryset)

                filedata = dataset.export(export_format)

                filename = f"InvenTree_PurchaseOrderData.{export_format}"

                return DownloadFile(filedata, filename)

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    filter_backends = [
        rest_filters.DjangoFilterBackend,
        filters.SearchFilter,
        InvenTreeOrderingFilter
    ]

    ordering_field_aliases = {
        'MPN': 'part__manufacturer_part__MPN',
        'SKU': 'part__SKU',
        'part_name': 'part__part__name',
    }

    ordering_fields = [
        'MPN',
        'part_name',
        'purchase_price',
        'quantity',
        'received',
        'reference',
        'SKU',
        'total_price',
        'target_date',
    ]

    search_fields = [
        'part__part__name',
        'part__part__description',
        'part__MPN',
        'part__SKU',
        'reference',
    ]


class POLineItemDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Detail API endpoint for PurchaseOrderLineItem object
    """

    queryset = models.PurchaseOrderLineItem.objects.all()
    serializer_class = serializers.POLineItemSerializer

    def get_queryset(self):

        queryset = super().get_queryset()

        queryset = serializers.POLineItemSerializer.annotate_queryset(queryset)

        return queryset


class SOAttachmentList(generics.ListCreateAPIView, AttachmentMixin):
    """
    API endpoint for listing (and creating) a SalesOrderAttachment (file upload)
    """

    queryset = models.SalesOrderAttachment.objects.all()
    serializer_class = serializers.SOAttachmentSerializer

    filter_backends = [
        rest_filters.DjangoFilterBackend,
    ]

    filter_fields = [
        'order',
    ]


class SOAttachmentDetail(generics.RetrieveUpdateDestroyAPIView, AttachmentMixin):
    """
    Detail endpoint for SalesOrderAttachment
    """

    queryset = models.SalesOrderAttachment.objects.all()
    serializer_class = serializers.SOAttachmentSerializer


class SOList(generics.ListCreateAPIView):
    """
    API endpoint for accessing a list of SalesOrder objects.

    - GET: Return list of SO objects (with filters)
    - POST: Create a new SalesOrder
    """

    queryset = models.SalesOrder.objects.all()
    serializer_class = serializers.SalesOrderSerializer

    def create(self, request, *args, **kwargs):
        """
        Save user information on create
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = serializer.save()
        item.created_by = request.user
        item.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_serializer(self, *args, **kwargs):

        try:
            kwargs['customer_detail'] = str2bool(self.request.query_params.get('customer_detail', False))
        except AttributeError:
            pass

        # Ensure the context is passed through to the serializer
        kwargs['context'] = self.get_serializer_context()

        return self.serializer_class(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):

        queryset = super().get_queryset(*args, **kwargs)

        queryset = queryset.prefetch_related(
            'customer',
            'lines'
        )

        queryset = serializers.SalesOrderSerializer.annotate_queryset(queryset)

        return queryset

    def filter_queryset(self, queryset):
        """
        Perform custom filtering operations on the SalesOrder queryset.
        """

        queryset = super().filter_queryset(queryset)

        params = self.request.query_params

        # Filter by 'outstanding' status
        outstanding = params.get('outstanding', None)

        if outstanding is not None:
            outstanding = str2bool(outstanding)

            if outstanding:
                queryset = queryset.filter(status__in=models.SalesOrderStatus.OPEN)
            else:
                queryset = queryset.exclude(status__in=models.SalesOrderStatus.OPEN)

        # Filter by 'overdue' status
        overdue = params.get('overdue', None)

        if overdue is not None:
            overdue = str2bool(overdue)

            if overdue:
                queryset = queryset.filter(models.SalesOrder.OVERDUE_FILTER)
            else:
                queryset = queryset.exclude(models.SalesOrder.OVERDUE_FILTER)

        status = params.get('status', None)

        if status is not None:
            queryset = queryset.filter(status=status)

        # Filter by "Part"
        # Only return SalesOrder which have LineItem referencing the part
        part = params.get('part', None)

        if part is not None:
            try:
                part = Part.objects.get(pk=part)
                queryset = queryset.filter(id__in=[so.id for so in part.sales_orders()])
            except (Part.DoesNotExist, ValueError):
                pass

        # Filter by 'date range'
        min_date = params.get('min_date', None)
        max_date = params.get('max_date', None)

        if min_date is not None and max_date is not None:
            queryset = models.SalesOrder.filterByDate(queryset, min_date, max_date)

        return queryset

    filter_backends = [
        rest_filters.DjangoFilterBackend,
        filters.SearchFilter,
        InvenTreeOrderingFilter,
    ]

    ordering_field_aliases = {
        'reference': ['reference_int', 'reference'],
    }

    filter_fields = [
        'customer',
    ]

    ordering_fields = [
        'creation_date',
        'reference',
        'customer__name',
        'customer_reference',
        'status',
        'target_date',
        'line_items',
        'shipment_date',
    ]

    search_fields = [
        'customer__name',
        'reference',
        'description',
        'customer_reference',
    ]

    ordering = '-creation_date'


class SODetail(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for detail view of a SalesOrder object.
    """

    queryset = models.SalesOrder.objects.all()
    serializer_class = serializers.SalesOrderSerializer

    def get_serializer(self, *args, **kwargs):

        try:
            kwargs['customer_detail'] = str2bool(self.request.query_params.get('customer_detail', False))
        except AttributeError:
            pass

        kwargs['context'] = self.get_serializer_context()

        return self.serializer_class(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):

        queryset = super().get_queryset(*args, **kwargs)

        queryset = queryset.prefetch_related('customer', 'lines')

        queryset = serializers.SalesOrderSerializer.annotate_queryset(queryset)

        return queryset


class SOLineItemFilter(rest_filters.FilterSet):
    """
    Custom filters for SOLineItemList endpoint
    """

    class Meta:
        model = models.SalesOrderLineItem
        fields = [
            'order',
            'part',
        ]

    completed = rest_filters.BooleanFilter(label='completed', method='filter_completed')

    def filter_completed(self, queryset, name, value):
        """
        Filter by lines which are "completed"

        A line is completed when shipped >= quantity
        """

        value = str2bool(value)

        q = Q(shipped__gte=F('quantity'))

        if value:
            queryset = queryset.filter(q)
        else:
            queryset = queryset.exclude(q)

        return queryset


class SOLineItemList(generics.ListCreateAPIView):
    """
    API endpoint for accessing a list of SalesOrderLineItem objects.
    """

    queryset = models.SalesOrderLineItem.objects.all()
    serializer_class = serializers.SOLineItemSerializer
    filterset_class = SOLineItemFilter

    def get_serializer(self, *args, **kwargs):

        try:
            params = self.request.query_params

            kwargs['part_detail'] = str2bool(params.get('part_detail', False))
            kwargs['order_detail'] = str2bool(params.get('order_detail', False))
            kwargs['allocations'] = str2bool(params.get('allocations', False))
        except AttributeError:
            pass

        kwargs['context'] = self.get_serializer_context()

        return self.serializer_class(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):

        queryset = super().get_queryset(*args, **kwargs)

        queryset = queryset.prefetch_related(
            'part',
            'part__stock_items',
            'allocations',
            'allocations__item__location',
            'order',
            'order__stock_items',
        )

        return queryset

    filter_backends = [
        rest_filters.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]

    ordering_fields = [
        'part__name',
        'quantity',
        'reference',
        'target_date',
    ]

    search_fields = [
        'part__name',
        'quantity',
        'reference',
    ]

    filter_fields = [
        'order',
        'part',
    ]


class SOLineItemDetail(generics.RetrieveUpdateDestroyAPIView):
    """ API endpoint for detail view of a SalesOrderLineItem object """

    queryset = models.SalesOrderLineItem.objects.all()
    serializer_class = serializers.SOLineItemSerializer


class SalesOrderComplete(generics.CreateAPIView):
    """
    API endpoint for manually marking a SalesOrder as "complete".
    """

    queryset = models.SalesOrder.objects.all()
    serializer_class = serializers.SalesOrderCompleteSerializer

    def get_serializer_context(self):

        ctx = super().get_serializer_context()

        ctx['request'] = self.request

        try:
            ctx['order'] = models.SalesOrder.objects.get(pk=self.kwargs.get('pk', None))
        except:
            pass

        return ctx


class SalesOrderAllocateSerials(generics.CreateAPIView):
    """
    API endpoint to allocation stock items against a SalesOrder,
    by specifying serial numbers.
    """

    queryset = models.SalesOrder.objects.none()
    serializer_class = serializers.SOSerialAllocationSerializer

    def get_serializer_context(self):

        ctx = super().get_serializer_context()

        # Pass through the SalesOrder object to the serializer
        try:
            ctx['order'] = models.SalesOrder.objects.get(pk=self.kwargs.get('pk', None))
        except:
            pass

        ctx['request'] = self.request

        return ctx


class SalesOrderAllocate(generics.CreateAPIView):
    """
    API endpoint to allocate stock items against a SalesOrder

    - The SalesOrder is specified in the URL
    - See the SOShipmentAllocationSerializer class
    """

    queryset = models.SalesOrder.objects.none()
    serializer_class = serializers.SOShipmentAllocationSerializer

    def get_serializer_context(self):

        ctx = super().get_serializer_context()

        # Pass through the SalesOrder object to the serializer
        try:
            ctx['order'] = models.SalesOrder.objects.get(pk=self.kwargs.get('pk', None))
        except:
            pass

        ctx['request'] = self.request

        return ctx


class SOAllocationDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for detali view of a SalesOrderAllocation object
    """

    queryset = models.SalesOrderAllocation.objects.all()
    serializer_class = serializers.SalesOrderAllocationSerializer


class SOAllocationList(generics.ListAPIView):
    """
    API endpoint for listing SalesOrderAllocation objects
    """

    queryset = models.SalesOrderAllocation.objects.all()
    serializer_class = serializers.SalesOrderAllocationSerializer

    def get_serializer(self, *args, **kwargs):

        try:
            params = self.request.query_params

            kwargs['part_detail'] = str2bool(params.get('part_detail', False))
            kwargs['item_detail'] = str2bool(params.get('item_detail', False))
            kwargs['order_detail'] = str2bool(params.get('order_detail', False))
            kwargs['location_detail'] = str2bool(params.get('location_detail', False))
            kwargs['customer_detail'] = str2bool(params.get('customer_detail', False))
        except AttributeError:
            pass

        return self.serializer_class(*args, **kwargs)

    def filter_queryset(self, queryset):

        queryset = super().filter_queryset(queryset)

        # Filter by order
        params = self.request.query_params

        # Filter by "part" reference
        part = params.get('part', None)

        if part is not None:
            queryset = queryset.filter(item__part=part)

        # Filter by "order" reference
        order = params.get('order', None)

        if order is not None:
            queryset = queryset.filter(line__order=order)

        # Filter by "stock item"
        item = params.get('item', params.get('stock_item', None))

        if item is not None:
            queryset = queryset.filter(item=item)

        # Filter by "outstanding" order status
        outstanding = params.get('outstanding', None)

        if outstanding is not None:
            outstanding = str2bool(outstanding)

            if outstanding:
                # Filter only "open" orders
                # Filter only allocations which have *not* shipped
                queryset = queryset.filter(
                    line__order__status__in=SalesOrderStatus.OPEN,
                    shipment__shipment_date=None,
                )
            else:
                queryset = queryset.exclude(
                    line__order__status__in=SalesOrderStatus.OPEN,
                    shipment__shipment_date=None
                )

        return queryset

    filter_backends = [
        rest_filters.DjangoFilterBackend,
    ]

    # Default filterable fields
    filter_fields = [
    ]


class SOShipmentFilter(rest_filters.FilterSet):
    """
    Custom filterset for the SOShipmentList endpoint
    """

    shipped = rest_filters.BooleanFilter(label='shipped', method='filter_shipped')

    def filter_shipped(self, queryset, name, value):

        value = str2bool(value)

        if value:
            queryset = queryset.exclude(shipment_date=None)
        else:
            queryset = queryset.filter(shipment_date=None)

        return queryset

    class Meta:
        model = models.SalesOrderShipment
        fields = [
            'order',
        ]


class SOShipmentList(generics.ListCreateAPIView):
    """
    API list endpoint for SalesOrderShipment model
    """

    queryset = models.SalesOrderShipment.objects.all()
    serializer_class = serializers.SalesOrderShipmentSerializer
    filterset_class = SOShipmentFilter

    filter_backends = [
        rest_filters.DjangoFilterBackend,
    ]


class SOShipmentDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    API detail endpooint for SalesOrderShipment model
    """

    queryset = models.SalesOrderShipment.objects.all()
    serializer_class = serializers.SalesOrderShipmentSerializer


class SOShipmentComplete(generics.CreateAPIView):
    """
    API endpoint for completing (shipping) a SalesOrderShipment
    """

    queryset = models.SalesOrderShipment.objects.all()
    serializer_class = serializers.SalesOrderShipmentCompleteSerializer

    def get_serializer_context(self):
        """
        Pass the request object to the serializer
        """

        ctx = super().get_serializer_context()
        ctx['request'] = self.request

        try:
            ctx['shipment'] = models.SalesOrderShipment.objects.get(
                pk=self.kwargs.get('pk', None)
            )
        except:
            pass

        return ctx


class POAttachmentList(generics.ListCreateAPIView, AttachmentMixin):
    """
    API endpoint for listing (and creating) a PurchaseOrderAttachment (file upload)
    """

    queryset = models.PurchaseOrderAttachment.objects.all()
    serializer_class = serializers.POAttachmentSerializer

    filter_backends = [
        rest_filters.DjangoFilterBackend,
    ]

    filter_fields = [
        'order',
    ]


class POAttachmentDetail(generics.RetrieveUpdateDestroyAPIView, AttachmentMixin):
    """
    Detail endpoint for a PurchaseOrderAttachment
    """

    queryset = models.PurchaseOrderAttachment.objects.all()
    serializer_class = serializers.POAttachmentSerializer


order_api_urls = [

    # API endpoints for purchase orders
    url(r'^po/', include([

        # Purchase order attachments
        url(r'attachment/', include([
            url(r'^(?P<pk>\d+)/$', POAttachmentDetail.as_view(), name='api-po-attachment-detail'),
            url(r'^.*$', POAttachmentList.as_view(), name='api-po-attachment-list'),
        ])),

        # Individual purchase order detail URLs
        url(r'^(?P<pk>\d+)/', include([
            url(r'^receive/', POReceive.as_view(), name='api-po-receive'),
            url(r'.*$', PODetail.as_view(), name='api-po-detail'),
        ])),

        # Purchase order list
        url(r'^.*$', POList.as_view(), name='api-po-list'),
    ])),

    # API endpoints for purchase order line items
    url(r'^po-line/', include([
        url(r'^(?P<pk>\d+)/$', POLineItemDetail.as_view(), name='api-po-line-detail'),
        url(r'^.*$', POLineItemList.as_view(), name='api-po-line-list'),
    ])),

    # API endpoints for sales orders
    url(r'^so/', include([
        url(r'attachment/', include([
            url(r'^(?P<pk>\d+)/$', SOAttachmentDetail.as_view(), name='api-so-attachment-detail'),
            url(r'^.*$', SOAttachmentList.as_view(), name='api-so-attachment-list'),
        ])),

        url(r'^shipment/', include([
            url(r'^(?P<pk>\d+)/', include([
                url(r'^ship/$', SOShipmentComplete.as_view(), name='api-so-shipment-ship'),
                url(r'^.*$', SOShipmentDetail.as_view(), name='api-so-shipment-detail'),
            ])),
            url(r'^.*$', SOShipmentList.as_view(), name='api-so-shipment-list'),
        ])),

        # Sales order detail view
        url(r'^(?P<pk>\d+)/', include([
            url(r'^complete/', SalesOrderComplete.as_view(), name='api-so-complete'),
            url(r'^allocate/', SalesOrderAllocate.as_view(), name='api-so-allocate'),
            url(r'^allocate-serials/', SalesOrderAllocateSerials.as_view(), name='api-so-allocate-serials'),
            url(r'^.*$', SODetail.as_view(), name='api-so-detail'),
        ])),

        # Sales order list view
        url(r'^.*$', SOList.as_view(), name='api-so-list'),
    ])),

    # API endpoints for sales order line items
    url(r'^so-line/', include([
        url(r'^(?P<pk>\d+)/$', SOLineItemDetail.as_view(), name='api-so-line-detail'),
        url(r'^$', SOLineItemList.as_view(), name='api-so-line-list'),
    ])),

    # API endpoints for sales order allocations
    url(r'^so-allocation/', include([
        url(r'^(?P<pk>\d+)/$', SOAllocationDetail.as_view(), name='api-so-allocation-detail'),
        url(r'^.*$', SOAllocationList.as_view(), name='api-so-allocation-list'),
    ])),
]
