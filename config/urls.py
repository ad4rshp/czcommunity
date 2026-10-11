"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, include
from core import views as core_views
from accounts import views as accounts_views
from profiles import views as profiles_views
from chat import views as chat_views

from django.http import JsonResponse
urlpatterns = [
    path('.well-known/appspecific/com.chrome.devtools.json', lambda r: JsonResponse({})),
    path('admin/', admin.site.urls),
    path('friends/', profiles_views.friends_list, name='friends'),
    path('settings/', profiles_views.profile_edit, name='global_settings'),
    path('dm/<str:username>/', chat_views.dm_view, name='dm_chat'),
    path('', core_views.home, name='home'),
    path('community/', core_views.community_dashboard, name='community'),
    path('community/create/', core_views.create_community, name='create_community'),
    path('community/edit/', core_views.community_settings, name='edit_dashboard'),
    path('community/settings/', core_views.community_settings, name='community_settings'),
    path('community/delete/', core_views.delete_community_view, name='delete_community'),
    path('community/<int:community_id>/leave/', core_views.leave_community, name='leave_community'),
    path('captcha/', include('captcha.urls')),
    path('tos/', core_views.tos, name='tos'),
    path('privacy/', core_views.privacy, name='privacy'),
    path('login/', accounts_views.login_view, name='login'),
    path('register/', accounts_views.register_view, name='register'),
    path('logout/', accounts_views.logout_view, name='logout'),
    path('community/chat/', include('chat.urls')),
    path('profiles/', include('profiles.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
