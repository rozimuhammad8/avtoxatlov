from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("mahalla/create/", views.mahalla_create, name="mahalla_create"),
    path("mahalla/<int:pk>/", views.mahalla_detail, name="mahalla_detail"),
    path("mahalla/<int:pk>/token/", views.save_token, name="save_token"),
    path("mahalla/<int:pk>/upload/", views.upload_excel, name="upload_excel"),
    path("mahalla/<int:pk>/streets/", views.fetch_streets, name="fetch_streets"),
    path("mahalla/<int:pk>/fill/start/", views.start_fill, name="start_fill"),
    path("mahalla/<int:pk>/fill/stop/", views.stop_fill, name="stop_fill"),
    path("mahalla/<int:pk>/fill/status/", views.fill_status, name="fill_status"),
]
