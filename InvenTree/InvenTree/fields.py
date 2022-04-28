""" Custom fields used in InvenTree """

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import sys

from .validators import allowable_url_schemes

from django.utils.translation import ugettext_lazy as _

from django.forms.fields import URLField as FormURLField
from django.db import models as models
from django.core import validators
from django import forms

from decimal import Decimal

from djmoney.models.fields import MoneyField as ModelMoneyField
from djmoney.forms.fields import MoneyField
from djmoney.models.validators import MinMoneyValidator

import InvenTree.helpers


class InvenTreeURLFormField(FormURLField):
    """ Custom URL form field with custom scheme validators """

    default_validators = [validators.URLValidator(schemes=allowable_url_schemes())]


class InvenTreeURLField(models.URLField):
    """ Custom URL field which has custom scheme validators """

    default_validators = [validators.URLValidator(schemes=allowable_url_schemes())]

    def formfield(self, **kwargs):
        return super().formfield(**{
            'form_class': InvenTreeURLFormField
        })


def money_kwargs():
    """ returns the database settings for MoneyFields """
    from common.settings import currency_code_mappings, currency_code_default

    kwargs = {}
    kwargs['currency_choices'] = currency_code_mappings()
    kwargs['default_currency'] = currency_code_default()
    return kwargs


class InvenTreeModelMoneyField(ModelMoneyField):
    """
    Custom MoneyField for clean migrations while using dynamic currency settings
    """

    def __init__(self, **kwargs):
        # detect if creating migration
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            # remove currency information for a clean migration
            kwargs['default_currency'] = ''
            kwargs['currency_choices'] = []
        else:
            # set defaults
            kwargs.update(money_kwargs())

        # Set a minimum value validator
        validators = kwargs.get('validators', [])

        if len(validators) == 0:
            validators.append(
                MinMoneyValidator(0),
            )

        kwargs['validators'] = validators

        super().__init__(**kwargs)

    def formfield(self, **kwargs):
        """ override form class to use own function """
        kwargs['form_class'] = InvenTreeMoneyField
        return super().formfield(**kwargs)


class InvenTreeMoneyField(MoneyField):
    """ custom MoneyField for clean migrations while using dynamic currency settings """
    def __init__(self, *args, **kwargs):
        # override initial values with the real info from database
        kwargs.update(money_kwargs())
        super().__init__(*args, **kwargs)


class DatePickerFormField(forms.DateField):
    """
    Custom date-picker field
    """

    def __init__(self, **kwargs):

        help_text = kwargs.get('help_text', _('Enter date'))
        label = kwargs.get('label', None)
        required = kwargs.get('required', False)
        initial = kwargs.get('initial', None)

        widget = forms.DateInput(
            attrs={
                'type': 'date',
            }
        )

        forms.DateField.__init__(
            self,
            required=required,
            initial=initial,
            help_text=help_text,
            widget=widget,
            label=label
        )


def round_decimal(value, places):
    """
    Round value to the specified number of places.
    """

    if value is not None:
        # see https://docs.python.org/2/library/decimal.html#decimal.Decimal.quantize for options
        return value.quantize(Decimal(10) ** -places)
    return value


class RoundingDecimalFormField(forms.DecimalField):
    def to_python(self, value):
        value = super(RoundingDecimalFormField, self).to_python(value)
        value = round_decimal(value, self.decimal_places)
        return value

    def prepare_value(self, value):
        """
        Override the 'prepare_value' method, to remove trailing zeros when displaying.
        Why? It looks nice!
        """

        if type(value) == Decimal:
            return InvenTree.helpers.normalize(value)
        else:
            return value


class RoundingDecimalField(models.DecimalField):
    def to_python(self, value):
        value = super(RoundingDecimalField, self).to_python(value)
        return round_decimal(value, self.decimal_places)

    def formfield(self, **kwargs):
        defaults = {
            'form_class': RoundingDecimalFormField
        }

        defaults.update(kwargs)

        return super().formfield(**kwargs)
