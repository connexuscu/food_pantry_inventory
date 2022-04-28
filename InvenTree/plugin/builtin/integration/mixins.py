"""
Plugin mixin classes
"""

import logging
import json
import requests

from django.conf.urls import url, include
from django.db.utils import OperationalError, ProgrammingError

from plugin.models import PluginConfig, PluginSetting
from plugin.urls import PLUGIN_BASE
from plugin.helpers import MixinImplementationError, MixinNotImplementedError


logger = logging.getLogger('inventree')


class SettingsMixin:
    """
    Mixin that enables global settings for the plugin
    """

    class MixinMeta:
        MIXIN_NAME = 'Settings'

    def __init__(self):
        super().__init__()
        self.add_mixin('settings', 'has_settings', __class__)
        self.settings = getattr(self, 'SETTINGS', {})

    @property
    def has_settings(self):
        """
        Does this plugin use custom global settings
        """
        return bool(self.settings)

    def get_setting(self, key):
        """
        Return the 'value' of the setting associated with this plugin
        """

        return PluginSetting.get_setting(key, plugin=self)

    def set_setting(self, key, value, user=None):
        """
        Set plugin setting value by key
        """

        try:
            plugin, _ = PluginConfig.objects.get_or_create(key=self.plugin_slug(), name=self.plugin_name())
        except (OperationalError, ProgrammingError):  # pragma: no cover
            plugin = None

        if not plugin:
            # Cannot find associated plugin model, return
            return

        PluginSetting.set_setting(key, value, user, plugin=plugin)


class ScheduleMixin:
    """
    Mixin that provides support for scheduled tasks.

    Implementing classes must provide a dict object called SCHEDULED_TASKS,
    which provides information on the tasks to be scheduled.

    SCHEDULED_TASKS = {
        # Name of the task (will be prepended with the plugin name)
        'test_server': {
            'func': 'myplugin.tasks.test_server',   # Python function to call (no arguments!)
            'schedule': "I",                        # Schedule type (see django_q.Schedule)
            'minutes': 30,                          # Number of minutes (only if schedule type = Minutes)
            'repeats': 5,                           # Number of repeats (leave blank for 'forever')
        },
        'member_func': {
            'func': 'my_class_func',                # Note, without the 'dot' notation, it will call a class member function
            'schedule': "H",                        # Once per hour
        },
    }

    Note: 'schedule' parameter must be one of ['I', 'H', 'D', 'W', 'M', 'Q', 'Y']

    Note: The 'func' argument can take two different forms:
        - Dotted notation e.g. 'module.submodule.func' - calls a global function with the defined path
        - Member notation e.g. 'my_func' (no dots!) - calls a member function of the calling class
    """

    ALLOWABLE_SCHEDULE_TYPES = ['I', 'H', 'D', 'W', 'M', 'Q', 'Y']

    # Override this in subclass model
    SCHEDULED_TASKS = {}

    class MixinMeta:
        """
        Meta options for this mixin
        """
        MIXIN_NAME = 'Schedule'

    def __init__(self):
        super().__init__()
        self.scheduled_tasks = self.get_scheduled_tasks()
        self.validate_scheduled_tasks()

        self.add_mixin('schedule', 'has_scheduled_tasks', __class__)

    def get_scheduled_tasks(self):
        return getattr(self, 'SCHEDULED_TASKS', {})

    @property
    def has_scheduled_tasks(self):
        """
        Are tasks defined for this plugin
        """
        return bool(self.scheduled_tasks)

    def validate_scheduled_tasks(self):
        """
        Check that the provided scheduled tasks are valid
        """

        if not self.has_scheduled_tasks:
            raise MixinImplementationError("SCHEDULED_TASKS not defined")

        for key, task in self.scheduled_tasks.items():

            if 'func' not in task:
                raise MixinImplementationError(f"Task '{key}' is missing 'func' parameter")

            if 'schedule' not in task:
                raise MixinImplementationError(f"Task '{key}' is missing 'schedule' parameter")

            schedule = task['schedule'].upper().strip()

            if schedule not in self.ALLOWABLE_SCHEDULE_TYPES:
                raise MixinImplementationError(f"Task '{key}': Schedule '{schedule}' is not a valid option")

            # If 'minutes' is selected, it must be provided!
            if schedule == 'I' and 'minutes' not in task:
                raise MixinImplementationError(f"Task '{key}' is missing 'minutes' parameter")

    def get_task_name(self, key):
        """
        Task name for key
        """
        # Generate a 'unique' task name
        slug = self.plugin_slug()
        return f"plugin.{slug}.{key}"

    def get_task_names(self):
        """
        All defined task names
        """
        # Returns a list of all task names associated with this plugin instance
        return [self.get_task_name(key) for key in self.scheduled_tasks.keys()]

    def register_tasks(self):
        """
        Register the tasks with the database
        """

        try:
            from django_q.models import Schedule

            for key, task in self.scheduled_tasks.items():

                task_name = self.get_task_name(key)

                if Schedule.objects.filter(name=task_name).exists():
                    # Scheduled task already exists - continue!
                    continue

                logger.info(f"Adding scheduled task '{task_name}'")

                func_name = task['func'].strip()

                if '.' in func_name:
                    """
                    Dotted notation indicates that we wish to run a globally defined function,
                    from a specified Python module.
                    """

                    Schedule.objects.create(
                        name=task_name,
                        func=func_name,
                        schedule_type=task['schedule'],
                        minutes=task.get('minutes', None),
                        repeats=task.get('repeats', -1),
                    )

                else:
                    """
                    Non-dotted notation indicates that we wish to call a 'member function' of the calling plugin.

                    This is managed by the plugin registry itself.
                    """

                    slug = self.plugin_slug()

                    Schedule.objects.create(
                        name=task_name,
                        func='plugin.registry.call_function',
                        args=f"'{slug}', '{func_name}'",
                        schedule_type=task['schedule'],
                        minutes=task.get('minutes', None),
                        repeats=task.get('repeats', -1),
                    )

        except (ProgrammingError, OperationalError):
            # Database might not yet be ready
            logger.warning("register_tasks failed, database not ready")

    def unregister_tasks(self):
        """
        Deregister the tasks with the database
        """

        try:
            from django_q.models import Schedule

            for key, task in self.scheduled_tasks.items():

                task_name = self.get_task_name(key)

                try:
                    scheduled_task = Schedule.objects.get(name=task_name)
                    scheduled_task.delete()
                except Schedule.DoesNotExist:
                    pass
        except (ProgrammingError, OperationalError):
            # Database might not yet be ready
            logger.warning("unregister_tasks failed, database not ready")


class EventMixin:
    """
    Mixin that provides support for responding to triggered events.

    Implementing classes must provide a "process_event" function:
    """

    def process_event(self, event, *args, **kwargs):
        """
        Function to handle events
        Must be overridden by plugin
        """
        # Default implementation does not do anything
        raise MixinNotImplementedError

    class MixinMeta:
        """
        Meta options for this mixin
        """
        MIXIN_NAME = 'Events'

    def __init__(self):
        super().__init__()
        self.add_mixin('events', True, __class__)


class UrlsMixin:
    """
    Mixin that enables custom URLs for the plugin
    """

    class MixinMeta:
        """
        Meta options for this mixin
        """
        MIXIN_NAME = 'URLs'

    def __init__(self):
        super().__init__()
        self.add_mixin('urls', 'has_urls', __class__)
        self.urls = self.setup_urls()

    def setup_urls(self):
        """
        Setup url endpoints for this plugin
        """
        return getattr(self, 'URLS', None)

    @property
    def base_url(self):
        """
        Base url for this plugin
        """
        return f'{PLUGIN_BASE}/{self.slug}/'

    @property
    def internal_name(self):
        """
        Internal url pattern name
        """
        return f'plugin:{self.slug}:'

    @property
    def urlpatterns(self):
        """
        Urlpatterns for this plugin
        """
        if self.has_urls:
            return url(f'^{self.slug}/', include((self.urls, self.slug)), name=self.slug)
        return None

    @property
    def has_urls(self):
        """
        Does this plugin use custom urls
        """
        return bool(self.urls)


class NavigationMixin:
    """
    Mixin that enables custom navigation links with the plugin
    """

    NAVIGATION_TAB_NAME = None
    NAVIGATION_TAB_ICON = "fas fa-question"

    class MixinMeta:
        """
        Meta options for this mixin
        """
        MIXIN_NAME = 'Navigation Links'

    def __init__(self):
        super().__init__()
        self.add_mixin('navigation', 'has_naviation', __class__)
        self.navigation = self.setup_navigation()

    def setup_navigation(self):
        """
        Setup navigation links for this plugin
        """
        nav_links = getattr(self, 'NAVIGATION', None)
        if nav_links:
            # check if needed values are configured
            for link in nav_links:
                if False in [a in link for a in ('link', 'name', )]:
                    raise MixinNotImplementedError('Wrong Link definition', link)
        return nav_links

    @property
    def has_naviation(self):
        """
        Does this plugin define navigation elements
        """
        return bool(self.navigation)

    @property
    def navigation_name(self):
        """
        Name for navigation tab
        """
        name = getattr(self, 'NAVIGATION_TAB_NAME', None)
        if not name:
            name = self.human_name
        return name

    @property
    def navigation_icon(self):
        """
        Icon-name for navigation tab
        """
        return getattr(self, 'NAVIGATION_TAB_ICON', "fas fa-question")


class AppMixin:
    """
    Mixin that enables full django app functions for a plugin
    """

    class MixinMeta:
        """m
        Mta options for this mixin
        """
        MIXIN_NAME = 'App registration'

    def __init__(self):
        super().__init__()
        self.add_mixin('app', 'has_app', __class__)

    @property
    def has_app(self):
        """
        This plugin is always an app with this plugin
        """
        return True


class LabelPrintingMixin:
    """
    Mixin which enables direct printing of stock labels.

    Each plugin must provide a PLUGIN_NAME attribute, which is used to uniquely identify the printer.

    The plugin must also implement the print_label() function
    """

    class MixinMeta:
        """
        Meta options for this mixin
        """
        MIXIN_NAME = 'Label printing'

    def __init__(self):
        super().__init__()
        self.add_mixin('labels', True, __class__)

    def print_label(self, label, **kwargs):
        """
        Callback to print a single label

        Arguments:
            label: A black-and-white pillow Image object

        kwargs:
            length: The length of the label (in mm)
            width: The width of the label (in mm)

        """

        # Unimplemented (to be implemented by the particular plugin class)
        ...


class APICallMixin:
    """
    Mixin that enables easier API calls for a plugin

    Steps to set up:
    1. Add this mixin before (left of) SettingsMixin and PluginBase
    2. Add two settings for the required url and token/passowrd (use `SettingsMixin`)
    3. Save the references to keys of the settings in `API_URL_SETTING` and `API_TOKEN_SETTING`
    4. (Optional) Set `API_TOKEN` to the name required for the token by the external API - Defaults to `Bearer`
    5. (Optional) Override the `api_url` property method if the setting needs to be extended
    6. (Optional) Override `api_headers` to add extra headers (by default the token and Content-Type are contained)
    7. Access the API in you plugin code via `api_call`

    Example:
    ```
    from plugin import IntegrationPluginBase
    from plugin.mixins import APICallMixin, SettingsMixin


    class SampleApiCallerPlugin(APICallMixin, SettingsMixin, IntegrationPluginBase):
        '''
        A small api call sample
        '''
        PLUGIN_NAME = "Sample API Caller"

        SETTINGS = {
            'API_TOKEN': {
                'name': 'API Token',
                'protected': True,
            },
            'API_URL': {
                'name': 'External URL',
                'description': 'Where is your API located?',
                'default': 'reqres.in',
            },
        }
        API_URL_SETTING = 'API_URL'
        API_TOKEN_SETTING = 'API_TOKEN'

        def get_external_url(self):
            '''
            returns data from the sample endpoint
            '''
            return self.api_call('api/users/2')
    ```
    """
    API_METHOD = 'https'
    API_URL_SETTING = None
    API_TOKEN_SETTING = None

    API_TOKEN = 'Bearer'

    class MixinMeta:
        """meta options for this mixin"""
        MIXIN_NAME = 'API calls'

    def __init__(self):
        super().__init__()
        self.add_mixin('api_call', 'has_api_call', __class__)

    @property
    def has_api_call(self):
        """Is the mixin ready to call external APIs?"""
        if not bool(self.API_URL_SETTING):
            raise ValueError("API_URL_SETTING must be defined")
        if not bool(self.API_TOKEN_SETTING):
            raise ValueError("API_TOKEN_SETTING must be defined")
        return True

    @property
    def api_url(self):
        return f'{self.API_METHOD}://{self.get_setting(self.API_URL_SETTING)}'

    @property
    def api_headers(self):
        headers = {'Content-Type': 'application/json'}
        if getattr(self, 'API_TOKEN_SETTING'):
            headers[self.API_TOKEN] = self.get_setting(self.API_TOKEN_SETTING)
        return headers

    def api_build_url_args(self, arguments):
        groups = []
        for key, val in arguments.items():
            groups.append(f'{key}={",".join([str(a) for a in val])}')
        return f'?{"&".join(groups)}'

    def api_call(self, endpoint, method: str = 'GET', url_args=None, data=None, headers=None, simple_response: bool = True, endpoint_is_url: bool = False):
        if url_args:
            endpoint += self.api_build_url_args(url_args)

        if headers is None:
            headers = self.api_headers

        if endpoint_is_url:
            url = endpoint
        else:
            url = f'{self.api_url}/{endpoint}'

        # build kwargs for call
        kwargs = {
            'url': url,
            'headers': headers,
        }
        if data:
            kwargs['data'] = json.dumps(data)

        # run command
        response = requests.request(method, **kwargs)

        # return
        if simple_response:
            return response.json()
        return response
