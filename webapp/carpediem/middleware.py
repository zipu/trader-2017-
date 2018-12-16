from django.http import HttpResponseRedirect
from django.conf import settings
from re import compile

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    # One-time configuration and initialization.
    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        assert hasattr(request, 'user'), "The Login Required middleware\
             requires authentication middleware to be installed. Edit your\
             MIDDLEWARE_CLASSES setting to insert\
             'django.contrib.auth.middlware.AuthenticationMiddleware'. If that doesn't\
             work, ensure your TEMPLATE_CONTEXT_PROCESSORS setting includes\
             'django.core.context_processors.auth'."
        if not request.user.is_authenticated():
            path = request.path_info.lstrip('/')
            if path == 'login/':
                return self.get_response(request)
            else:
                return HttpResponseRedirect(settings.LOGIN_URL) 
        else:
            return self.get_response(request)


