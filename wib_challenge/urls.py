"""
URL configuration for wib_challenge project.
The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from debug_toolbar.toolbar import debug_toolbar_urls
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from core.views import health_check

urlpatterns = [
    path('administration/', admin.site.urls),
    path('api/', include(('core.urls', 'core'), namespace='core')),
    path('api/jobs/', include(('jobs.urls', 'jobs'), namespace='jobs')),
    path('api/learnings/', include(('learning.urls', 'jobs'), namespace='learning')),
    path('api/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('api/', include(('questions.urls', 'questions'), namespace='questions')),
    path('api/', include(('candidates.urls', 'candidates'), namespace='candidates')),
    path('api/', include(('evaluations.urls', 'evaluations'), namespace='evaluations')),
    path('api/', include(('organizations.urls', 'organizations'), namespace='organizations')),
    path('health/', health_check, name='health_check'),
]

if settings.DEBUG:
    urlpatterns = [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/redoc',
             SpectacularRedocView.as_view(url_name='schema'), name='redoc-ui'),
        re_path('^api/docs(/swagger)?/$',
                SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        *debug_toolbar_urls(),
        path('api-auth/', include('rest_framework.urls'), name='rest_framework'),
        *urlpatterns, *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
        *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
    ]
