"""
Pull rendered copies of the templated
only used for testing the js files! - This file is omited from coverage
"""

from django.test import TestCase  # pragma: no cover
from django.contrib.auth import get_user_model  # pragma: no cover

import os  # pragma: no cover
import pathlib  # pragma: no cover


class RenderJavascriptFiles(TestCase):  # pragma: no cover
    """
    A unit test to "render" javascript files.

    The server renders templated javascript files,
    we need the fully-rendered files for linting and static tests.
    """

    def setUp(self):

        user = get_user_model()

        self.user = user.objects.create_user(
            username='testuser',
            password='testpassword',
            email='user@gmail.com',
        )

        self.client.login(username='testuser', password='testpassword')

    def download_file(self, filename, prefix):

        url = os.path.join(prefix, filename)

        response = self.client.get(url)

        here = os.path.abspath(os.path.dirname(__file__))

        output_dir = os.path.join(
            here,
            '..',
            '..',
            'js_tmp',
        )

        output_dir = os.path.abspath(output_dir)

        if not os.path.exists(output_dir):
            os.mkdir(output_dir)

        output_file = os.path.join(
            output_dir,
            filename,
        )

        with open(output_file, 'wb') as output:
            output.write(response.content)

    def download_files(self, subdir, prefix):
        here = os.path.abspath(os.path.dirname(__file__))

        js_template_dir = os.path.join(
            here,
            '..',
            'templates',
            'js',
        )

        directory = os.path.join(js_template_dir, subdir)

        directory = os.path.abspath(directory)

        js_files = pathlib.Path(directory).rglob('*.js')

        n = 0

        for f in js_files:
            js = os.path.basename(f)

            self.download_file(js, prefix)

            n += 1

        return n

    def test_render_files(self):
        """
        Look for all javascript files
        """

        n = 0

        print("Rendering javascript files...")

        n += self.download_files('translated', '/js/i18n')
        n += self.download_files('dynamic', '/js/dynamic')

        print(f"Rendered {n} javascript files.")
