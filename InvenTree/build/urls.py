"""
URL lookup for Build app
"""

from django.conf.urls import url, include

from . import views

build_detail_urls = [
    url(r'^cancel/', views.BuildCancel.as_view(), name='build-cancel'),
    url(r'^delete/', views.BuildDelete.as_view(), name='build-delete'),

    url(r'^.*$', views.BuildDetail.as_view(), name='build-detail'),
]

build_urls = [

    url(r'^(?P<pk>\d+)/', include(build_detail_urls)),

    url(r'.*$', views.BuildIndex.as_view(), name='build-index'),
]
