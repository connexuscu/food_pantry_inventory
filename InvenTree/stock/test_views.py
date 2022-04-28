""" Unit tests for Stock views (see views.py) """

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

# from common.models import InvenTreeSetting


class StockViewTestCase(TestCase):

    fixtures = [
        'category',
        'part',
        'company',
        'location',
        'supplier_part',
        'stock',
    ]

    def setUp(self):
        super().setUp()

        # Create a user
        user = get_user_model()

        self.user = user.objects.create_user(
            username='username',
            email='user@email.com',
            password='password'
        )

        self.user.is_staff = True
        self.user.save()

        # Put the user into a group with the correct permissions
        group = Group.objects.create(name='mygroup')
        self.user.groups.add(group)

        # Give the group *all* the permissions!
        for rule in group.rule_sets.all():
            rule.can_view = True
            rule.can_change = True
            rule.can_add = True
            rule.can_delete = True

            rule.save()

        self.client.login(username='username', password='password')


class StockListTest(StockViewTestCase):
    """ Tests for Stock list views """

    def test_stock_index(self):
        response = self.client.get(reverse('stock-index'))
        self.assertEqual(response.status_code, 200)


class StockOwnershipTest(StockViewTestCase):
    """ Tests for stock ownership views """

    def setUp(self):
        """ Add another user for ownership tests """

    """
    TODO: Refactor this following test to use the new API form

        super().setUp()

        # Promote existing user with staff, admin and superuser statuses
        self.user.is_staff = True
        self.user.is_admin = True
        self.user.is_superuser = True
        self.user.save()

        # Create a new user
        user = get_user_model()

        self.new_user = user.objects.create_user(
            username='john',
            email='john@email.com',
            password='custom123',
        )

        # Put the user into a new group with the correct permissions
        group = Group.objects.create(name='new_group')
        self.new_user.groups.add(group)

        # Give the group *all* the permissions!
        for rule in group.rule_sets.all():
            rule.can_view = True
            rule.can_change = True
            rule.can_add = True
            rule.can_delete = True

            rule.save()

    def enable_ownership(self):
        # Enable stock location ownership

        InvenTreeSetting.set_setting('STOCK_OWNERSHIP_CONTROL', True, self.user)
        self.assertEqual(True, InvenTreeSetting.get_setting('STOCK_OWNERSHIP_CONTROL'))

    def test_owner_control(self):
        # Test stock location and item ownership
        from .models import StockLocation
        from users.models import Owner

        new_user_group = self.new_user.groups.all()[0]
        new_user_group_owner = Owner.get_owner(new_user_group)

        user_as_owner = Owner.get_owner(self.user)
        new_user_as_owner = Owner.get_owner(self.new_user)

        # Enable ownership control
        self.enable_ownership()

        test_location_id = 4
        test_item_id = 11
        # Set ownership on existing item (and change location)
        response = self.client.post(reverse('stock-item-edit', args=(test_item_id,)),
                                    {'part': 1, 'status': StockStatus.OK, 'owner': user_as_owner.pk},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertContains(response, '"form_valid": true', status_code=200)


        # Logout
        self.client.logout()

        # Login with new user
        self.client.login(username='john', password='custom123')

        # TODO: Refactor this following test to use the new API form
        # Test item edit
        response = self.client.post(reverse('stock-item-edit', args=(test_item_id,)),
                                    {'part': 1, 'status': StockStatus.OK, 'owner': new_user_as_owner.pk},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        # Make sure the item's owner is unchanged
        item = StockItem.objects.get(pk=test_item_id)
        self.assertEqual(item.owner, user_as_owner)

        # Create new parent location
        parent_location = {
            'name': 'John Desk',
            'description': 'John\'s desk',
            'owner': new_user_group_owner.pk,
        }

        # Retrieve created location
        location_created = StockLocation.objects.get(name=new_location['name'])

        # Create new item
        new_item = {
            'part': 25,
            'location': location_created.pk,
            'quantity': 123,
            'status': StockStatus.OK,
        }

        # Try to create new item with no owner
        response = self.client.post(reverse('stock-item-create'),
                                    new_item, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, '"form_valid": false', status_code=200)

        # Try to create new item with invalid owner
        new_item['owner'] = user_as_owner.pk
        response = self.client.post(reverse('stock-item-create'),
                                    new_item, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, '"form_valid": false', status_code=200)

        # Try to create new item with valid owner
        new_item['owner'] = new_user_as_owner.pk
        response = self.client.post(reverse('stock-item-create'),
                                    new_item, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response, '"form_valid": true', status_code=200)

        # Logout
        self.client.logout()
    """
