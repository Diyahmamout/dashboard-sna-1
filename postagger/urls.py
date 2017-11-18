from django.conf.urls import url

from . import api 

urlpatterns = [
	url(r'^fetch/(?P<userid>[a-zA-Z0-9]+)/$', api.on_fetch),
	url(r'^submit/$', api.on_submit)
]