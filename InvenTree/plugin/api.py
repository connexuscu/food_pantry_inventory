"""
JSON API for the plugin app
"""

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url, include

from rest_framework import generics
from rest_framework import status
from rest_framework import permissions
from rest_framework.response import Response

from common.api import GlobalSettingsPermissions
from plugin.models import PluginConfig, PluginSetting
import plugin.serializers as PluginSerializers


class PluginList(generics.ListAPIView):
    """ API endpoint for list of PluginConfig objects

    - GET: Return a list of all PluginConfig objects
    """

    # Allow any logged in user to read this endpoint
    # This is necessary to allow certain functionality,
    # e.g. determining which label printing plugins are available
    permission_classes = [permissions.IsAuthenticated]

    serializer_class = PluginSerializers.PluginConfigSerializer
    queryset = PluginConfig.objects.all()

    ordering_fields = [
        'key',
        'name',
        'active',
    ]

    ordering = [
        'key',
    ]

    search_fields = [
        'key',
        'name',
    ]


class PluginDetail(generics.RetrieveUpdateDestroyAPIView):
    """ API detail endpoint for PluginConfig object

    get:
    Return a single PluginConfig object

    post:
    Update a PluginConfig

    delete:
    Remove a PluginConfig
    """

    queryset = PluginConfig.objects.all()
    serializer_class = PluginSerializers.PluginConfigSerializer


class PluginInstall(generics.CreateAPIView):
    """
    Endpoint for installing a new plugin
    """
    queryset = PluginConfig.objects.none()
    serializer_class = PluginSerializers.PluginConfigInstallSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = self.perform_create(serializer)
        result['input'] = serializer.data
        headers = self.get_success_headers(serializer.data)
        return Response(result, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        return serializer.save()


class PluginSettingList(generics.ListAPIView):
    """
    List endpoint for all plugin related settings.

    - read only
    - only accessible by staff users
    """

    queryset = PluginSetting.objects.all()
    serializer_class = PluginSerializers.PluginSettingSerializer

    permission_classes = [
        GlobalSettingsPermissions,
    ]


class PluginSettingDetail(generics.RetrieveUpdateAPIView):
    """
    Detail endpoint for a plugin-specific setting.

    Note that these cannot be created or deleted via the API
    """

    queryset = PluginSetting.objects.all()
    serializer_class = PluginSerializers.PluginSettingSerializer

    # Staff permission required
    permission_classes = [
        GlobalSettingsPermissions,
    ]


plugin_api_urls = [

    # Plugin settings URLs
    url(r'^settings/', include([
        url(r'^(?P<pk>\d+)/', PluginSettingDetail.as_view(), name='api-plugin-setting-detail'),
        url(r'^.*$', PluginSettingList.as_view(), name='api-plugin-setting-list'),
    ])),

    # Detail views for a single PluginConfig item
    url(r'^(?P<pk>\d+)/', include([
        url(r'^.*$', PluginDetail.as_view(), name='api-plugin-detail'),
    ])),

    url(r'^install/', PluginInstall.as_view(), name='api-plugin-install'),

    # Anything else
    url(r'^.*$', PluginList.as_view(), name='api-plugin-list'),
]
