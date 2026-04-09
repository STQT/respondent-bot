from django.urls import path

from apps.polls_webapp import views


app_name = "polls_webapp"


urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login, name="login"),
    path("auth/telegram/", views.telegram_auth, name="telegram_auth"),
    path("logout/", views.logout_view, name="logout"),
    path("billing/", views.billing, name="billing"),
    path("polls/", views.poll_list, name="poll_list"),
    path("polls/new/", views.poll_create, name="poll_create"),
    path("polls/<uuid:poll_uuid>/edit/", views.poll_edit, name="poll_edit"),
    path("polls/<uuid:poll_uuid>/preview/", views.poll_preview, name="poll_preview"),
    path("polls/<uuid:poll_uuid>/publish/", views.poll_publish, name="poll_publish"),
    path("polls/<uuid:poll_uuid>/analytics/", views.poll_analytics, name="poll_analytics"),
    path("polls/<uuid:poll_uuid>/export/start/", views.poll_export_start, name="poll_export_start"),
    path("polls/<uuid:poll_uuid>/questions/new/", views.question_create, name="question_create"),
    path("polls/<uuid:poll_uuid>/questions/<int:question_id>/edit/", views.question_edit, name="question_edit"),
    path(
        "polls/<uuid:poll_uuid>/questions/<int:question_id>/choices/new/",
        views.choice_create,
        name="choice_create",
    ),
    path(
        "polls/<uuid:poll_uuid>/questions/<int:question_id>/choices/<int:choice_id>/delete/",
        views.choice_delete,
        name="choice_delete",
    ),
]

