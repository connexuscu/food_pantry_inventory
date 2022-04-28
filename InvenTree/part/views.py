"""
Django views for interacting with Part app
"""

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.shortcuts import get_object_or_404
from django.shortcuts import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.views.generic import DetailView, ListView
from django.forms import HiddenInput
from django.conf import settings
from django.contrib import messages

from djmoney.contrib.exchange.models import convert_money
from djmoney.contrib.exchange.exceptions import MissingRate

from PIL import Image

import requests
import os
import io

from decimal import Decimal

from .models import PartCategory, Part
from .models import PartParameterTemplate
from .models import PartCategoryParameterTemplate

from common.models import InvenTreeSetting
from company.models import SupplierPart
from common.files import FileManager
from common.views import FileManagementFormView, FileManagementAjaxView

from stock.models import StockItem, StockLocation

import common.settings as inventree_settings

from . import forms as part_forms
from . import settings as part_settings
from .bom import MakeBomTemplate, ExportBom, IsValidBOMFormat
from order.models import PurchaseOrderLineItem

from InvenTree.views import AjaxView, AjaxCreateView, AjaxUpdateView, AjaxDeleteView
from InvenTree.views import QRCodeView
from InvenTree.views import InvenTreeRoleMixin

from InvenTree.helpers import str2bool


class PartIndex(InvenTreeRoleMixin, ListView):
    """ View for displaying list of Part objects
    """

    model = Part
    template_name = 'part/category.html'
    context_object_name = 'parts'

    def get_queryset(self):
        return Part.objects.all().select_related('category')

    def get_context_data(self, **kwargs):

        context = super(PartIndex, self).get_context_data(**kwargs).copy()

        # View top-level categories
        children = PartCategory.objects.filter(parent=None)

        context['children'] = children
        context['category_count'] = PartCategory.objects.count()
        context['part_count'] = Part.objects.count()

        return context


class PartSetCategory(AjaxUpdateView):
    """ View for settings the part category for multiple parts at once """

    ajax_template_name = 'part/set_category.html'
    ajax_form_title = _('Set Part Category')
    form_class = part_forms.SetPartCategoryForm

    role_required = 'part.change'

    category = None
    parts = []

    def get(self, request, *args, **kwargs):
        """ Respond to a GET request to this view """

        self.request = request

        if 'parts[]' in request.GET:
            self.parts = Part.objects.filter(id__in=request.GET.getlist('parts[]'))
        else:
            self.parts = []

        return self.renderJsonResponse(request, form=self.get_form(), context=self.get_context_data())

    def post(self, request, *args, **kwargs):
        """ Respond to a POST request to this view """

        self.parts = []

        for item in request.POST:
            if item.startswith('part_id_'):
                pk = item.replace('part_id_', '')

                try:
                    part = Part.objects.get(pk=pk)
                except (Part.DoesNotExist, ValueError):
                    continue

                self.parts.append(part)

        self.category = None

        if 'part_category' in request.POST:
            pk = request.POST['part_category']

            try:
                self.category = PartCategory.objects.get(pk=pk)
            except (PartCategory.DoesNotExist, ValueError):
                self.category = None

        valid = self.category is not None

        data = {
            'form_valid': valid,
            'success': _('Set category for {n} parts').format(n=len(self.parts))
        }

        if valid:
            self.set_category()

        return self.renderJsonResponse(request, data=data, form=self.get_form(), context=self.get_context_data())

    @transaction.atomic
    def set_category(self):
        for part in self.parts:
            part.set_category(self.category)

    def get_context_data(self):
        """ Return context data for rendering in the form """
        ctx = {}

        ctx['parts'] = self.parts
        ctx['categories'] = PartCategory.objects.all()
        ctx['category'] = self.category

        return ctx


class PartImport(FileManagementFormView):
    ''' Part: Upload file, match to fields and import parts(using multi-Step form) '''
    permission_required = 'part.add'

    class PartFileManager(FileManager):
        REQUIRED_HEADERS = [
            'Name',
            'Description',
        ]

        OPTIONAL_MATCH_HEADERS = [
            'Category',
            'default_location',
            'default_supplier',
            'variant_of',
        ]

        OPTIONAL_HEADERS = [
            'Keywords',
            'IPN',
            'Revision',
            'Link',
            'default_expiry',
            'minimum_stock',
            'Units',
            'Notes',
            'Active',
            'base_cost',
            'Multiple',
            'Assembly',
            'Component',
            'is_template',
            'Purchaseable',
            'Salable',
            'Trackable',
            'Virtual',
            'Stock',
        ]

    name = 'part'
    form_steps_template = [
        'part/import_wizard/part_upload.html',
        'part/import_wizard/match_fields.html',
        'part/import_wizard/match_references.html',
    ]
    form_steps_description = [
        _("Upload File"),
        _("Match Fields"),
        _("Match References"),
    ]

    form_field_map = {
        'name': 'name',
        'description': 'description',
        'keywords': 'keywords',
        'ipn': 'ipn',
        'revision': 'revision',
        'link': 'link',
        'default_expiry': 'default_expiry',
        'minimum_stock': 'minimum_stock',
        'units': 'units',
        'notes': 'notes',
        'category': 'category',
        'default_location': 'default_location',
        'default_supplier': 'default_supplier',
        'variant_of': 'variant_of',
        'active': 'active',
        'base_cost': 'base_cost',
        'multiple': 'multiple',
        'assembly': 'assembly',
        'component': 'component',
        'is_template': 'is_template',
        'purchaseable': 'purchaseable',
        'salable': 'salable',
        'trackable': 'trackable',
        'virtual': 'virtual',
        'stock': 'stock',
    }
    file_manager_class = PartFileManager

    def get_field_selection(self):
        """ Fill the form fields for step 3 """
        # fetch available elements
        self.allowed_items = {}
        self.matches = {}

        self.allowed_items['Category'] = PartCategory.objects.all()
        self.matches['Category'] = ['name__contains']
        self.allowed_items['default_location'] = StockLocation.objects.all()
        self.matches['default_location'] = ['name__contains']
        self.allowed_items['default_supplier'] = SupplierPart.objects.all()
        self.matches['default_supplier'] = ['SKU__contains']
        self.allowed_items['variant_of'] = Part.objects.all()
        self.matches['variant_of'] = ['name__contains']

        # setup
        self.file_manager.setup()
        # collect submitted column indexes
        col_ids = {}
        for col in self.file_manager.HEADERS:
            index = self.get_column_index(col)
            if index >= 0:
                col_ids[col] = index

        # parse all rows
        for row in self.rows:
            # check each submitted column
            for idx in col_ids:
                data = row['data'][col_ids[idx]]['cell']

                if idx in self.file_manager.OPTIONAL_MATCH_HEADERS:
                    try:
                        exact_match = self.allowed_items[idx].get(**{a: data for a in self.matches[idx]})
                    except (ValueError, self.allowed_items[idx].model.DoesNotExist, self.allowed_items[idx].model.MultipleObjectsReturned):
                        exact_match = None

                    row['match_options_' + idx] = self.allowed_items[idx]
                    row['match_' + idx] = exact_match
                    continue

                # general fields
                row[idx.lower()] = data

    def done(self, form_list, **kwargs):
        """ Create items """
        items = self.get_clean_items()

        import_done = 0
        import_error = []

        # Create Part instances
        for part_data in items.values():

            # set related parts
            optional_matches = {}
            for idx in self.file_manager.OPTIONAL_MATCH_HEADERS:
                if idx.lower() in part_data:
                    try:
                        optional_matches[idx] = self.allowed_items[idx].get(pk=int(part_data[idx.lower()]))
                    except (ValueError, self.allowed_items[idx].model.DoesNotExist, self.allowed_items[idx].model.MultipleObjectsReturned):
                        optional_matches[idx] = None
                else:
                    optional_matches[idx] = None

            # add part
            new_part = Part(
                name=part_data.get('name', ''),
                description=part_data.get('description', ''),
                keywords=part_data.get('keywords', None),
                IPN=part_data.get('ipn', None),
                revision=part_data.get('revision', None),
                link=part_data.get('link', None),
                default_expiry=part_data.get('default_expiry', 0),
                minimum_stock=part_data.get('minimum_stock', 0),
                units=part_data.get('units', None),
                notes=part_data.get('notes', None),
                category=optional_matches['Category'],
                default_location=optional_matches['default_location'],
                default_supplier=optional_matches['default_supplier'],
                variant_of=optional_matches['variant_of'],
                active=str2bool(part_data.get('active', True)),
                base_cost=part_data.get('base_cost', 0),
                multiple=part_data.get('multiple', 1),
                assembly=str2bool(part_data.get('assembly', part_settings.part_assembly_default())),
                component=str2bool(part_data.get('component', part_settings.part_component_default())),
                is_template=str2bool(part_data.get('is_template', part_settings.part_template_default())),
                purchaseable=str2bool(part_data.get('purchaseable', part_settings.part_purchaseable_default())),
                salable=str2bool(part_data.get('salable', part_settings.part_salable_default())),
                trackable=str2bool(part_data.get('trackable', part_settings.part_trackable_default())),
                virtual=str2bool(part_data.get('virtual', part_settings.part_virtual_default())),
            )
            try:
                new_part.save()

                # add stock item if set
                if part_data.get('stock', None):
                    stock = StockItem(
                        part=new_part,
                        location=new_part.default_location,
                        quantity=int(part_data.get('stock', 1)),
                    )
                    stock.save()
                import_done += 1
            except ValidationError as _e:
                import_error.append(', '.join(set(_e.messages)))

        # Set alerts
        if import_done:
            alert = f"<strong>{_('Part-Import')}</strong><br>{_('Imported {n} parts').format(n=import_done)}"
            messages.success(self.request, alert)
        if import_error:
            error_text = '\n'.join([f'<li><strong>x{import_error.count(a)}</strong>: {a}</li>' for a in set(import_error)])
            messages.error(self.request, f"<strong>{_('Some errors occured:')}</strong><br><ul>{error_text}</ul>")

        return HttpResponseRedirect(reverse('part-index'))


class PartImportAjax(FileManagementAjaxView, PartImport):
    ajax_form_steps_template = [
        'part/import_wizard/ajax_part_upload.html',
        'part/import_wizard/ajax_match_fields.html',
        'part/import_wizard/ajax_match_references.html',
    ]

    def validate(self, obj, form, **kwargs):
        return PartImport.validate(self, self.steps.current, form, **kwargs)


class PartDetail(InvenTreeRoleMixin, DetailView):
    """ Detail view for Part object
    """

    context_object_name = 'part'
    queryset = Part.objects.all().select_related('category')
    template_name = 'part/detail.html'
    form_class = part_forms.PartPriceForm

    # Add in some extra context information based on query params
    def get_context_data(self, **kwargs):
        """
        Provide extra context data to template
        """
        context = super().get_context_data(**kwargs)

        part = self.get_object()

        ctx = part.get_context_data(self.request)

        context.update(**ctx)

        show_price_history = InvenTreeSetting.get_setting('PART_SHOW_PRICE_HISTORY', False)

        context['show_price_history'] = show_price_history

        # Pricing information
        if show_price_history:
            ctx = self.get_pricing(self.get_quantity())
            ctx['form'] = self.form_class(initial=self.get_initials())

            context.update(ctx)

        return context

    def get_quantity(self):
        """ Return set quantity in decimal format """
        return Decimal(self.request.POST.get('quantity', 1))

    def get_part(self):
        return self.get_object()

    def get_pricing(self, quantity=1, currency=None):
        """ returns context with pricing information """
        ctx = PartPricing.get_pricing(self, quantity, currency)
        part = self.get_part()
        default_currency = inventree_settings.currency_code_default()

        # Stock history
        if part.total_stock > 1:
            price_history = []
            stock = part.stock_entries(include_variants=False, in_stock=True).\
                order_by('purchase_order__issue_date').prefetch_related('purchase_order', 'supplier_part')

            for stock_item in stock:
                if None in [stock_item.purchase_price, stock_item.quantity]:
                    continue

                # convert purchase price to current currency - only one currency in the graph
                try:
                    price = convert_money(stock_item.purchase_price, default_currency)
                except MissingRate:
                    continue

                line = {
                    'price': price.amount,
                    'qty': stock_item.quantity
                }
                # Supplier Part Name  # TODO use in graph
                if stock_item.supplier_part:
                    line['name'] = stock_item.supplier_part.pretty_name

                    if stock_item.supplier_part.unit_pricing and price:
                        line['price_diff'] = price.amount - stock_item.supplier_part.unit_pricing
                        line['price_part'] = stock_item.supplier_part.unit_pricing

                # set date for graph labels
                if stock_item.purchase_order and stock_item.purchase_order.issue_date:
                    line['date'] = stock_item.purchase_order.issue_date.isoformat()
                elif stock_item.tracking_info.count() > 0:
                    line['date'] = stock_item.tracking_info.first().date.date().isoformat()
                else:
                    # Not enough information
                    continue

                price_history.append(line)

            ctx['price_history'] = price_history

        # BOM Information for Pie-Chart
        if part.has_bom:
            # get internal price setting
            use_internal = InvenTreeSetting.get_setting('PART_BOM_USE_INTERNAL_PRICE', False)
            ctx_bom_parts = []
            # iterate over all bom-items
            for item in part.bom_items.all():
                ctx_item = {'name': str(item.sub_part)}
                price, qty = item.sub_part.get_price_range(quantity, internal=use_internal), item.quantity

                price_min, price_max = 0, 0
                if price:  # check if price available
                    price_min = str((price[0] * qty) / quantity)
                    if len(set(price)) == 2:  # min and max-price present
                        price_max = str((price[1] * qty) / quantity)
                        ctx['bom_pie_max'] = True  # enable showing max prices in bom

                ctx_item['max_price'] = price_min
                ctx_item['min_price'] = price_max if price_max else price_min
                ctx_bom_parts.append(ctx_item)

            # add to global context
            ctx['bom_parts'] = ctx_bom_parts

        # Sale price history
        sale_items = PurchaseOrderLineItem.objects.filter(part__part=part).order_by('order__issue_date').\
            prefetch_related('order', ).all()

        if sale_items:
            sale_history = []

            for sale_item in sale_items:
                # check for not fully defined elements
                if None in [sale_item.purchase_price, sale_item.quantity]:
                    continue

                try:
                    price = convert_money(sale_item.purchase_price, default_currency)
                except MissingRate:
                    continue

                line = {
                    'price': price.amount if price else 0,
                    'qty': sale_item.quantity,
                }

                # set date for graph labels
                if sale_item.order.issue_date:
                    line['date'] = sale_item.order.issue_date.isoformat()
                elif sale_item.order.creation_date:
                    line['date'] = sale_item.order.creation_date.isoformat()
                else:
                    line['date'] = _('None')

                sale_history.append(line)

            ctx['sale_history'] = sale_history

        return ctx

    def get_initials(self):
        """ returns initials for form """
        return {'quantity': self.get_quantity()}

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        kwargs['object'] = self.object
        ctx = self.get_context_data(**kwargs)
        return self.get(request, context=ctx)


class PartDetailFromIPN(PartDetail):
    slug_field = 'IPN'
    slug_url_kwarg = 'slug'

    def get_object(self):
        """ Return Part object which IPN field matches the slug value """
        queryset = self.get_queryset()
        # Get slug
        slug = self.kwargs.get(self.slug_url_kwarg)

        if slug is not None:
            slug_field = self.get_slug_field()
            # Filter by the slug value
            queryset = queryset.filter(**{slug_field: slug})

            try:
                # Get unique part from queryset
                part = queryset.get()
                # Return Part object
                return part
            except queryset.model.MultipleObjectsReturned:
                pass
            except queryset.model.DoesNotExist:
                pass

        return None

    def get(self, request, *args, **kwargs):
        """ Attempt to match slug to a Part, else redirect to PartIndex view """
        self.object = self.get_object()

        if not self.object:
            return HttpResponseRedirect(reverse('part-index'))

        return super(PartDetailFromIPN, self).get(request, *args, **kwargs)


class PartQRCode(QRCodeView):
    """ View for displaying a QR code for a Part object """

    ajax_form_title = _("Part QR Code")

    role_required = 'part.view'

    def get_qr_data(self):
        """ Generate QR code data for the Part """

        try:
            part = Part.objects.get(id=self.pk)
            return part.format_barcode()
        except Part.DoesNotExist:
            return None


class PartImageDownloadFromURL(AjaxUpdateView):
    """
    View for downloading an image from a provided URL
    """

    model = Part

    ajax_template_name = 'image_download.html'
    form_class = part_forms.PartImageDownloadForm
    ajax_form_title = _('Download Image')

    def validate(self, part, form):
        """
        Validate that the image data are correct.

        - Try to download the image!
        """

        # First ensure that the normal validation routines pass
        if not form.is_valid():
            return

        # We can now extract a valid URL from the form data
        url = form.cleaned_data.get('url', None)

        # Download the file
        response = requests.get(url, stream=True)

        # Look at response header, reject if too large
        content_length = response.headers.get('Content-Length', '0')

        try:
            content_length = int(content_length)
        except (ValueError):
            # If we cannot extract meaningful length, just assume it's "small enough"
            content_length = 0

        # TODO: Factor this out into a configurable setting
        MAX_IMG_LENGTH = 10 * 1024 * 1024

        if content_length > MAX_IMG_LENGTH:
            form.add_error('url', _('Image size exceeds maximum allowable size for download'))
            return

        self.response = response

        # Check for valid response code
        if not response.status_code == 200:
            form.add_error('url', _('Invalid response: {code}').format(code=response.status_code))
            return

        response.raw.decode_content = True

        try:
            self.image = Image.open(response.raw).convert()
            self.image.verify()
        except:
            form.add_error('url', _("Supplied URL is not a valid image file"))
            return

    def save(self, part, form, **kwargs):
        """
        Save the downloaded image to the part
        """

        fmt = self.image.format

        if not fmt:
            fmt = 'PNG'

        buffer = io.BytesIO()

        self.image.save(buffer, format=fmt)

        # Construct a simplified name for the image
        filename = f"part_{part.pk}_image.{fmt.lower()}"

        part.image.save(
            filename,
            ContentFile(buffer.getvalue()),
        )


class PartImageSelect(AjaxUpdateView):
    """ View for selecting Part image from existing images. """

    model = Part
    ajax_template_name = 'part/select_image.html'
    ajax_form_title = _('Select Part Image')

    fields = [
        'image',
    ]

    def post(self, request, *args, **kwargs):

        part = self.get_object()
        form = self.get_form()

        img = request.POST.get('image', '')

        img = os.path.basename(img)

        data = {}

        if img:
            img_path = os.path.join(settings.MEDIA_ROOT, 'part_images', img)

            # Ensure that the image already exists
            if os.path.exists(img_path):

                part.image = os.path.join('part_images', img)
                part.save()

                data['success'] = _('Updated part image')

        if 'success' not in data:
            data['error'] = _('Part image not found')

        return self.renderJsonResponse(request, form, data)


class BomUpload(InvenTreeRoleMixin, DetailView):
    """ View for uploading a BOM file, and handling BOM data importing. """

    context_object_name = 'part'
    queryset = Part.objects.all()
    template_name = 'part/upload_bom.html'


class BomUploadTemplate(AjaxView):
    """
    Provide a BOM upload template file for download.
    - Generates a template file in the provided format e.g. ?format=csv
    """

    def get(self, request, *args, **kwargs):

        export_format = request.GET.get('format', 'csv')

        return MakeBomTemplate(export_format)


class BomDownload(AjaxView):
    """
    Provide raw download of a BOM file.
    - File format should be passed as a query param e.g. ?format=csv
    """

    role_required = 'part.view'

    model = Part

    def get(self, request, *args, **kwargs):

        part = get_object_or_404(Part, pk=self.kwargs['pk'])

        export_format = request.GET.get('format', 'csv')

        cascade = str2bool(request.GET.get('cascade', False))

        parameter_data = str2bool(request.GET.get('parameter_data', False))

        stock_data = str2bool(request.GET.get('stock_data', False))

        supplier_data = str2bool(request.GET.get('supplier_data', False))

        manufacturer_data = str2bool(request.GET.get('manufacturer_data', False))

        levels = request.GET.get('levels', None)

        if levels is not None:
            try:
                levels = int(levels)

                if levels <= 0:
                    levels = None

            except ValueError:
                levels = None

        if not IsValidBOMFormat(export_format):
            export_format = 'csv'

        return ExportBom(part,
                         fmt=export_format,
                         cascade=cascade,
                         max_levels=levels,
                         parameter_data=parameter_data,
                         stock_data=stock_data,
                         supplier_data=supplier_data,
                         manufacturer_data=manufacturer_data,
                         )

    def get_data(self):
        return {
            'info': 'Exported BOM'
        }


class PartDelete(AjaxDeleteView):
    """ View to delete a Part object """

    model = Part
    ajax_template_name = 'part/partial_delete.html'
    ajax_form_title = _('Confirm Part Deletion')
    context_object_name = 'part'

    success_url = '/part/'

    def get_data(self):
        return {
            'danger': _('Part was deleted'),
        }


class PartPricing(AjaxView):
    """ View for inspecting part pricing information """

    model = Part
    ajax_template_name = "part/part_pricing.html"
    ajax_form_title = _("Part Pricing")
    form_class = part_forms.PartPriceForm

    role_required = ['sales_order.view', 'part.view']

    def get_quantity(self):
        """ Return set quantity in decimal format """
        return Decimal(self.request.POST.get('quantity', 1))

    def get_part(self):
        try:
            return Part.objects.get(id=self.kwargs['pk'])
        except Part.DoesNotExist:
            return None

    def get_pricing(self, quantity=1, currency=None):
        """ returns context with pricing information """
        if quantity <= 0:
            quantity = 1

        # TODO - Capacity for price comparison in different currencies
        currency = None

        # Currency scaler
        scaler = Decimal(1.0)

        part = self.get_part()

        ctx = {
            'part': part,
            'quantity': quantity,
            'currency': currency,
        }

        if part is None:
            return ctx

        # Supplier pricing information
        if part.supplier_count > 0:
            buy_price = part.get_supplier_price_range(quantity)

            if buy_price is not None:
                min_buy_price, max_buy_price = buy_price

                min_buy_price /= scaler
                max_buy_price /= scaler

                min_unit_buy_price = round(min_buy_price / quantity, 3)
                max_unit_buy_price = round(max_buy_price / quantity, 3)

                min_buy_price = round(min_buy_price, 3)
                max_buy_price = round(max_buy_price, 3)

                if min_buy_price:
                    ctx['min_total_buy_price'] = min_buy_price
                    ctx['min_unit_buy_price'] = min_unit_buy_price

                if max_buy_price:
                    ctx['max_total_buy_price'] = max_buy_price
                    ctx['max_unit_buy_price'] = max_unit_buy_price

        # BOM pricing information
        if part.bom_count > 0:

            use_internal = InvenTreeSetting.get_setting('PART_BOM_USE_INTERNAL_PRICE', False)
            bom_price = part.get_bom_price_range(quantity, internal=use_internal)
            purchase_price = part.get_bom_price_range(quantity, purchase=True)

            if bom_price is not None:
                min_bom_price, max_bom_price = bom_price

                min_bom_price /= scaler
                max_bom_price /= scaler

                if min_bom_price:
                    ctx['min_total_bom_price'] = round(min_bom_price, 3)
                    ctx['min_unit_bom_price'] = round(min_bom_price / quantity, 3)

                if max_bom_price:
                    ctx['max_total_bom_price'] = round(max_bom_price, 3)
                    ctx['max_unit_bom_price'] = round(max_bom_price / quantity, 3)

            if purchase_price is not None:
                min_bom_purchase_price, max_bom_purchase_price = purchase_price

                min_bom_purchase_price /= scaler
                max_bom_purchase_price /= scaler
                if min_bom_purchase_price:
                    ctx['min_total_bom_purchase_price'] = round(min_bom_purchase_price, 3)
                    ctx['min_unit_bom_purchase_price'] = round(min_bom_purchase_price / quantity, 3)

                if max_bom_purchase_price:
                    ctx['max_total_bom_purchase_price'] = round(max_bom_purchase_price, 3)
                    ctx['max_unit_bom_purchase_price'] = round(max_bom_purchase_price / quantity, 3)

        # internal part pricing information
        internal_part_price = part.get_internal_price(quantity)
        if internal_part_price is not None:
            ctx['total_internal_part_price'] = round(internal_part_price, 3)
            ctx['unit_internal_part_price'] = round(internal_part_price / quantity, 3)

        # part pricing information
        part_price = part.get_price(quantity)
        if part_price is not None:
            ctx['total_part_price'] = round(part_price, 3)
            ctx['unit_part_price'] = round(part_price / quantity, 3)

        return ctx

    def get_initials(self):
        """ returns initials for form """
        return {'quantity': self.get_quantity()}

    def get(self, request, *args, **kwargs):
        init = self.get_initials()
        qty = self.get_quantity()
        return self.renderJsonResponse(request, self.form_class(initial=init), context=self.get_pricing(qty))

    def post(self, request, *args, **kwargs):

        currency = None

        quantity = self.get_quantity()

        # Retain quantity value set by user
        form = self.form_class(initial=self.get_initials())

        # TODO - How to handle pricing in different currencies?
        currency = None

        # check if data is set
        try:
            data = self.data
        except AttributeError:
            data = {}

        # Always mark the form as 'invalid' (the user may wish to keep getting pricing data)
        data['form_valid'] = False

        return self.renderJsonResponse(request, form, data=data, context=self.get_pricing(quantity, currency))


class PartParameterTemplateCreate(AjaxCreateView):
    """
    View for creating a new PartParameterTemplate
    """

    model = PartParameterTemplate
    form_class = part_forms.EditPartParameterTemplateForm
    ajax_form_title = _('Create Part Parameter Template')


class PartParameterTemplateEdit(AjaxUpdateView):
    """
    View for editing a PartParameterTemplate
    """

    model = PartParameterTemplate
    form_class = part_forms.EditPartParameterTemplateForm
    ajax_form_title = _('Edit Part Parameter Template')


class PartParameterTemplateDelete(AjaxDeleteView):
    """ View for deleting an existing PartParameterTemplate """

    model = PartParameterTemplate
    ajax_form_title = _("Delete Part Parameter Template")


class CategoryDetail(InvenTreeRoleMixin, DetailView):
    """ Detail view for PartCategory """

    model = PartCategory
    context_object_name = 'category'
    queryset = PartCategory.objects.all().prefetch_related('children')
    template_name = 'part/category.html'

    def get_context_data(self, **kwargs):

        context = super(CategoryDetail, self).get_context_data(**kwargs).copy()

        try:
            context['part_count'] = kwargs['object'].partcount()
        except KeyError:
            context['part_count'] = 0

        # Get current category
        category = kwargs.get('object', None)

        if category:

            # Insert "starred" information
            context['starred'] = category.is_starred_by(self.request.user)
            context['starred_directly'] = context['starred'] and category.is_starred_by(
                self.request.user,
                include_parents=False,
            )

        return context


class CategoryEdit(AjaxUpdateView):
    """
    Update view to edit a PartCategory
    """

    model = PartCategory
    form_class = part_forms.EditCategoryForm
    ajax_template_name = 'modal_form.html'
    ajax_form_title = _('Edit Part Category')

    def get_context_data(self, **kwargs):
        context = super(CategoryEdit, self).get_context_data(**kwargs).copy()

        try:
            context['category'] = self.get_object()
        except:
            pass

        return context

    def get_form(self):
        """ Customize form data for PartCategory editing.

        Limit the choices for 'parent' field to those which make sense
        """

        form = super(AjaxUpdateView, self).get_form()

        category = self.get_object()

        # Remove any invalid choices for the parent category part
        parent_choices = PartCategory.objects.all()
        parent_choices = parent_choices.exclude(id__in=category.getUniqueChildren())

        form.fields['parent'].queryset = parent_choices

        return form


class CategoryDelete(AjaxDeleteView):
    """
    Delete view to delete a PartCategory
    """

    model = PartCategory
    ajax_template_name = 'part/category_delete.html'
    ajax_form_title = _('Delete Part Category')
    context_object_name = 'category'
    success_url = '/part/'

    def get_data(self):
        return {
            'danger': _('Part category was deleted'),
        }


class CategoryParameterTemplateCreate(AjaxCreateView):
    """ View for creating a new PartCategoryParameterTemplate """

    model = PartCategoryParameterTemplate
    form_class = part_forms.EditCategoryParameterTemplateForm
    ajax_form_title = _('Create Category Parameter Template')

    def get_initial(self):
        """ Get initial data for Category """
        initials = super().get_initial()

        category_id = self.kwargs.get('pk', None)

        if category_id:
            try:
                initials['category'] = PartCategory.objects.get(pk=category_id)
            except (PartCategory.DoesNotExist, ValueError):
                pass

        return initials

    def get_form(self):
        """ Create a form to upload a new CategoryParameterTemplate
        - Hide the 'category' field (parent part)
        - Display parameter templates which are not yet related
        """

        form = super(AjaxCreateView, self).get_form()

        form.fields['category'].widget = HiddenInput()

        if form.is_valid():
            form.cleaned_data['category'] = self.kwargs.get('pk', None)

        try:
            # Get selected category
            category = self.get_initial()['category']

            # Get existing parameter templates
            parameters = [template.parameter_template.pk
                          for template in category.get_parameter_templates()]

            # Exclude templates already linked to category
            updated_choices = []
            for choice in form.fields["parameter_template"].choices:
                if (choice[0] not in parameters):
                    updated_choices.append(choice)

            # Update choices for parameter templates
            form.fields['parameter_template'].choices = updated_choices
        except KeyError:
            pass

        return form

    def post(self, request, *args, **kwargs):
        """ Capture the POST request

        - If the add_to_all_categories object is set, link parameter template to
          all categories
        - If the add_to_same_level_categories object is set, link parameter template to
          same level categories
        """

        form = self.get_form()

        valid = form.is_valid()

        if valid:
            add_to_same_level_categories = form.cleaned_data['add_to_same_level_categories']
            add_to_all_categories = form.cleaned_data['add_to_all_categories']

            selected_category = PartCategory.objects.get(pk=int(self.kwargs['pk']))
            parameter_template = form.cleaned_data['parameter_template']
            default_value = form.cleaned_data['default_value']

            categories = PartCategory.objects.all()

            if add_to_same_level_categories and not add_to_all_categories:
                # Get level
                level = selected_category.level
                # Filter same level categories
                categories = categories.filter(level=level)

            if add_to_same_level_categories or add_to_all_categories:
                # Add parameter template and default value to categories
                for category in categories:
                    # Skip selected category (will be processed in the post call)
                    if category.pk != selected_category.pk:
                        try:
                            cat_template = PartCategoryParameterTemplate.objects.create(category=category,
                                                                                        parameter_template=parameter_template,
                                                                                        default_value=default_value)
                            cat_template.save()
                        except IntegrityError:
                            # Parameter template is already linked to category
                            pass

        return super().post(request, *args, **kwargs)


class CategoryParameterTemplateEdit(AjaxUpdateView):
    """ View for editing a PartCategoryParameterTemplate """

    model = PartCategoryParameterTemplate
    form_class = part_forms.EditCategoryParameterTemplateForm
    ajax_form_title = _('Edit Category Parameter Template')

    def get_object(self):
        try:
            self.object = self.model.objects.get(pk=self.kwargs['pid'])
        except:
            return None

        return self.object

    def get_form(self):
        """ Create a form to upload a new CategoryParameterTemplate
        - Hide the 'category' field (parent part)
        - Display parameter templates which are not yet related
        """

        form = super(AjaxUpdateView, self).get_form()

        form.fields['category'].widget = HiddenInput()
        form.fields['add_to_all_categories'].widget = HiddenInput()
        form.fields['add_to_same_level_categories'].widget = HiddenInput()

        if form.is_valid():
            form.cleaned_data['category'] = self.kwargs.get('pk', None)

        try:
            # Get selected category
            category = PartCategory.objects.get(pk=self.kwargs.get('pk', None))
            # Get selected template
            selected_template = self.get_object().parameter_template

            # Get existing parameter templates
            parameters = [template.parameter_template.pk
                          for template in category.get_parameter_templates()
                          if template.parameter_template.pk != selected_template.pk]

            # Exclude templates already linked to category
            updated_choices = []
            for choice in form.fields["parameter_template"].choices:
                if (choice[0] not in parameters):
                    updated_choices.append(choice)

            # Update choices for parameter templates
            form.fields['parameter_template'].choices = updated_choices
            # Set initial choice to current template
            form.fields['parameter_template'].initial = selected_template
        except KeyError:
            pass

        return form


class CategoryParameterTemplateDelete(AjaxDeleteView):
    """ View for deleting an existing PartCategoryParameterTemplate """

    model = PartCategoryParameterTemplate
    ajax_form_title = _("Delete Category Parameter Template")

    def get_object(self):
        try:
            self.object = self.model.objects.get(pk=self.kwargs['pid'])
        except:
            return None

        return self.object
