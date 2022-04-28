"""
Unit tests for plugins
"""

from django.test import TestCase

from plugin.samples.integration.sample import SampleIntegrationPlugin
from plugin.samples.integration.another_sample import WrongIntegrationPlugin, NoIntegrationPlugin
import plugin.templatetags.plugin_extras as plugin_tags
from plugin import registry, InvenTreePluginBase


class InvenTreePluginTests(TestCase):
    """ Tests for InvenTreePlugin """
    def setUp(self):
        self.plugin = InvenTreePluginBase()

        class NamedPlugin(InvenTreePluginBase):
            """a named plugin"""
            PLUGIN_NAME = 'abc123'

        self.named_plugin = NamedPlugin()

    def test_basic_plugin_init(self):
        """check if a basic plugin intis"""
        self.assertEqual(self.plugin.PLUGIN_NAME, '')
        self.assertEqual(self.plugin.plugin_name(), '')

    def test_basic_plugin_name(self):
        """check if the name of a basic plugin can be set"""
        self.assertEqual(self.named_plugin.PLUGIN_NAME, 'abc123')
        self.assertEqual(self.named_plugin.plugin_name(), 'abc123')


class PluginTagTests(TestCase):
    """ Tests for the plugin extras """

    def setUp(self):
        self.sample = SampleIntegrationPlugin()
        self.plugin_no = NoIntegrationPlugin()
        self.plugin_wrong = WrongIntegrationPlugin()

    def test_tag_plugin_list(self):
        """test that all plugins are listed"""
        self.assertEqual(plugin_tags.plugin_list(), registry.plugins)

    def test_tag_incative_plugin_list(self):
        """test that all inactive plugins are listed"""
        self.assertEqual(plugin_tags.inactive_plugin_list(), registry.plugins_inactive)

    def test_tag_plugin_settings(self):
        """check all plugins are listed"""
        self.assertEqual(
            plugin_tags.plugin_settings(self.sample),
            registry.mixins_settings.get(self.sample)
        )

    def test_tag_mixin_enabled(self):
        """check that mixin enabled functions work"""
        key = 'urls'
        # mixin enabled
        self.assertEqual(plugin_tags.mixin_enabled(self.sample, key), True)
        # mixin not enabled
        self.assertEqual(plugin_tags.mixin_enabled(self.plugin_wrong, key), False)
        # mxixn not existing
        self.assertEqual(plugin_tags.mixin_enabled(self.plugin_no, key), False)

    def test_tag_safe_url(self):
        """test that the safe url tag works expected"""
        # right url
        self.assertEqual(plugin_tags.safe_url('api-plugin-install'), '/api/plugin/install/')
        # wrong url
        self.assertEqual(plugin_tags.safe_url('indexas'), None)

    def test_tag_plugin_errors(self):
        """test that all errors are listed"""
        self.assertEqual(plugin_tags.plugin_errors(), registry.errors)
