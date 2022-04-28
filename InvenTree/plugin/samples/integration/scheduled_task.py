"""
Sample plugin which supports task scheduling
"""

from plugin import IntegrationPluginBase
from plugin.mixins import ScheduleMixin, SettingsMixin


# Define some simple tasks to perform
def print_hello():
    print("Hello")


def print_world():
    print("World")


class ScheduledTaskPlugin(ScheduleMixin, SettingsMixin, IntegrationPluginBase):
    """
    A sample plugin which provides support for scheduled tasks
    """

    PLUGIN_NAME = "ScheduledTasksPlugin"
    PLUGIN_SLUG = "schedule"
    PLUGIN_TITLE = "Scheduled Tasks"

    SCHEDULED_TASKS = {
        'member': {
            'func': 'member_func',
            'schedule': 'I',
            'minutes': 30,
        },
        'hello': {
            'func': 'plugin.samples.integration.scheduled_task.print_hello',
            'schedule': 'I',
            'minutes': 45,
        },
        'world': {
            'func': 'plugin.samples.integration.scheduled_task.print_hello',
            'schedule': 'H',
        },
    }

    SETTINGS = {
        'T_OR_F': {
            'name': 'True or False',
            'description': 'Print true or false when running the periodic task',
            'validator': bool,
            'default': False,
        },
    }

    def member_func(self, *args, **kwargs):
        """
        A simple member function to demonstrate functionality
        """

        t_or_f = self.get_setting('T_OR_F')

        print(f"Called member_func - value is {t_or_f}")
