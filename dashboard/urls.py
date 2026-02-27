from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('api/server-time/', views.server_time_api, name='server_time_api'),
    path('api/calendar/', views.calendar_data_api, name='calendar_data_api'),
    path('musik/', views.musik_list_view, name='musik_list'),
    path('musik/<int:pk>/hapus/', views.musik_delete_view, name='musik_delete'),
    path('jadwal/', views.jadwal_list_view, name='jadwal_list'),
    path('jadwal/tambah/', views.jadwal_create_view, name='jadwal_create'),
    path('jadwal/<int:pk>/edit/', views.jadwal_edit_view, name='jadwal_edit'),
    path('jadwal/<int:pk>/hapus/', views.jadwal_delete_view, name='jadwal_delete'),
    path('jadwal/<int:pk>/toggle/', views.jadwal_toggle_view, name='jadwal_toggle'),
    path('jadwal/grup/<path:nama>/edit/', views.jadwal_group_edit_view, name='jadwal_group_edit'),
    path('jadwal/grup/<path:nama>/hapus/', views.jadwal_group_delete_view, name='jadwal_group_delete'),
    path('jadwal/grup/<path:nama>/toggle/', views.jadwal_group_toggle_view, name='jadwal_group_toggle'),
    path('pengecualian/', views.pengecualian_list_view, name='pengecualian_list'),
    path('pengecualian/tambah/', views.pengecualian_create_view, name='pengecualian_create'),
    path('pengecualian/api/jadwal/', views.pengecualian_jadwal_api, name='pengecualian_jadwal_api'),
    path('pengecualian/<int:pk>/hapus/', views.pengecualian_delete_view, name='pengecualian_delete'),
    # Audio playback controls
    path('musik/<int:pk>/test/', views.musik_test_play_view, name='musik_test_play'),
    path('musik/stop/', views.musik_stop_play_view, name='musik_stop_play'),
    path('api/playback-status/', views.playback_status_api, name='playback_status_api'),
]
