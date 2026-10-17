from django.urls import path
from . import views

urlpatterns = [
    path('members/', views.member_directory, name='members'),
    path('members/directory/', views.member_directory, name='member_directory'),
    path('directory/', views.member_directory, name='member_directory_alias'),
    path('settings/profile/', views.profile_edit, name='profile_edit'),
    path('edit/', views.profile_edit, name='profile_edit_alias'),
    path('settings/', views.profile_edit, name='profile_settings_alias'),
    path('api/check-username/', views.check_username_api, name='check_username_api'),
    path('<str:username>/', views.profile_detail, name='profile'),
    path('<str:username>/card/', views.profile_card_fragment, name='profile_card_fragment'),
    path('action/send-request/', views.send_friend_request_by_username, name='send_friend_request_by_username'),
    path('status/update/', views.quick_status_update, name='quick_status_update'),
    path('api/social/clear-ping/', views.clear_social_ping, name='clear_social_ping'),
    path('api/user-id/', views.get_user_id_api, name='get_user_id_api'),
    path('<str:username>/friend/', views.handle_friend_action, name='friend_action'),
]
