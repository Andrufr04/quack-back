from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from users.views import ChangePasswordView, EmailChangeConfirmView, EmailChangeRequestView, MyTokenObtainPairView, PasswordResetConfirmView, PasswordResetRequestView

urlpatterns = [
    path('superplusadminmaxverstappen/', admin.site.urls),
    path('api/login/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/users/', include('users.urls')),
    path('api/profiles/', include('profiles.urls')),
    path('api/education/', include('education.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('api/password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('api/change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('api/email-change-request/', EmailChangeRequestView.as_view(), name='email_change_request'),
    path('api/email-change-confirm/', EmailChangeConfirmView.as_view(), name='email_change_confirm'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)