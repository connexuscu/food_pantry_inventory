""" Unit tests for action plugins """

from django.test import TestCase

from plugin.action import ActionPlugin


class ActionPluginTests(TestCase):
    """ Tests for ActionPlugin """
    ACTION_RETURN = 'a action was performed'

    def setUp(self):
        self.plugin = ActionPlugin('user')

        class TestActionPlugin(ActionPlugin):
            """a action plugin"""
            ACTION_NAME = 'abc123'

            def perform_action(self):
                return ActionPluginTests.ACTION_RETURN + 'action'

            def get_result(self):
                return ActionPluginTests.ACTION_RETURN + 'result'

            def get_info(self):
                return ActionPluginTests.ACTION_RETURN + 'info'

        self.action_plugin = TestActionPlugin('user')

        class NameActionPlugin(ActionPlugin):
            PLUGIN_NAME = 'Aplugin'

        self.action_name = NameActionPlugin('user')

    def test_action_name(self):
        """check the name definition possibilities"""
        self.assertEqual(self.plugin.action_name(), '')
        self.assertEqual(self.action_plugin.action_name(), 'abc123')
        self.assertEqual(self.action_name.action_name(), 'Aplugin')

    def test_function(self):
        """check functions"""
        # the class itself
        self.assertIsNone(self.plugin.perform_action())
        self.assertEqual(self.plugin.get_result(), False)
        self.assertIsNone(self.plugin.get_info())
        self.assertEqual(self.plugin.get_response(), {
            "action": '',
            "result": False,
            "info": None,
        })

        # overriden functions
        self.assertEqual(self.action_plugin.perform_action(), self.ACTION_RETURN + 'action')
        self.assertEqual(self.action_plugin.get_result(), self.ACTION_RETURN + 'result')
        self.assertEqual(self.action_plugin.get_info(), self.ACTION_RETURN + 'info')
        self.assertEqual(self.action_plugin.get_response(), {
            "action": 'abc123',
            "result": self.ACTION_RETURN + 'result',
            "info": self.ACTION_RETURN + 'info',
        })
