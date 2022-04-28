import sys


def isInTestMode():
    """
    Returns True if the database is in testing mode
    """

    return 'test' in sys.argv


def isImportingData():
    """
    Returns True if the database is currently importing data,
    e.g. 'loaddata' command is performed
    """

    return 'loaddata' in sys.argv


def canAppAccessDatabase(allow_test=False):
    """
    Returns True if the apps.py file can access database records.

    There are some circumstances where we don't want the ready function in apps.py
    to touch the database
    """

    # If any of the following management commands are being executed,
    # prevent custom "on load" code from running!
    excluded_commands = [
        'flush',
        'loaddata',
        'dumpdata',
        'makemigrations',
        'migrate',
        'check',
        'shell',
        'createsuperuser',
        'wait_for_db',
        'prerender',
        'rebuild',
        'collectstatic',
        'makemessages',
        'compilemessages',
    ]

    if not allow_test:
        # Override for testing mode?
        excluded_commands.append('test')

    for cmd in excluded_commands:
        if cmd in sys.argv:
            return False

    return True
