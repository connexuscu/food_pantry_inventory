from django.shortcuts import HttpResponseRedirect
from django.urls import reverse_lazy, Resolver404
from django.shortcuts import redirect
from django.conf.urls import include, url
from django.conf import settings
from django.contrib.auth.middleware import PersistentRemoteUserMiddleware

import logging

from rest_framework.authtoken.models import Token
from allauth_2fa.middleware import BaseRequire2FAMiddleware, AllauthTwoFactorMiddleware

from InvenTree.urls import frontendpatterns
from common.models import InvenTreeSetting


logger = logging.getLogger("inventree")


class AuthRequiredMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        assert hasattr(request, 'user')

        # API requests are handled by the DRF library
        if request.path_info.startswith('/api/'):
            return self.get_response(request)

        if not request.user.is_authenticated:
            """
            Normally, a web-based session would use csrftoken based authentication.
            However when running an external application (e.g. the InvenTree app or Python library),
            we must validate the user token manually.
            """

            authorized = False

            # Allow static files to be accessed without auth
            # Important for e.g. login page
            if request.path_info.startswith('/static/'):
                authorized = True

            # Unauthorized users can access the login page
            elif request.path_info.startswith('/accounts/'):
                authorized = True

            elif 'Authorization' in request.headers.keys() or 'authorization' in request.headers.keys():
                auth = request.headers.get('Authorization', request.headers.get('authorization')).strip()

                if auth.lower().startswith('token') and len(auth.split()) == 2:
                    token_key = auth.split()[1]

                    # Does the provided token match a valid user?
                    try:
                        token = Token.objects.get(key=token_key)

                        # Provide the user information to the request
                        request.user = token.user
                        authorized = True

                    except Token.DoesNotExist:
                        logger.warning(f"Access denied for unknown token {token_key}")

            # No authorization was found for the request
            if not authorized:
                # A logout request will redirect the user to the login screen
                if request.path_info == reverse_lazy('account_logout'):
                    return HttpResponseRedirect(reverse_lazy('account_login'))

                path = request.path_info

                # List of URL endpoints we *do not* want to redirect to
                urls = [
                    reverse_lazy('account_login'),
                    reverse_lazy('account_logout'),
                    reverse_lazy('admin:login'),
                    reverse_lazy('admin:logout'),
                ]

                if path not in urls and not path.startswith('/api/'):
                    # Save the 'next' parameter to pass through to the login view

                    return redirect('%s?next=%s' % (reverse_lazy('account_login'), request.path))

        response = self.get_response(request)

        return response


url_matcher = url('', include(frontendpatterns))


class Check2FAMiddleware(BaseRequire2FAMiddleware):
    """check if user is required to have MFA enabled"""
    def require_2fa(self, request):
        # Superusers are require to have 2FA.
        try:
            if url_matcher.resolve(request.path[1:]):
                return InvenTreeSetting.get_setting('LOGIN_ENFORCE_MFA')
        except Resolver404:
            pass
        return False


class CustomAllauthTwoFactorMiddleware(AllauthTwoFactorMiddleware):
    """This function ensures only frontend code triggers the MFA auth cycle"""
    def process_request(self, request):
        try:
            if not url_matcher.resolve(request.path[1:]):
                super().process_request(request)
        except Resolver404:
            pass


class InvenTreeRemoteUserMiddleware(PersistentRemoteUserMiddleware):
    """
    Middleware to check if HTTP-header based auth is enabled and to set it up
    """
    header = settings.REMOTE_LOGIN_HEADER

    def process_request(self, request):
        if not settings.REMOTE_LOGIN:
            return

        return super().process_request(request)
