import logging

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required

from django.core.urlresolvers import reverse

from django.http import HttpResponseRedirect
from django.shortcuts import render

from django.views.decorators.http import require_http_methods

from vocab.forms import RegisterForm

logger = logging.getLogger(__name__)

@require_http_methods(["GET"])
def home(request):
    return render(request, 'home.html', {'form': RegisterForm()})

@login_required()
@require_http_methods(["GET"])
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse('home'))