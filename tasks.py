# -*- coding: utf-8 -*-

import os
import json
import sys
import pathlib
import re

try:
    from invoke import ctask as task
except:
    from invoke import task


def apps():
    """
    Returns a list of installed apps
    """

    return [
        'barcode',
        'build',
        'common',
        'company',
        'label',
        'order',
        'part',
        'report',
        'stock',
        'InvenTree',
        'users',
    ]


def localDir():
    """
    Returns the directory of *THIS* file.
    Used to ensure that the various scripts always run
    in the correct directory.
    """
    return os.path.dirname(os.path.abspath(__file__))


def managePyDir():
    """
    Returns the directory of the manage.py file
    """

    return os.path.join(localDir(), 'InvenTree')


def managePyPath():
    """
    Return the path of the manage.py file
    """

    return os.path.join(managePyDir(), 'manage.py')


def manage(c, cmd, pty=False):
    """
    Runs a given command against django's "manage.py" script.

    Args:
        c - Command line context
        cmd - django command to run
    """

    result = c.run('cd "{path}" && python3 manage.py {cmd}'.format(
        path=managePyDir(),
        cmd=cmd
    ), pty=pty)

@task
def plugins(c):
    """
    Installs all plugins as specified in 'plugins.txt'
    """

    from InvenTree.InvenTree.config import get_plugin_file

    plugin_file = get_plugin_file()

    print(f"Installing plugin packages from '{plugin_file}'")

    # Install the plugins
    c.run(f"pip3 install -U -r '{plugin_file}'")

@task(post=[plugins])
def install(c):
    """
    Installs required python packages
    """

    print("Installing required python packages from 'requirements.txt'")

    # Install required Python packages with PIP
    c.run('pip3 install -U -r requirements.txt')

@task
def shell(c):
    """
    Open a python shell with access to the InvenTree database models.
    """

    manage(c, 'shell', pty=True)


@task
def superuser(c):
    """
    Create a superuser (admin) account for the database.
    """

    manage(c, 'createsuperuser', pty=True)


@task
def check(c):
    """
    Check validity of django codebase
    """

    manage(c, "check")


@task
def wait(c):
    """
    Wait until the database connection is ready
    """

    return manage(c, "wait_for_db")


@task(pre=[wait])
def worker(c):
    """
    Run the InvenTree background worker process
    """

    manage(c, 'qcluster', pty=True)


@task
def rebuild_models(c):
    """
    Rebuild database models with MPTT structures
    """

    manage(c, "rebuild_models", pty=True)


@task
def rebuild_thumbnails(c):
    """
    Rebuild missing image thumbnails
    """

    manage(c, "rebuild_thumbnails", pty=True)


@task
def clean_settings(c):
    """
    Clean the setting tables of old settings
    """

    manage(c, "clean_settings")


@task(help={'mail': 'mail of the user whos MFA should be disabled'})
def remove_mfa(c, mail=''):
    """
    Remove MFA for a user
    """

    if not mail:
        print('You must provide a users mail')

    manage(c, f"remove_mfa {mail}")


@task(post=[rebuild_models, rebuild_thumbnails])
def migrate(c):
    """
    Performs database migrations.
    This is a critical step if the database schema have been altered!
    """

    print("Running InvenTree database migrations...")
    print("========================================")

    manage(c, "makemigrations")
    manage(c, "migrate --noinput")
    manage(c, "migrate --run-syncdb")
    manage(c, "check")

    print("========================================")
    print("InvenTree database migrations completed!")


@task
def static(c):
    """
    Copies required static files to the STATIC_ROOT directory,
    as per Django requirements.
    """

    manage(c, "prerender")
    manage(c, "collectstatic --no-input")


@task
def translate_stats(c):
    """
    Collect translation stats.
    The file generated from this is needed for the UI.
    """

    path = os.path.join('InvenTree', 'script', 'translation_stats.py')
    c.run(f'python3 {path}')


@task(post=[translate_stats, static])
def translate(c):
    """
    Regenerate translation files.

    Run this command after added new translatable strings,
    or after adding translations for existing strings.
    """

    # Translate applicable .py / .html / .js files
    manage(c, "makemessages --all -e py,html,js --no-wrap")
    manage(c, "compilemessages")


@task(pre=[install, migrate, translate_stats, static, clean_settings])
def update(c):
    """
    Update InvenTree installation.

    This command should be invoked after source code has been updated,
    e.g. downloading new code from GitHub.

    The following tasks are performed, in order:

    - install
    - migrate
    - translate_stats
    - static
    - clean_settings
    """
    pass


@task
def style(c):
    """
    Run PEP style checks against InvenTree sourcecode
    """

    print("Running PEP style checks...")
    c.run('flake8 InvenTree')


@task
def test(c, database=None):
    """
    Run unit-tests for InvenTree codebase.
    """
    # Run sanity check on the django install
    manage(c, 'check')

    # Run coverage tests
    manage(c, 'test', pty=True)


@task
def coverage(c):
    """
    Run code-coverage of the InvenTree codebase,
    using the 'coverage' code-analysis tools.

    Generates a code coverage report (available in the htmlcov directory)
    """

    # Run sanity check on the django install
    manage(c, 'check')

    # Run coverage tests
    c.run('coverage run {manage} test {apps}'.format(
        manage=managePyPath(),
        apps=' '.join(apps())
    ))

    # Generate coverage report
    c.run('coverage html')


def content_excludes():
    """
    Returns a list of content types to exclude from import/export
    """

    excludes = [
        "contenttypes",
        "auth.permission",
        "authtoken.token",
        "error_report.error",
        "admin.logentry",
        "django_q.schedule",
        "django_q.task",
        "django_q.ormq",
        "users.owner",
        "exchange.rate",
        "exchange.exchangebackend",
        "common.notificationentry",
        "user_sessions.session",
    ]

    output = ""

    for e in excludes:
        output += f"--exclude {e} "

    return output


@task(help={'filename': "Output filename (default = 'data.json')"})
def export_records(c, filename='data.json'):
    """
    Export all database records to a file
    """

    # Get an absolute path to the file
    if not os.path.isabs(filename):
        filename = os.path.join(localDir(), filename)
        filename = os.path.abspath(filename)

    print(f"Exporting database records to file '{filename}'")

    if os.path.exists(filename):
        response = input("Warning: file already exists. Do you want to overwrite? [y/N]: ")
        response = str(response).strip().lower()

        if response not in ['y', 'yes']:
            print("Cancelled export operation")
            sys.exit(1)

    tmpfile = f"{filename}.tmp"

    cmd = f"dumpdata --indent 2 --output '{tmpfile}' {content_excludes()}"

    # Dump data to temporary file
    manage(c, cmd, pty=True)

    print("Running data post-processing step...")

    # Post-process the file, to remove any "permissions" specified for a user or group
    with open(tmpfile, "r") as f_in:
        data = json.loads(f_in.read())

    for entry in data:
        if "model" in entry:

            # Clear out any permissions specified for a group
            if entry["model"] == "auth.group":
                entry["fields"]["permissions"] = []

            # Clear out any permissions specified for a user
            if entry["model"] == "auth.user":
                entry["fields"]["user_permissions"] = []

    # Write the processed data to file
    with open(filename, "w") as f_out:
        f_out.write(json.dumps(data, indent=2))

    print("Data export completed")


@task(help={'filename': 'Input filename'}, post=[rebuild_models, rebuild_thumbnails])
def import_records(c, filename='data.json'):
    """
    Import database records from a file
    """

    # Get an absolute path to the supplied filename
    if not os.path.isabs(filename):
        filename = os.path.join(localDir(), filename)

    if not os.path.exists(filename):
        print(f"Error: File '{filename}' does not exist")
        sys.exit(1)

    print(f"Importing database records from '{filename}'")

    # Pre-process the data, to remove any "permissions" specified for a user or group
    tmpfile = f"{filename}.tmp.json"

    with open(filename, "r") as f_in:
        data = json.loads(f_in.read())

    for entry in data:
        if "model" in entry:

            # Clear out any permissions specified for a group
            if entry["model"] == "auth.group":
                entry["fields"]["permissions"] = []

            # Clear out any permissions specified for a user
            if entry["model"] == "auth.user":
                entry["fields"]["user_permissions"] = []

    # Write the processed data to the tmp file
    with open(tmpfile, "w") as f_out:
        f_out.write(json.dumps(data, indent=2))

    cmd = f"loaddata '{tmpfile}' -i {content_excludes()}"

    manage(c, cmd, pty=True)

    print("Data import completed")


@task
def delete_data(c, force=False):
    """
    Delete all database records!

    Warning: This will REALLY delete all records in the database!!
    """

    if force:
        manage(c, 'flush --noinput')
    else:
        manage(c, 'flush')


@task(post=[rebuild_models, rebuild_thumbnails])
def import_fixtures(c):
    """
    Import fixture data into the database.

    This command imports all existing test fixture data into the database.

    Warning:
        - Intended for testing / development only!
        - Running this command may overwrite existing database data!!
        - Don't say you were not warned...
    """

    fixtures = [
        # Build model
        'build',

        # Common models
        'settings',

        # Company model
        'company',
        'price_breaks',
        'supplier_part',

        # Order model
        'order',

        # Part model
        'bom',
        'category',
        'params',
        'part',
        'test_templates',

        # Stock model
        'location',
        'stock_tests',
        'stock',

        # Users
        'users'
    ]

    command = 'loaddata ' + ' '.join(fixtures)

    manage(c, command, pty=True)


@task(help={'address': 'Server address:port (default=127.0.0.1:8000)'})
def server(c, address="127.0.0.1:8000"):
    """
    Launch a (deveopment) server using Django's in-built webserver.

    Note: This is *not* sufficient for a production installation.
    """

    manage(c, "runserver {address}".format(address=address), pty=True)


@task(post=[translate_stats, static, server])
def test_translations(c):
    """
    Add a fictional language to test if each component is ready for translations
    """
    import django
    from django.conf import settings

    # setup django
    base_path = os.getcwd()
    new_base_path = pathlib.Path('InvenTree').absolute()
    sys.path.append(str(new_base_path))
    os.chdir(new_base_path)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvenTree.settings')
    django.setup()

    # Add language
    print("Add dummy language...")
    print("========================================")
    manage(c, "makemessages -e py,html,js --no-wrap -l xx")

    # change translation
    print("Fill in dummy translations...")
    print("========================================")

    file_path = pathlib.Path(settings.LOCALE_PATHS[0], 'xx', 'LC_MESSAGES', 'django.po')
    new_file_path = str(file_path) + '_new'

    # complie regex
    reg = re.compile(
        r"[a-zA-Z0-9]{1}"+  # match any single letter and number
        r"(?![^{\(\<]*[}\)\>])"+  # that is not inside curly brackets, brackets or a tag
        r"(?<![^\%][^\(][)][a-z])"+  # that is not a specially formatted variable with singles
        r"(?![^\\][\n])"  # that is not a newline
    )
    last_string = ''

    # loop through input file lines
    with open(file_path, "rt") as file_org:
        with open(new_file_path, "wt") as file_new:
            for line in file_org:
                if line.startswith('msgstr "'):
                    # write output -> replace regex matches with x in the read in (multi)string
                    file_new.write(f'msgstr "{reg.sub("x", last_string[7:-2])}"\n')
                    last_string = ""  # reset (multi)string
                elif line.startswith('msgid "'):
                    last_string = last_string + line  # a new translatable string starts -> start append
                    file_new.write(line)
                else:
                    if last_string:
                        last_string = last_string + line  # a string is beeing read in -> continue appending
                    file_new.write(line)

    # change out translation files
    os.rename(file_path, str(file_path) + '_old')
    os.rename(new_file_path, file_path)

    # compile languages
    print("Compile languages ...")
    print("========================================")
    manage(c, "compilemessages")

    # reset cwd
    os.chdir(base_path)

    # set env flag
    os.environ['TEST_TRANSLATIONS'] = 'True'


@task
def render_js_files(c):
    """
    Render templated javascript files (used for static testing).
    """

    manage(c, "test InvenTree.ci_render_js")
