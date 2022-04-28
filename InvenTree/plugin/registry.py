"""
Registry for loading and managing multiple plugins at run-time

- Holds the class and the object that contains all code to maintain plugin states
- Manages setup and teardown of plugin class instances
"""

import importlib
import pathlib
import logging
import os
import subprocess

from typing import OrderedDict
from importlib import reload

from django.apps import apps
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError, IntegrityError
from django.conf.urls import url, include
from django.urls import clear_url_caches
from django.contrib import admin
from django.utils.text import slugify

try:
    from importlib import metadata
except:  # pragma: no cover
    import importlib_metadata as metadata
    # TODO remove when python minimum is 3.8

from maintenance_mode.core import maintenance_mode_on
from maintenance_mode.core import get_maintenance_mode, set_maintenance_mode

from .integration import IntegrationPluginBase
from .helpers import handle_error, log_error, get_plugins, IntegrationPluginError


logger = logging.getLogger('inventree')


class PluginsRegistry:
    """
    The PluginsRegistry class
    """

    def __init__(self) -> None:
        # plugin registry
        self.plugins = {}
        self.plugins_inactive = {}

        self.plugin_modules = []         # Holds all discovered plugins

        self.errors = {}                 # Holds discovering errors

        # flags
        self.is_loading = False
        self.apps_loading = True        # Marks if apps were reloaded yet
        self.git_is_modern = True       # Is a modern version of git available

        # integration specific
        self.installed_apps = []         # Holds all added plugin_paths

        # mixins
        self.mixins_settings = {}

    def call_plugin_function(self, slug, func, *args, **kwargs):
        """
        Call a member function (named by 'func') of the plugin named by 'slug'.

        As this is intended to be run by the background worker,
        we do not perform any try/except here.

        Instead, any error messages are returned to the worker.
        """

        plugin = self.plugins[slug]

        plugin_func = getattr(plugin, func)

        return plugin_func(*args, **kwargs)

    # region public functions
    # region loading / unloading
    def load_plugins(self):
        """
        Load and activate all IntegrationPlugins
        """
        if not settings.PLUGINS_ENABLED:
            # Plugins not enabled, do nothing
            return  # pragma: no cover

        logger.info('Start loading plugins')

        # Set maintanace mode
        _maintenance = bool(get_maintenance_mode())
        if not _maintenance:
            set_maintenance_mode(True)

        registered_successful = False
        blocked_plugin = None
        retry_counter = settings.PLUGIN_RETRY

        while not registered_successful:
            try:
                # We are using the db so for migrations etc we need to try this block
                self._init_plugins(blocked_plugin)
                self._activate_plugins()
                registered_successful = True
            except (OperationalError, ProgrammingError):  # pragma: no cover
                # Exception if the database has not been migrated yet
                logger.info('Database not accessible while loading plugins')
                break
            except IntegrationPluginError as error:
                logger.error(f'[PLUGIN] Encountered an error with {error.path}:\n{error.message}')
                log_error({error.path: error.message}, 'load')
                blocked_plugin = error.path  # we will not try to load this app again

                # Initialize apps without any integration plugins
                self._clean_registry()
                self._clean_installed_apps()
                self._activate_plugins(force_reload=True)

                # We do not want to end in an endless loop
                retry_counter -= 1

                if retry_counter <= 0:  # pragma: no cover
                    if settings.PLUGIN_TESTING:
                        print('[PLUGIN] Max retries, breaking loading')
                    # TODO error for server status
                    break
                if settings.PLUGIN_TESTING:
                    print(f'[PLUGIN] Above error occured during testing - {retry_counter}/{settings.PLUGIN_RETRY} retries left')

                # now the loading will re-start up with init

        # Remove maintenance mode
        if not _maintenance:
            set_maintenance_mode(False)

        logger.info('Finished loading plugins')

    def unload_plugins(self):
        """
        Unload and deactivate all IntegrationPlugins
        """

        if not settings.PLUGINS_ENABLED:
            # Plugins not enabled, do nothing
            return  # pragma: no cover

        logger.info('Start unloading plugins')

        # Set maintanace mode
        _maintenance = bool(get_maintenance_mode())
        if not _maintenance:
            set_maintenance_mode(True)  # pragma: no cover

        # remove all plugins from registry
        self._clean_registry()

        # deactivate all integrations
        self._deactivate_plugins()

        # remove maintenance
        if not _maintenance:
            set_maintenance_mode(False)  # pragma: no cover
        logger.info('Finished unloading plugins')

    def reload_plugins(self):
        """
        Safely reload IntegrationPlugins
        """

        # Do not reload whe currently loading
        if self.is_loading:
            return  # pragma: no cover

        logger.info('Start reloading plugins')

        with maintenance_mode_on():
            self.unload_plugins()
            self.load_plugins()

        logger.info('Finished reloading plugins')

    def collect_plugins(self):
        """
        Collect integration plugins from all possible ways of loading
        """

        if not settings.PLUGINS_ENABLED:
            # Plugins not enabled, do nothing
            return  # pragma: no cover

        self.plugin_modules = []  # clear

        # Collect plugins from paths
        for plugin in settings.PLUGIN_DIRS:
            modules = get_plugins(importlib.import_module(plugin), IntegrationPluginBase)
            if modules:
                [self.plugin_modules.append(item) for item in modules]

        # Check if not running in testing mode and apps should be loaded from hooks
        if (not settings.PLUGIN_TESTING) or (settings.PLUGIN_TESTING and settings.PLUGIN_TESTING_SETUP):
            # Collect plugins from setup entry points
            for entry in metadata.entry_points().get('inventree_plugins', []):  # pragma: no cover
                try:
                    plugin = entry.load()
                    plugin.is_package = True
                    self.plugin_modules.append(plugin)
                except Exception as error:
                    handle_error(error, do_raise=False, log_name='discovery')

        # Log collected plugins
        logger.info(f'Collected {len(self.plugin_modules)} plugins!')
        logger.info(", ".join([a.__module__ for a in self.plugin_modules]))

    def install_plugin_file(self):
        """
        Make sure all plugins are installed in the current enviroment
        """

        if settings.PLUGIN_FILE_CHECKED:
            logger.info('Plugin file was already checked')
            return

        try:
            output = str(subprocess.check_output(['pip', 'install', '-U', '-r', settings.PLUGIN_FILE], cwd=os.path.dirname(settings.BASE_DIR)), 'utf-8')
        except subprocess.CalledProcessError as error:  # pragma: no cover
            logger.error(f'Ran into error while trying to install plugins!\n{str(error)}')
            return False

        logger.info(f'plugin requirements were run\n{output}')

        # do not run again
        settings.PLUGIN_FILE_CHECKED = True

    # endregion

    # region registry functions
    def with_mixin(self, mixin: str):
        """
        Returns reference to all plugins that have a specified mixin enabled
        """
        result = []

        for plugin in self.plugins.values():
            if plugin.mixin_enabled(mixin):
                result.append(plugin)

        return result
    # endregion
    # endregion

    # region general internal loading /activating / deactivating / deloading
    def _init_plugins(self, disabled=None):
        """
        Initialise all found plugins

        :param disabled: loading path of disabled app, defaults to None
        :type disabled: str, optional
        :raises error: IntegrationPluginError
        """

        from plugin.models import PluginConfig

        logger.info('Starting plugin initialisation')

        # Initialize integration plugins
        for plugin in self.plugin_modules:
            # Check if package
            was_packaged = getattr(plugin, 'is_package', False)

            # Check if activated
            # These checks only use attributes - never use plugin supplied functions -> that would lead to arbitrary code execution!!
            plug_name = plugin.PLUGIN_NAME
            plug_key = plugin.PLUGIN_SLUG if getattr(plugin, 'PLUGIN_SLUG', None) else plug_name
            plug_key = slugify(plug_key)  # keys are slugs!
            try:
                plugin_db_setting, _ = PluginConfig.objects.get_or_create(key=plug_key, name=plug_name)
            except (OperationalError, ProgrammingError) as error:
                # Exception if the database has not been migrated yet - check if test are running - raise if not
                if not settings.PLUGIN_TESTING:
                    raise error  # pragma: no cover
                plugin_db_setting = None
            except (IntegrityError) as error:
                logger.error(f"Error initializing plugin: {error}")

            # Always activate if testing
            if settings.PLUGIN_TESTING or (plugin_db_setting and plugin_db_setting.active):
                # Check if the plugin was blocked -> threw an error
                if disabled:
                    # option1: package, option2: file-based
                    if (plugin.__name__ == disabled) or (plugin.__module__ == disabled):
                        # Errors are bad so disable the plugin in the database
                        if not settings.PLUGIN_TESTING:  # pragma: no cover
                            plugin_db_setting.active = False
                            # TODO save the error to the plugin
                            plugin_db_setting.save(no_reload=True)

                        # Add to inactive plugins so it shows up in the ui
                        self.plugins_inactive[plug_key] = plugin_db_setting
                        continue  # continue -> the plugin is not loaded

                # Initialize package
                # now we can be sure that an admin has activated the plugin
                # TODO check more stuff -> as of Nov 2021 there are not many checks in place
                # but we could enhance those to check signatures, run the plugin against a whitelist etc.
                logger.info(f'Loading integration plugin {plugin.PLUGIN_NAME}')
                try:
                    plugin = plugin()
                except Exception as error:
                    # log error and raise it -> disable plugin
                    handle_error(error, log_name='init')

                logger.info(f'Loaded integration plugin {plugin.slug}')
                plugin.is_package = was_packaged
                if plugin_db_setting:
                    plugin.pk = plugin_db_setting.pk

                # safe reference
                self.plugins[plugin.slug] = plugin
            else:
                # save for later reference
                self.plugins_inactive[plug_key] = plugin_db_setting

    def _activate_plugins(self, force_reload=False):
        """
        Run integration functions for all plugins

        :param force_reload: force reload base apps, defaults to False
        :type force_reload: bool, optional
        """
        # activate integrations
        plugins = self.plugins.items()
        logger.info(f'Found {len(plugins)} active plugins')

        self.activate_integration_settings(plugins)
        self.activate_integration_schedule(plugins)
        self.activate_integration_app(plugins, force_reload=force_reload)

    def _deactivate_plugins(self):
        """
        Run integration deactivation functions for all plugins
        """

        self.deactivate_integration_app()
        self.deactivate_integration_schedule()
        self.deactivate_integration_settings()
    # endregion

    # region mixin specific loading ...
    def activate_integration_settings(self, plugins):

        logger.info('Activating plugin settings')

        self.mixins_settings = {}

        for slug, plugin in plugins:
            if plugin.mixin_enabled('settings'):
                plugin_setting = plugin.settings
                self.mixins_settings[slug] = plugin_setting

    def deactivate_integration_settings(self):

        # collect all settings
        plugin_settings = {}

        for _, plugin_setting in self.mixins_settings.items():
            plugin_settings.update(plugin_setting)

        # clear cache
        self.mixins_settings = {}

    def activate_integration_schedule(self, plugins):

        logger.info('Activating plugin tasks')

        from common.models import InvenTreeSetting

        # List of tasks we have activated
        task_keys = []

        if settings.PLUGIN_TESTING or InvenTreeSetting.get_setting('ENABLE_PLUGINS_SCHEDULE'):

            for slug, plugin in plugins:

                if plugin.mixin_enabled('schedule'):
                    config = plugin.plugin_config()

                    # Only active tasks for plugins which are enabled
                    if config and config.active:
                        plugin.register_tasks()
                        task_keys += plugin.get_task_names()

        if len(task_keys) > 0:
            logger.info(f"Activated {len(task_keys)} scheduled tasks")

        # Remove any scheduled tasks which do not match
        # This stops 'old' plugin tasks from accumulating
        try:
            from django_q.models import Schedule

            scheduled_plugin_tasks = Schedule.objects.filter(name__istartswith="plugin.")

            deleted_count = 0

            for task in scheduled_plugin_tasks:
                if task.name not in task_keys:
                    task.delete()
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(f"Removed {deleted_count} old scheduled tasks")
        except (ProgrammingError, OperationalError):
            # Database might not yet be ready
            logger.warning("activate_integration_schedule failed, database not ready")

    def deactivate_integration_schedule(self):
        """
        Deactivate ScheduleMixin
        currently nothing is done
        """
        pass

    def activate_integration_app(self, plugins, force_reload=False):
        """
        Activate AppMixin plugins - add custom apps and reload

        :param plugins: list of IntegrationPlugins that should be installed
        :type plugins: dict
        :param force_reload: only reload base apps, defaults to False
        :type force_reload: bool, optional
        """
        from common.models import InvenTreeSetting

        if settings.PLUGIN_TESTING or InvenTreeSetting.get_setting('ENABLE_PLUGINS_APP'):
            logger.info('Registering IntegrationPlugin apps')
            apps_changed = False

            # add them to the INSTALLED_APPS
            for slug, plugin in plugins:
                if plugin.mixin_enabled('app'):
                    plugin_path = self._get_plugin_path(plugin)
                    if plugin_path not in settings.INSTALLED_APPS:
                        settings.INSTALLED_APPS += [plugin_path]
                        self.installed_apps += [plugin_path]
                        apps_changed = True

            # if apps were changed or force loading base apps -> reload
            if apps_changed or force_reload:
                # first startup or force loading of base apps -> registry is prob false
                if self.apps_loading or force_reload:
                    self.apps_loading = False
                    self._reload_apps(force_reload=True)
                else:
                    self._reload_apps()

                # rediscover models/ admin sites
                self._reregister_contrib_apps()

                # update urls - must be last as models must be registered for creating admin routes
                self._update_urls()

    def _reregister_contrib_apps(self):
        """fix reloading of contrib apps - models and admin
        this is needed if plugins were loaded earlier and then reloaded as models and admins rely on imports
        those register models and admin in their respective objects (e.g. admin.site for admin)
        """
        for plugin_path in self.installed_apps:
            try:
                app_name = plugin_path.split('.')[-1]
                app_config = apps.get_app_config(app_name)
            except LookupError:  # pragma: no cover
                # the plugin was never loaded correctly
                logger.debug(f'{app_name} App was not found during deregistering')
                break

            # reload models if they were set
            # models_module gets set if models were defined - even after multiple loads
            # on a reload the models registery is empty but models_module is not
            if app_config.models_module and len(app_config.models) == 0:
                reload(app_config.models_module)

            # check for all models if they are registered with the site admin
            model_not_reg = False
            for model in app_config.get_models():
                if not admin.site.is_registered(model):
                    model_not_reg = True

            # reload admin if at least one model is not registered
            # models are registered with admin in the 'admin.py' file - so we check
            # if the app_config has an admin module before trying to laod it
            if model_not_reg and hasattr(app_config.module, 'admin'):
                reload(app_config.module.admin)

    def _get_plugin_path(self, plugin):
        """parse plugin path
        the input can be eiter:
        - a local file / dir
        - a package
        """
        try:
            # for local path plugins
            plugin_path = '.'.join(pathlib.Path(plugin.path).relative_to(settings.BASE_DIR).parts)
        except ValueError:
            # plugin is shipped as package
            plugin_path = plugin.PLUGIN_NAME
        return plugin_path

    def deactivate_integration_app(self):
        """
        Deactivate integration app - some magic required
        """

        # unregister models from admin
        for plugin_path in self.installed_apps:
            models = []  # the modelrefs need to be collected as poping an item in a iter is not welcomed
            app_name = plugin_path.split('.')[-1]
            try:
                app_config = apps.get_app_config(app_name)

                # check all models
                for model in app_config.get_models():
                    # remove model from admin site
                    admin.site.unregister(model)
                    models += [model._meta.model_name]
            except LookupError:  # pragma: no cover
                # if an error occurs the app was never loaded right -> so nothing to do anymore
                logger.debug(f'{app_name} App was not found during deregistering')
                break

            # unregister the models (yes, models are just kept in multilevel dicts)
            for model in models:
                # remove model from general registry
                apps.all_models[plugin_path].pop(model)

            # clear the registry for that app
            # so that the import trick will work on reloading the same plugin
            # -> the registry is kept for the whole lifecycle
            if models and app_name in apps.all_models:
                apps.all_models.pop(app_name)

        # remove plugin from installed_apps
        self._clean_installed_apps()

        # reset load flag and reload apps
        settings.INTEGRATION_APPS_LOADED = False
        self._reload_apps()

        # update urls to remove the apps from the site admin
        self._update_urls()

    def _clean_installed_apps(self):
        for plugin in self.installed_apps:
            if plugin in settings.INSTALLED_APPS:
                settings.INSTALLED_APPS.remove(plugin)

        self.installed_apps = []

    def _clean_registry(self):
        # remove all plugins from registry
        self.plugins = {}
        self.plugins_inactive = {}

    def _update_urls(self):
        from InvenTree.urls import urlpatterns as global_pattern, frontendpatterns as urlpatterns
        from plugin.urls import get_plugin_urls

        for index, a in enumerate(urlpatterns):
            if hasattr(a, 'app_name'):
                if a.app_name == 'admin':
                    urlpatterns[index] = url(r'^admin/', admin.site.urls, name='inventree-admin')
                elif a.app_name == 'plugin':
                    urlpatterns[index] = get_plugin_urls()

        # replace frontendpatterns
        global_pattern[0] = url('', include(urlpatterns))
        clear_url_caches()

    def _reload_apps(self, force_reload: bool = False):
        self.is_loading = True  # set flag to disable loop reloading
        if force_reload:
            # we can not use the built in functions as we need to brute force the registry
            apps.app_configs = OrderedDict()
            apps.apps_ready = apps.models_ready = apps.loading = apps.ready = False
            apps.clear_cache()
            self._try_reload(apps.populate, settings.INSTALLED_APPS)
        else:
            self._try_reload(apps.set_installed_apps, settings.INSTALLED_APPS)
        self.is_loading = False

    def _try_reload(self, cmd, *args, **kwargs):
        """
        wrapper to try reloading the apps
        throws an custom error that gets handled by the loading function
        """
        try:
            cmd(*args, **kwargs)
            return True, []
        except Exception as error:  # pragma: no cover
            handle_error(error)
    # endregion


registry = PluginsRegistry()


def call_function(plugin_name, function_name, *args, **kwargs):
    """ Global helper function to call a specific member function of a plugin """
    return registry.call_plugin_function(plugin_name, function_name, *args, **kwargs)
