# -*- coding: utf-8 -*-

from rest_framework import serializers
from django.contrib.auth.models import User

from .models import Owner

from InvenTree.serializers import InvenTreeModelSerializer


class UserSerializer(InvenTreeModelSerializer):
    """ Serializer for a User
    """

    class Meta:
        model = User
        fields = ('pk',
                  'username',
                  'first_name',
                  'last_name',
                  'email',)


class OwnerSerializer(InvenTreeModelSerializer):
    """
    Serializer for an "Owner" (either a "user" or a "group")
    """

    name = serializers.CharField(read_only=True)

    label = serializers.CharField(read_only=True)

    class Meta:
        model = Owner
        fields = [
            'pk',
            'owner_id',
            'name',
            'label',
        ]
