from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("<int:conversation_id>/", views.room, name="room")
]