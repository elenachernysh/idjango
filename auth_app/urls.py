from django.urls import path
from .views import LinkTokenView, AccessTokenView, AccountsView


app_name = "auth_app"

urlpatterns = [
    path('get_link_token/', LinkTokenView.as_view(), name='get_link_token'),
    path('get_access_token/', AccessTokenView.as_view(), name='get_access_token'),
    path('accounts/', AccountsView.as_view(), name='accounts'),
]
