"""
Django Forms for interacting with Stock app
"""

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms
from django.forms.utils import ErrorDict
from django.utils.translation import ugettext_lazy as _

from mptt.fields import TreeNodeChoiceField

from InvenTree.forms import HelperForm
from InvenTree.fields import RoundingDecimalFormField
from InvenTree.fields import DatePickerFormField

from .models import StockLocation, StockItem, StockItemTracking


class ReturnStockItemForm(HelperForm):
    """
    Form for manually returning a StockItem into stock

    TODO: This could be a simple API driven form!
    """

    class Meta:
        model = StockItem
        fields = [
            'location',
        ]


class EditStockLocationForm(HelperForm):
    """
    Form for editing a StockLocation

    TODO: Migrate this form to the modern API forms interface
    """

    class Meta:
        model = StockLocation
        fields = [
            'name',
            'parent',
            'description',
            'owner',
        ]


class ConvertStockItemForm(HelperForm):
    """
    Form for converting a StockItem to a variant of its current part.

    TODO: Migrate this form to the modern API forms interface
    """

    class Meta:
        model = StockItem
        fields = [
            'part'
        ]


class CreateStockItemForm(HelperForm):
    """
    Form for creating a new StockItem

    TODO: Migrate this form to the modern API forms interface
    """

    expiry_date = DatePickerFormField(
        label=_('Expiry Date'),
        help_text=_('Expiration date for this stock item'),
    )

    serial_numbers = forms.CharField(label=_('Serial Numbers'), required=False, help_text=_('Enter unique serial numbers (or leave blank)'))

    def __init__(self, *args, **kwargs):

        self.field_prefix = {
            'serial_numbers': 'fa-hashtag',
            'link': 'fa-link',
        }

        super().__init__(*args, **kwargs)

    class Meta:
        model = StockItem
        fields = [
            'part',
            'supplier_part',
            'location',
            'quantity',
            'batch',
            'serial_numbers',
            'packaging',
            'purchase_price',
            'expiry_date',
            'link',
            'delete_on_deplete',
            'status',
            'owner',
        ]

    # Custom clean to prevent complex StockItem.clean() logic from running (yet)
    def full_clean(self):
        self._errors = ErrorDict()

        if not self.is_bound:  # Stop further processing.
            return

        self.cleaned_data = {}

        # If the form is permitted to be empty, and none of the form data has
        # changed from the initial data, short circuit any validation.
        if self.empty_permitted and not self.has_changed():
            return

        # Don't run _post_clean() as this will run StockItem.clean()
        self._clean_fields()
        self._clean_form()


class SerializeStockForm(HelperForm):
    """
    Form for serializing a StockItem.

    TODO: Migrate this form to the modern API forms interface
    """

    destination = TreeNodeChoiceField(queryset=StockLocation.objects.all(), label=_('Destination'), required=True, help_text=_('Destination for serialized stock (by default, will remain in current location)'))

    serial_numbers = forms.CharField(label=_('Serial numbers'), required=True, help_text=_('Unique serial numbers (must match quantity)'))

    note = forms.CharField(label=_('Notes'), required=False, help_text=_('Add transaction note (optional)'))

    quantity = RoundingDecimalFormField(max_digits=10, decimal_places=5, label=_('Quantity'))

    def __init__(self, *args, **kwargs):

        # Extract the stock item
        item = kwargs.pop('item', None)

        if item:
            self.field_placeholder['serial_numbers'] = item.part.getSerialNumberString(item.quantity)

        super().__init__(*args, **kwargs)

    class Meta:
        model = StockItem

        fields = [
            'quantity',
            'serial_numbers',
            'destination',
            'note',
        ]


class UninstallStockForm(forms.ModelForm):
    """
    Form for uninstalling a stock item which is installed in another item.

    TODO: Migrate this form to the modern API forms interface
    """

    location = TreeNodeChoiceField(queryset=StockLocation.objects.all(), label=_('Location'), help_text=_('Destination location for uninstalled items'))

    note = forms.CharField(label=_('Notes'), required=False, help_text=_('Add transaction note (optional)'))

    confirm = forms.BooleanField(required=False, initial=False, label=_('Confirm uninstall'), help_text=_('Confirm removal of installed stock items'))

    class Meta:

        model = StockItem

        fields = [
            'location',
            'note',
            'confirm',
        ]


class EditStockItemForm(HelperForm):
    """ Form for editing a StockItem object.
    Note that not all fields can be edited here (even if they can be specified during creation.

    location - Must be updated in a 'move' transaction
    quantity - Must be updated in a 'stocktake' transaction
    part - Cannot be edited after creation

    TODO: Migrate this form to the modern API forms interface
    """

    expiry_date = DatePickerFormField(
        label=_('Expiry Date'),
        help_text=_('Expiration date for this stock item'),
    )

    class Meta:
        model = StockItem

        fields = [
            'supplier_part',
            'serial',
            'batch',
            'status',
            'expiry_date',
            'purchase_price',
            'packaging',
            'link',
            'delete_on_deplete',
            'owner',
        ]


class TrackingEntryForm(HelperForm):
    """
    Form for creating / editing a StockItemTracking object.

    Note: 2021-05-11 - This form is not currently used - should delete?
    """

    class Meta:
        model = StockItemTracking

        fields = [
            'notes',
        ]
