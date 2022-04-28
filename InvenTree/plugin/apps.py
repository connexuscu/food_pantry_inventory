# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from maintenance_mode.core import set_maintenance_mode

from InvenTree.ready import isImportingData
from plugin import registry
from plugin.helpers import check_git_version, log_error


logger = logging.getLogger('inventree')


class PluginAppConfig(AppConfig):
    name = 'plugin'

    def ready(self):
        if settings.PLUGINS_ENABLED:

            if isImportingData():  # pragma: no cover
                logger.info('Skipping plugin loading for data import')
            else:
                logger.info('Loading InvenTree plugins')

                if not registry.is_loading:
                    # this is the first startup
                    try:
                        from common.models import InvenTreeSetting
                        if InvenTreeSetting.get_setting('PLUGIN_ON_STARTUP', create=False):
                            # make sure all plugins are installed
                            registry.install_plugin_file()
                    except:
                        pass

                    # get plugins and init them
                    registry.collect_plugins()
                    registry.load_plugins()

                    # drop out of maintenance
                    # makes sure we did not have an error in reloading and maintenance is still active
                    set_maintenance_mode(False)

            # check git version
            registry.git_is_modern = check_git_version()
            if not registry.git_is_modern:  # pragma: no cover  # simulating old git seems not worth it for coverage
                log_error(_('Your enviroment has an outdated git version. This prevents InvenTree from loading plugin details.'), 'load')
