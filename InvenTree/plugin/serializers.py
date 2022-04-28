"""
JSON serializers for plugin app
"""

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import subprocess

from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from rest_framework import serializers

from plugin.models import PluginConfig, PluginSetting
from common.serializers import SettingsSerializer


class PluginConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for a PluginConfig:
    """

    meta = serializers.DictField(read_only=True)
    mixins = serializers.DictField(read_only=True)

    class Meta:
        model = PluginConfig
        fields = [
            'key',
            'name',
            'active',
            'meta',
            'mixins',
        ]


class PluginConfigInstallSerializer(serializers.Serializer):
    """
    Serializer for installing a new plugin
    """

    url = serializers.CharField(
        required=False,
        allow_blank=True,
        label=_('Source URL'),
        help_text=_('Source for the package - this can be a custom registry or a VCS path')
    )
    packagename = serializers.CharField(
        required=False,
        allow_blank=True,
        label=_('Package Name'),
        help_text=_('Name for the Plugin Package - can also contain a version indicator'),
    )
    confirm = serializers.BooleanField(
        label=_('Confirm plugin installation'),
        help_text=_('This will install this plugin now into the current instance. The instance will go into maintenance.')
    )

    class Meta:
        fields = [
            'url',
            'packagename',
            'confirm',
        ]

    def validate(self, data):
        super().validate(data)

        # check the base requirements are met
        if not data.get('confirm'):
            raise ValidationError({'confirm': _('Installation not confirmed')})
        if (not data.get('url')) and (not data.get('packagename')):
            msg = _('Either packagename of URL must be provided')
            raise ValidationError({'url': msg, 'packagename': msg})

        return data

    def save(self):
        data = self.validated_data

        packagename = data.get('packagename', '')
        url = data.get('url', '')

        # build up the command
        install_name = []

        if url:
            # use custom registration / VCS
            if True in [identifier in url for identifier in ['git+https', 'hg+https', 'svn+svn', ]]:
                # using a VCS provider
                if packagename:
                    install_name.append(f'{packagename}@{url}')
                else:
                    install_name.append(url)
            else:
                # using a custom package repositories
                install_name.append('-i')
                install_name.append(url)
                install_name.append(packagename)

        elif packagename:
            # use pypi
            install_name.append(packagename)

        command = 'python -m pip install'.split()
        command.extend(install_name)
        ret = {'command': ' '.join(command)}
        success = False
        # execute pypi
        try:
            result = subprocess.check_output(command, cwd=os.path.dirname(settings.BASE_DIR))
            ret['result'] = str(result, 'utf-8')
            ret['success'] = True
            success = True
        except subprocess.CalledProcessError as error:  # pragma: no cover
            ret['result'] = str(error.output, 'utf-8')
            ret['error'] = True

        # save plugin to plugin_file if installed successfull
        if success:
            with open(settings.PLUGIN_FILE, "a") as plugin_file:
                plugin_file.write(f'{" ".join(install_name)}  # Installed {timezone.now()} by {str(self.context["request"].user)}\n')

        return ret


class PluginSettingSerializer(SettingsSerializer):
    """
    Serializer for the PluginSetting model
    """

    plugin = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PluginSetting
        fields = [
            'pk',
            'key',
            'value',
            'name',
            'description',
            'type',
            'choices',
            'plugin',
        ]
