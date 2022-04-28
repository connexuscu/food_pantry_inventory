# Tests for labels

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.urls import reverse

from InvenTree.api_tester import InvenTreeAPITestCase


class TestReportTests(InvenTreeAPITestCase):
    """
    Tests for the StockItem TestReport templates
    """

    fixtures = [
        'category',
        'part',
        'location',
        'stock',
    ]

    roles = [
        'stock.view',
        'stock_location.view',
    ]

    list_url = reverse('api-stockitem-testreport-list')

    def setUp(self):

        super().setUp()

    def do_list(self, filters={}):

        response = self.client.get(self.list_url, filters, format='json')

        self.assertEqual(response.status_code, 200)

        return response.data

    def test_list(self):

        response = self.do_list()

        # TODO - Add some report templates to the fixtures
        self.assertEqual(len(response), 0)

        # TODO - Add some tests to this response
        response = self.do_list(
            {
                'item': 10,
            }
        )

        # TODO - Add some tests to this response
        response = self.do_list(
            {
                'item': 100000,
            }
        )

        # TODO - Add some tests to this response
        response = self.do_list(
            {
                'items': [10, 11, 12],
            }
        )


class TestLabels(InvenTreeAPITestCase):
    """
    Tests for the label APIs
    """

    fixtures = [
        'category',
        'part',
        'location',
        'stock',
    ]

    roles = [
        'stock.view',
        'stock_location.view',
    ]

    def do_list(self, filters={}):

        response = self.client.get(self.list_url, filters, format='json')

        self.assertEqual(response.status_code, 200)

        return response.data

    def test_lists(self):
        self.list_url = reverse('api-stockitem-label-list')
        self.do_list()

        self.list_url = reverse('api-stocklocation-label-list')
        self.do_list()

        self.list_url = reverse('api-part-label-list')
        self.do_list()
