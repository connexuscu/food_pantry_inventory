# -*- coding: utf-8 -*-

import logging

from django.apps import AppConfig


logger = logging.getLogger('inventree')


class CommonConfig(AppConfig):
    name = 'common'

    def ready(self):

        self.clear_restart_flag()

    def clear_restart_flag(self):
        """
        Clear the SERVER_RESTART_REQUIRED setting
        """

        try:
            import common.models

            if common.models.InvenTreeSetting.get_setting('SERVER_RESTART_REQUIRED', backup_value=False, create=False):
                logger.info("Clearing SERVER_RESTART_REQUIRED flag")
                common.models.InvenTreeSetting.set_setting('SERVER_RESTART_REQUIRED', False, None)
        except:
            pass
