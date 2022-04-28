""" Unit tests for integration plugins """

from django.test import TestCase
from django.conf import settings
from django.conf.urls import url, include
from django.contrib.auth import get_user_model

from datetime import datetime

from plugin import IntegrationPluginBase
from plugin.mixins import AppMixin, SettingsMixin, UrlsMixin, NavigationMixin, APICallMixin
from plugin.urls import PLUGIN_BASE


class BaseMixinDefinition:
    def test_mixin_name(self):
        # mixin name
        self.assertIn(self.MIXIN_NAME, [item['key'] for item in self.mixin.registered_mixins])
        # human name
        self.assertIn(self.MIXIN_HUMAN_NAME, [item['human_name'] for item in self.mixin.registered_mixins])


class SettingsMixinTest(BaseMixinDefinition, TestCase):
    MIXIN_HUMAN_NAME = 'Settings'
    MIXIN_NAME = 'settings'
    MIXIN_ENABLE_CHECK = 'has_settings'

    TEST_SETTINGS = {'SETTING1': {'default': '123', }}

    def setUp(self):
        class SettingsCls(SettingsMixin, IntegrationPluginBase):
            SETTINGS = self.TEST_SETTINGS
        self.mixin = SettingsCls()

        class NoSettingsCls(SettingsMixin, IntegrationPluginBase):
            pass
        self.mixin_nothing = NoSettingsCls()

        user = get_user_model()
        self.test_user = user.objects.create_user('testuser', 'test@testing.com', 'password')
        self.test_user.is_staff = True

    def test_function(self):
        # settings variable
        self.assertEqual(self.mixin.settings, self.TEST_SETTINGS)

        # calling settings
        # not existing
        self.assertEqual(self.mixin.get_setting('ABCD'), '')
        self.assertEqual(self.mixin_nothing.get_setting('ABCD'), '')

        # right setting
        self.mixin.set_setting('SETTING1', '12345', self.test_user)
        self.assertEqual(self.mixin.get_setting('SETTING1'), '12345')

        # no setting
        self.assertEqual(self.mixin_nothing.get_setting(''), '')


class UrlsMixinTest(BaseMixinDefinition, TestCase):
    MIXIN_HUMAN_NAME = 'URLs'
    MIXIN_NAME = 'urls'
    MIXIN_ENABLE_CHECK = 'has_urls'

    def setUp(self):
        class UrlsCls(UrlsMixin, IntegrationPluginBase):
            def test():
                return 'ccc'
            URLS = [url('testpath', test, name='test'), ]
        self.mixin = UrlsCls()

        class NoUrlsCls(UrlsMixin, IntegrationPluginBase):
            pass
        self.mixin_nothing = NoUrlsCls()

    def test_function(self):
        plg_name = self.mixin.plugin_name()

        # base_url
        target_url = f'{PLUGIN_BASE}/{plg_name}/'
        self.assertEqual(self.mixin.base_url, target_url)

        # urlpattern
        target_pattern = url(f'^{plg_name}/', include((self.mixin.urls, plg_name)), name=plg_name)
        self.assertEqual(self.mixin.urlpatterns.reverse_dict, target_pattern.reverse_dict)

        # resolve the view
        self.assertEqual(self.mixin.urlpatterns.resolve('/testpath').func(), 'ccc')
        self.assertEqual(self.mixin.urlpatterns.reverse('test'), 'testpath')

        # no url
        self.assertIsNone(self.mixin_nothing.urls)
        self.assertIsNone(self.mixin_nothing.urlpatterns)

        # internal name
        self.assertEqual(self.mixin.internal_name, f'plugin:{self.mixin.slug}:')


class AppMixinTest(BaseMixinDefinition, TestCase):
    MIXIN_HUMAN_NAME = 'App registration'
    MIXIN_NAME = 'app'
    MIXIN_ENABLE_CHECK = 'has_app'

    def setUp(self):
        class TestCls(AppMixin, IntegrationPluginBase):
            pass
        self.mixin = TestCls()

    def test_function(self):
        # test that this plugin is in settings
        self.assertIn('plugin.samples.integration', settings.INSTALLED_APPS)


class NavigationMixinTest(BaseMixinDefinition, TestCase):
    MIXIN_HUMAN_NAME = 'Navigation Links'
    MIXIN_NAME = 'navigation'
    MIXIN_ENABLE_CHECK = 'has_naviation'

    def setUp(self):
        class NavigationCls(NavigationMixin, IntegrationPluginBase):
            NAVIGATION = [
                {'name': 'aa', 'link': 'plugin:test:test_view'},
            ]
            NAVIGATION_TAB_NAME = 'abcd1'
        self.mixin = NavigationCls()

        class NothingNavigationCls(NavigationMixin, IntegrationPluginBase):
            pass
        self.nothing_mixin = NothingNavigationCls()

    def test_function(self):
        # check right configuration
        self.assertEqual(self.mixin.navigation, [{'name': 'aa', 'link': 'plugin:test:test_view'}, ])
        # check wrong links fails
        with self.assertRaises(NotImplementedError):
            class NavigationCls(NavigationMixin, IntegrationPluginBase):
                NAVIGATION = ['aa', 'aa']
            NavigationCls()

        # navigation name
        self.assertEqual(self.mixin.navigation_name, 'abcd1')
        self.assertEqual(self.nothing_mixin.navigation_name, '')


class APICallMixinTest(BaseMixinDefinition, TestCase):
    MIXIN_HUMAN_NAME = 'API calls'
    MIXIN_NAME = 'api_call'
    MIXIN_ENABLE_CHECK = 'has_api_call'

    def setUp(self):
        class MixinCls(APICallMixin, SettingsMixin, IntegrationPluginBase):
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
        self.mixin = MixinCls()

        class WrongCLS(APICallMixin, IntegrationPluginBase):
            pass
        self.mixin_wrong = WrongCLS()

        class WrongCLS2(APICallMixin, IntegrationPluginBase):
            API_URL_SETTING = 'test'
        self.mixin_wrong2 = WrongCLS2()

    def test_function(self):
        # check init
        self.assertTrue(self.mixin.has_api_call)
        # api_url
        self.assertEqual('https://reqres.in', self.mixin.api_url)

        # api_headers
        headers = self.mixin.api_headers
        self.assertEqual(headers, {'Bearer': '', 'Content-Type': 'application/json'})

        # api_build_url_args
        # 1 arg
        result = self.mixin.api_build_url_args({'a': 'b'})
        self.assertEqual(result, '?a=b')
        # more args
        result = self.mixin.api_build_url_args({'a': 'b', 'c': 'd'})
        self.assertEqual(result, '?a=b&c=d')
        # list args
        result = self.mixin.api_build_url_args({'a': 'b', 'c': ['d', 'e', 'f', ]})
        self.assertEqual(result, '?a=b&c=d,e,f')

        # api_call
        result = self.mixin.get_external_url()
        self.assertTrue(result)
        self.assertIn('data', result,)

        # wrongly defined plugins should not load
        with self.assertRaises(ValueError):
            self.mixin_wrong.has_api_call()

        # cover wrong token setting
        with self.assertRaises(ValueError):
            self.mixin_wrong.has_api_call()


class IntegrationPluginBaseTests(TestCase):
    """ Tests for IntegrationPluginBase """

    def setUp(self):
        self.plugin = IntegrationPluginBase()

        class SimpeIntegrationPluginBase(IntegrationPluginBase):
            PLUGIN_NAME = 'SimplePlugin'

        self.plugin_simple = SimpeIntegrationPluginBase()

        class NameIntegrationPluginBase(IntegrationPluginBase):
            PLUGIN_NAME = 'Aplugin'
            PLUGIN_SLUG = 'a'
            PLUGIN_TITLE = 'a titel'
            PUBLISH_DATE = "1111-11-11"
            AUTHOR = 'AA BB'
            DESCRIPTION = 'A description'
            VERSION = '1.2.3a'
            WEBSITE = 'http://aa.bb/cc'
            LICENSE = 'MIT'

        self.plugin_name = NameIntegrationPluginBase()

    def test_action_name(self):
        """check the name definition possibilities"""
        # plugin_name
        self.assertEqual(self.plugin.plugin_name(), '')
        self.assertEqual(self.plugin_simple.plugin_name(), 'SimplePlugin')
        self.assertEqual(self.plugin_name.plugin_name(), 'Aplugin')

        # slug
        self.assertEqual(self.plugin.slug, '')
        self.assertEqual(self.plugin_simple.slug, 'simpleplugin')
        self.assertEqual(self.plugin_name.slug, 'a')

        # human_name
        self.assertEqual(self.plugin.human_name, '')
        self.assertEqual(self.plugin_simple.human_name, 'SimplePlugin')
        self.assertEqual(self.plugin_name.human_name, 'a titel')

        # description
        self.assertEqual(self.plugin.description, '')
        self.assertEqual(self.plugin_simple.description, 'SimplePlugin')
        self.assertEqual(self.plugin_name.description, 'A description')

        # author
        self.assertEqual(self.plugin_name.author, 'AA BB')

        # pub_date
        self.assertEqual(self.plugin_name.pub_date, datetime(1111, 11, 11, 0, 0))

        # version
        self.assertEqual(self.plugin.version, None)
        self.assertEqual(self.plugin_simple.version, None)
        self.assertEqual(self.plugin_name.version, '1.2.3a')

        # website
        self.assertEqual(self.plugin.website, None)
        self.assertEqual(self.plugin_simple.website, None)
        self.assertEqual(self.plugin_name.website, 'http://aa.bb/cc')

        # license
        self.assertEqual(self.plugin.license, None)
        self.assertEqual(self.plugin_simple.license, None)
        self.assertEqual(self.plugin_name.license, 'MIT')
