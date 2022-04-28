# -*- coding: utf-8 -*-
"""
Class for IntegrationPluginBase and Mixin Base
"""

import logging
import os
import inspect
from datetime import datetime
import pathlib

from django.urls.base import reverse
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

import plugin.plugin as plugin_base
from plugin.helpers import get_git_log, GitStatus


logger = logging.getLogger("inventree")


class MixinBase:
    """
    Base set of mixin functions and mechanisms
    """

    def __init__(self) -> None:
        self._mixinreg = {}
        self._mixins = {}

    def add_mixin(self, key: str, fnc_enabled=True, cls=None):
        """
        Add a mixin to the plugins registry
        """

        self._mixins[key] = fnc_enabled
        self.setup_mixin(key, cls=cls)

    def setup_mixin(self, key, cls=None):
        """
        Define mixin details for the current mixin -> provides meta details for all active mixins
        """

        # get human name
        human_name = getattr(cls.MixinMeta, 'MIXIN_NAME', key) if cls and hasattr(cls, 'MixinMeta') else key

        # register
        self._mixinreg[key] = {
            'key': key,
            'human_name': human_name,
        }

    @property
    def registered_mixins(self, with_base: bool = False):
        """
        Get all registered mixins for the plugin
        """

        mixins = getattr(self, '_mixinreg', None)
        if mixins:
            # filter out base
            if not with_base and 'base' in mixins:
                del mixins['base']
            # only return dict
            mixins = [a for a in mixins.values()]
        return mixins


class IntegrationPluginBase(MixinBase, plugin_base.InvenTreePluginBase):
    """
    The IntegrationPluginBase class is used to integrate with 3rd party software
    """

    AUTHOR = None
    DESCRIPTION = None
    PUBLISH_DATE = None
    VERSION = None
    WEBSITE = None
    LICENSE = None

    def __init__(self):
        super().__init__()
        self.add_mixin('base')
        self.def_path = inspect.getfile(self.__class__)
        self.path = os.path.dirname(self.def_path)

        self.define_package()

    @property
    def _is_package(self):
        """
        Is the plugin delivered as a package
        """
        return getattr(self, 'is_package', False)

    @property
    def is_sample(self):
        """
        Is this plugin part of the samples?
        """
        path = str(self.package_path)
        return path.startswith('plugin/samples/')

    # region properties
    @property
    def slug(self):
        """
        Slug of plugin
        """
        return self.plugin_slug()

    @property
    def name(self):
        """
        Name of plugin
        """
        return self.plugin_name()

    @property
    def human_name(self):
        """
        Human readable name of plugin
        """
        return self.plugin_title()

    @property
    def description(self):
        """
        Description of plugin
        """
        description = getattr(self, 'DESCRIPTION', None)
        if not description:
            description = self.plugin_name()
        return description

    @property
    def author(self):
        """
        Author of plugin - either from plugin settings or git
        """
        author = getattr(self, 'AUTHOR', None)
        if not author:
            author = self.package.get('author')
        if not author:
            author = _('No author found')  # pragma: no cover
        return author

    @property
    def pub_date(self):
        """
        Publishing date of plugin - either from plugin settings or git
        """
        pub_date = getattr(self, 'PUBLISH_DATE', None)
        if not pub_date:
            pub_date = self.package.get('date')
        else:
            pub_date = datetime.fromisoformat(str(pub_date))
        if not pub_date:
            pub_date = _('No date found')  # pragma: no cover
        return pub_date

    @property
    def version(self):
        """
        Version of plugin
        """
        version = getattr(self, 'VERSION', None)
        return version

    @property
    def website(self):
        """
        Website of plugin - if set else None
        """
        website = getattr(self, 'WEBSITE', None)
        return website

    @property
    def license(self):
        """
        License of plugin
        """
        lic = getattr(self, 'LICENSE', None)
        return lic
    # endregion

    @property
    def package_path(self):
        """
        Path to the plugin
        """
        if self._is_package:
            return self.__module__
        return pathlib.Path(self.def_path).relative_to(settings.BASE_DIR)

    @property
    def settings_url(self):
        """
        URL to the settings panel for this plugin
        """
        return f'{reverse("settings")}#select-plugin-{self.slug}'

    # region mixins
    def mixin(self, key):
        """
        Check if mixin is registered
        """
        return key in self._mixins

    def mixin_enabled(self, key):
        """
        Check if mixin is registered, enabled and ready
        """
        if self.mixin(key):
            fnc_name = self._mixins.get(key)

            # Allow for simple case where the mixin is "always" ready
            if fnc_name is True:
                return True

            return getattr(self, fnc_name, True)
        return False
    # endregion

    # region package info
    def _get_package_commit(self):
        """
        Get last git commit for the plugin
        """
        return get_git_log(self.def_path)

    def _get_package_metadata(self):
        """
        Get package metadata for plugin
        """
        return {}  # pragma: no cover  # TODO add usage for package metadata

    def define_package(self):
        """
        Add package info of the plugin into plugins context
        """
        package = self._get_package_metadata() if self._is_package else self._get_package_commit()

        # process date
        if package.get('date'):
            package['date'] = datetime.fromisoformat(package.get('date'))

        # process sign state
        sign_state = getattr(GitStatus, str(package.get('verified')), GitStatus.N)
        if sign_state.status == 0:
            self.sign_color = 'success'  # pragma: no cover
        elif sign_state.status == 1:
            self.sign_color = 'warning'
        else:
            self.sign_color = 'danger'  # pragma: no cover

        # set variables
        self.package = package
        self.sign_state = sign_state
    # endregion
