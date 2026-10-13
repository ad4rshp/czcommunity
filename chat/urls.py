from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views
from . import upload_views

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('category/<int:category_id>/add-channel/', views.add_channel, name='add_channel'),
    path('category/<slug:category_slug>/add-channel/', views.add_channel, name='add_channel_slug'),
    path('category/<int:category_id>/manage/', views.manage_category, name='manage_category'),
    path('category/<slug:category_slug>/manage/', views.manage_category, name='manage_category_slug'),
    path('channel/<int:channel_id>/move/', csrf_exempt(views.move_channel), name='move_channel'),
    path('channel/<slug:channel_slug>/upload/', upload_views.upload_attachment, name='upload_attachment'),
    path('channel/<slug:channel_slug>/edit/', views.edit_channel, name='edit_channel'),
    path('channel/<slug:channel_slug>/delete/', views.delete_channel, name='delete_channel'),
    path('channel/<slug:channel_slug>/permissions/', views.get_channel_permissions, name='get_channel_permissions'),
    path('api/search/', views.search_messages, name='search_messages'),
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/read/', csrf_exempt(views.mark_notifications_read), name='mark_notifications_read'),
    path('<slug:channel_slug>/', views.chat_view, name='chat_channel'),
]
