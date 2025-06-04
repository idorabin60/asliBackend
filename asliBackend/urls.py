"""
URL configuration for asliBackend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from django.urls import path, re_path
from users import views as user_views
from homeWork import views as hw_views
from chatBot import views as chatBot_views


urlpatterns = [
    path('admin/', admin.site.urls),
    re_path('login', user_views.login),
    re_path('test_token', user_views.test_token),
    re_path('signup', user_views.signup),
    re_path('user_homeworks', user_views.user_homeworks),
    re_path('all', hw_views.get_all_hw),
    path("homeworks/<int:homework_id>/", user_views.get_homework_by_id),
    path("get_teachers", user_views.get_all_teachers),
    path("chatbot/", chatBot_views.gpt_chat_view),
    path(
        'students_of_teacher/<int:teacher_id>/',
        user_views.students_of_teacher,
        name='students-of-teacher'
    ),
    path(
        'students/<int:student_id>/homeworks/',
        hw_views.student_homeworks,
        name='student-homeworks'
    ),
    path(
        'students/<int:student_id>/homeworks/<int:homework_id>/',
        hw_views.student_homework_detail,
        name='student-homework-detail'
    ),
    path(
        'users/<int:user_id>/',
        user_views.get_user_by_id,
        name='get-user-by-id'
    ),
    path(
        'homeworks/recent/',
        user_views.get_user_homework_from_last_two_weeks,
        name='homework-recent'

    )
]
