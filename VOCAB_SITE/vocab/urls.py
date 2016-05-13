"""vocab URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.views.generic import RedirectView

from . import views

# app_name = 'vocab'

urlpatterns = [
    # redirect for just /vocab
    url(r'^$', RedirectView.as_view(url='/')),    

    url(r'^adminIRIs$', views.adminIRIs, name="adminIRIs"),
    url(r'^createIRI$', views.createIRI, name="createIRI"),
    url(r'^createUser$', views.createUser, name="createUser"),
    url(r'^searchResults$', views.searchResults, name="searchResults"),
    url(r'^iriCreationResults$', views.iriCreationResults, name="iriCreationResults"),
    url(r'^userProfile$', views.userProfile, name="userProfile"),
    url(r'^createVocabulary$', views.createVocabulary, name="createVocabulary"),
    url(r'^downloadCSV$', views.downloadCSV, name="downloadCSV"),
    # url(r'^vocabulary/(?P<vocab_name>[\w-]+)$', views.vocabulary, name="vocabulary"),
]
