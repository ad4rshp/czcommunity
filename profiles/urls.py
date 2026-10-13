from django.urls import path
from . import views

urlpatterns = [
    path('members/', views.member_directory, name='members'),
    path('settings/profile/', views.profile_edit, name='profile_edit'),
    path('edit/', views.profile_edit, name='profile_edit_alias'),
    path('settings/', views.profile_edit, name='profile_settings_alias'),
    path('<str:username>/', views.profile_detail, name='profile'),
    path('<str:username>/card/', views.profile_card_fragment, name='profile_card_fragment'),
    path('action/send-request/', views.send_friend_request_by_username, name='send_friend_request_by_username'),
    path('status/update/', views.quick_status_update, name='quick_status_update'),
    path('<str:username>/friend/', views.handle_friend_action, name='friend_action'),
]
