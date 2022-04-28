"""
Main JSON interface views
"""

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.http import JsonResponse

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import AjaxView
from .version import inventreeVersion, inventreeApiVersion, inventreeInstanceName
from .status import is_worker_running

from plugin import registry


class InfoView(AjaxView):
    """ Simple JSON endpoint for InvenTree information.
    Use to confirm that the server is running, etc.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):

        data = {
            'server': 'InvenTree',
            'version': inventreeVersion(),
            'instance': inventreeInstanceName(),
            'apiVersion': inventreeApiVersion(),
            'worker_running': is_worker_running(),
            'plugins_enabled': settings.PLUGINS_ENABLED,
        }

        return JsonResponse(data)


class NotFoundView(AjaxView):
    """
    Simple JSON view when accessing an invalid API view.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):

        data = {
            'details': _('API endpoint not found'),
            'url': request.build_absolute_uri(),
        }

        return JsonResponse(data, status=404)


class AttachmentMixin:
    """
    Mixin for creating attachment objects,
    and ensuring the user information is saved correctly.
    """

    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]

    def perform_create(self, serializer):
        """ Save the user information when a file is uploaded """

        attachment = serializer.save()
        attachment.user = self.request.user
        attachment.save()


class ActionPluginView(APIView):
    """
    Endpoint for running custom action plugins.
    """

    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def post(self, request, *args, **kwargs):

        action = request.data.get('action', None)

        data = request.data.get('data', None)

        if action is None:
            return Response({
                'error': _("No action specified")
            })

        action_plugins = registry.with_mixin('action')
        for plugin in action_plugins:
            if plugin.action_name() == action:
                # TODO @matmair use easier syntax once InvenTree 0.7.0 is released
                plugin.init(request.user, data=data)

                plugin.perform_action()

                return Response(plugin.get_response())

        # If we got to here, no matching action was found
        return Response({
            'error': _("No matching action found"),
            "action": action,
        })
