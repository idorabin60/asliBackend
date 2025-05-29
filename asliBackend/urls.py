# from django.contrib import admin
# from rest_framework.authtoken import views as token_views

from django.urls import path, re_path
from users import views as user_views

urlpatterns = [
    # path('admin/', admin.site.urls),
    # path('api-token-auth/', token_views.obtain_auth_token),

    re_path('login',       user_views.login),
    re_path('test_token',  user_views.test_token),
    re_path('signup',      user_views.signup),
    re_path('user_homeworks', user_views.user_homeworks),
]
