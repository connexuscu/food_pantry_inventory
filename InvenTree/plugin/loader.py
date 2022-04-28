"""
load templates for loaded plugins
"""
from django.template.loaders.filesystem import Loader as FilesystemLoader
from pathlib import Path

from plugin import registry


class PluginTemplateLoader(FilesystemLoader):

    def get_dirs(self):
        dirname = 'templates'
        template_dirs = []
        for plugin in registry.plugins.values():
            new_path = Path(plugin.path) / dirname
            if Path(new_path).is_dir():
                template_dirs.append(new_path)
        return tuple(template_dirs)
