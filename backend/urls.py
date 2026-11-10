from django.http import JsonResponse
from django.urls import path

from assets import views

urlpatterns = [
	path("api/health", lambda request: JsonResponse({"ok": True, "backend": "Django"})),
	path("api/auth/session", views.SessionView.as_view()),
	path("api/profile", views.ProfileView.as_view()),
	path("api/auth/setup", views.SetupView.as_view()),
	path("api/auth/login", views.LoginView.as_view()),
	path("api/auth/logout", views.LogoutView.as_view()),
	path("api/auth/password", views.PasswordView.as_view()),
	path("api/assets", views.AssetsView.as_view()),
	path("api/assets/<int:pk>", views.AssetDetailView.as_view()),
	path("api/assets/<int:pk>/credentials", views.AssetCredentialsView.as_view()),
	path("api/directory", views.DirectoryView.as_view()),
	path("api/users", views.UsersView.as_view()),
	path("api/users/<int:pk>", views.UserDetailView.as_view()),
	path("api/role-options", views.RoleOptionsView.as_view()),
	path("api/roles", views.RolesView.as_view()),
	path("api/roles/<int:pk>", views.RoleDetailView.as_view()),
	path("api/reminders", views.RemindersView.as_view()),
	path("api/reminders/run", views.RunRemindersView.as_view()),
	path("api/reminders/email", views.EmailConfigView.as_view()),
	path("api/reminders/test-email", views.TestEmailView.as_view()),
	path("", views.frontend),
]
handler404 = views.not_found
handler500 = views.server_error