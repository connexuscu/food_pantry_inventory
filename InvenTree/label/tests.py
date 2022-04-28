# Tests for labels

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os

from django.test import TestCase
from django.conf import settings
from django.apps import apps
from django.core.exceptions import ValidationError

from InvenTree.helpers import validateFilterString

from .models import StockItemLabel, StockLocationLabel
from stock.models import StockItem


class LabelTest(TestCase):

    def setUp(self) -> None:
        # ensure the labels were created
        apps.get_app_config('label').create_labels()

    def test_default_labels(self):
        """
        Test that the default label templates are copied across
        """

        labels = StockItemLabel.objects.all()

        self.assertTrue(labels.count() > 0)

        labels = StockLocationLabel.objects.all()

        self.assertTrue(labels.count() > 0)

    def test_default_files(self):
        """
        Test that label files exist in the MEDIA directory
        """

        item_dir = os.path.join(
            settings.MEDIA_ROOT,
            'label',
            'inventree',
            'stockitem',
        )

        files = os.listdir(item_dir)

        self.assertTrue(len(files) > 0)

        loc_dir = os.path.join(
            settings.MEDIA_ROOT,
            'label',
            'inventree',
            'stocklocation',
        )

        files = os.listdir(loc_dir)

        self.assertTrue(len(files) > 0)

    def test_filters(self):
        """
        Test the label filters
        """

        filter_string = "part__pk=10"

        filters = validateFilterString(filter_string, model=StockItem)

        self.assertEqual(type(filters), dict)

        bad_filter_string = "part_pk=10"

        with self.assertRaises(ValidationError):
            validateFilterString(bad_filter_string, model=StockItem)
