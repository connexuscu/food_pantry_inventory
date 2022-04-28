"""
Top-level URL lookup for InvenTree application.

Passes URL lookup downstream to each app as required.
"""

from django.conf.urls import url, include
from django.urls import path
from django.contrib import admin

from company.urls import company_urls
from company.urls import manufacturer_part_urls
from company.urls import supplier_part_urls

from common.urls import common_urls
from part.urls import part_urls
from stock.urls import stock_urls
from build.urls import build_urls
from order.urls import order_urls
from plugin.urls import get_plugin_urls

from barcodes.api import barcode_api_urls
from common.api import common_api_urls, settings_api_urls
from part.api import part_api_urls, bom_api_urls
from company.api import company_api_urls
from stock.api import stock_api_urls
from build.api import build_api_urls
from order.api import order_api_urls
from label.api import label_api_urls
from report.api import report_api_urls
from plugin.api import plugin_api_urls

from django.conf import settings
from django.conf.urls.static import static

from django.views.generic.base import RedirectView
from rest_framework.documentation import include_docs_urls

from .views import auth_request
from .views import IndexView, SearchView, DatabaseStatsView
from .views import SettingsView, EditUserView, SetPasswordView, CustomEmailView, CustomConnectionsView, CustomPasswordResetFromKeyView
from .views import CustomSessionDeleteView, CustomSessionDeleteOtherView
from .views import CurrencyRefreshView
from .views import AppearanceSelectView, SettingCategorySelectView
from .views import DynamicJsView
from .views import NotificationsView

from .api import InfoView, NotFoundView
from .api import ActionPluginView

from users.api import user_urls

admin.site.site_header = "InvenTree Admin"

apipatterns = []

if settings.PLUGINS_ENABLED:
    apipatterns.append(
        url(r'^plugin/', include(plugin_api_urls))
    )

apipatterns += [
    url(r'^barcode/', include(barcode_api_urls)),
    url(r'^settings/', include(settings_api_urls)),
    url(r'^part/', include(part_api_urls)),
    url(r'^bom/', include(bom_api_urls)),
    url(r'^company/', include(company_api_urls)),
    url(r'^stock/', include(stock_api_urls)),
    url(r'^build/', include(build_api_urls)),
    url(r'^order/', include(order_api_urls)),
    url(r'^label/', include(label_api_urls)),
    url(r'^report/', include(report_api_urls)),

    # User URLs
    url(r'^user/', include(user_urls)),

    # Plugin endpoints
    url(r'^action/', ActionPluginView.as_view(), name='api-action-plugin'),

    # Webhook enpoint
    path('', include(common_api_urls)),

    # InvenTree information endpoint
    url(r'^$', InfoView.as_view(), name='api-inventree-info'),

    # Unknown endpoint
    url(r'^.*$', NotFoundView.as_view(), name='api-404'),
]

settings_urls = [

    url(r'^i18n/?', include('django.conf.urls.i18n')),

    url(r'^appearance/?', AppearanceSelectView.as_view(), name='settings-appearance'),
    url(r'^currencies-refresh/', CurrencyRefreshView.as_view(), name='settings-currencies-refresh'),

    url(r'^category/', SettingCategorySelectView.as_view(), name='settings-category'),

    # Catch any other urls
    url(r'^.*$', SettingsView.as_view(template_name='InvenTree/settings/settings.html'), name='settings'),
]

notifications_urls = [

    # Catch any other urls
    url(r'^.*$', NotificationsView.as_view(), name='notifications'),
]

# These javascript files are served "dynamically" - i.e. rendered on demand
dynamic_javascript_urls = [
    url(r'^calendar.js', DynamicJsView.as_view(template_name='js/dynamic/calendar.js'), name='calendar.js'),
    url(r'^nav.js', DynamicJsView.as_view(template_name='js/dynamic/nav.js'), name='nav.js'),
    url(r'^settings.js', DynamicJsView.as_view(template_name='js/dynamic/settings.js'), name='settings.js'),
]

# These javascript files are pased through the Django translation layer
translated_javascript_urls = [
    url(r'^api.js', DynamicJsView.as_view(template_name='js/translated/api.js'), name='api.js'),
    url(r'^attachment.js', DynamicJsView.as_view(template_name='js/translated/attachment.js'), name='attachment.js'),
    url(r'^barcode.js', DynamicJsView.as_view(template_name='js/translated/barcode.js'), name='barcode.js'),
    url(r'^bom.js', DynamicJsView.as_view(template_name='js/translated/bom.js'), name='bom.js'),
    url(r'^build.js', DynamicJsView.as_view(template_name='js/translated/build.js'), name='build.js'),
    url(r'^company.js', DynamicJsView.as_view(template_name='js/translated/company.js'), name='company.js'),
    url(r'^filters.js', DynamicJsView.as_view(template_name='js/translated/filters.js'), name='filters.js'),
    url(r'^forms.js', DynamicJsView.as_view(template_name='js/translated/forms.js'), name='forms.js'),
    url(r'^helpers.js', DynamicJsView.as_view(template_name='js/translated/helpers.js'), name='helpers.js'),
    url(r'^label.js', DynamicJsView.as_view(template_name='js/translated/label.js'), name='label.js'),
    url(r'^model_renderers.js', DynamicJsView.as_view(template_name='js/translated/model_renderers.js'), name='model_renderers.js'),
    url(r'^modals.js', DynamicJsView.as_view(template_name='js/translated/modals.js'), name='modals.js'),
    url(r'^order.js', DynamicJsView.as_view(template_name='js/translated/order.js'), name='order.js'),
    url(r'^part.js', DynamicJsView.as_view(template_name='js/translated/part.js'), name='part.js'),
    url(r'^report.js', DynamicJsView.as_view(template_name='js/translated/report.js'), name='report.js'),
    url(r'^search.js', DynamicJsView.as_view(template_name='js/translated/search.js'), name='search.js'),
    url(r'^stock.js', DynamicJsView.as_view(template_name='js/translated/stock.js'), name='stock.js'),
    url(r'^plugin.js', DynamicJsView.as_view(template_name='js/translated/plugin.js'), name='plugin.js'),
    url(r'^tables.js', DynamicJsView.as_view(template_name='js/translated/tables.js'), name='tables.js'),
    url(r'^table_filters.js', DynamicJsView.as_view(template_name='js/translated/table_filters.js'), name='table_filters.js'),
    url(r'^notification.js', DynamicJsView.as_view(template_name='js/translated/notification.js'), name='notification.js'),
]

backendpatterns = [
    # "Dynamic" javascript files which are rendered using InvenTree templating.
    url(r'^js/dynamic/', include(dynamic_javascript_urls)),
    url(r'^js/i18n/', include(translated_javascript_urls)),

    url(r'^auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^auth/?', auth_request),

    url(r'^api/', include(apipatterns)),
    url(r'^api-doc/', include_docs_urls(title='InvenTree API')),

    # 3rd party endpoints
    url(r'^markdownx/', include('markdownx.urls')),
]

frontendpatterns = [
    url(r'^part/', include(part_urls)),
    url(r'^manufacturer-part/', include(manufacturer_part_urls)),
    url(r'^supplier-part/', include(supplier_part_urls)),

    url(r'^common/', include(common_urls)),

    url(r'^stock/', include(stock_urls)),

    url(r'^company/', include(company_urls)),
    url(r'^order/', include(order_urls)),

    url(r'^build/', include(build_urls)),

    url(r'^settings/', include(settings_urls)),

    url(r'^notifications/', include(notifications_urls)),

    url(r'^edit-user/', EditUserView.as_view(), name='edit-user'),
    url(r'^set-password/', SetPasswordView.as_view(), name='set-password'),

    url(r'^index/', IndexView.as_view(), name='index'),
    url(r'^search/', SearchView.as_view(), name='search'),
    url(r'^stats/', DatabaseStatsView.as_view(), name='stats'),

    # admin sites
    url(f'^{settings.INVENTREE_ADMIN_URL}/error_log/', include('error_report.urls')),
    url(f'^{settings.INVENTREE_ADMIN_URL}/shell/', include('django_admin_shell.urls')),
    url(f'^{settings.INVENTREE_ADMIN_URL}/', admin.site.urls, name='inventree-admin'),

    # DB user sessions
    url(r'^accounts/sessions/other/delete/$', view=CustomSessionDeleteOtherView.as_view(), name='session_delete_other', ),
    url(r'^accounts/sessions/(?P<pk>\w+)/delete/$', view=CustomSessionDeleteView.as_view(), name='session_delete', ),

    # Single Sign On / allauth
    # overrides of urlpatterns
    url(r'^accounts/email/', CustomEmailView.as_view(), name='account_email'),
    url(r'^accounts/social/connections/', CustomConnectionsView.as_view(), name='socialaccount_connections'),
    url(r"^accounts/password/reset/key/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$", CustomPasswordResetFromKeyView.as_view(), name="account_reset_password_from_key"),
    url(r'^accounts/', include('allauth_2fa.urls')),    # MFA support
    url(r'^accounts/', include('allauth.urls')),        # included urlpatterns
]

# Append custom plugin URLs (if plugin support is enabled)
if settings.PLUGINS_ENABLED:
    frontendpatterns.append(get_plugin_urls())

urlpatterns = [
    url('', include(frontendpatterns)),
    url('', include(backendpatterns)),
]

# Server running in "DEBUG" mode?
if settings.DEBUG:
    # Static file access
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Media file access
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Debug toolbar access (only allowed in DEBUG mode)
    if 'debug_toolbar' in settings.INSTALLED_APPS:  # pragma: no cover
        import debug_toolbar
        urlpatterns = [
            path('__debug/', include(debug_toolbar.urls)),
        ] + urlpatterns

# Send any unknown URLs to the parts page
urlpatterns += [url(r'^.*$', RedirectView.as_view(url='/index/', permanent=False), name='index')]
