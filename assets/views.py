from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, render
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import exceptions, permissions, serializers
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView, exception_handler

from .models import PERMISSIONS, Asset, ReminderDelivery, ReminderSettings, Role, SecurityAuditEvent, SetupLock, User
from .serializers import AssetSerializer, LoginSerializer, PasswordSerializer, ProfileAvatarSerializer, ReminderDeliverySerializer, RoleSerializer, SetupSerializer, UserReadSerializer, UserWriteSerializer
from .email_config import SMTPConfigSerializer, configured, email_connection, public_config, save_config


def csrf_failure(request, reason=""):
    return JsonResponse({"error": "Session expired. Refresh the page and try again."}, status=403)


def api_exception_handler(error, context):
    if isinstance(error, IntegrityError):
        return Response({"error": "That email address, asset tag, or role name already exists"}, status=409)
    response = exception_handler(error, context)
    if response is None:
        return None
    if isinstance(error, exceptions.NotAuthenticated):
        response.status_code = 401

    def flatten(value):
        if isinstance(value, dict):
            return "; ".join(f"{key}: {flatten(item)}" for key, item in value.items())
        if isinstance(value, list):
            return "; ".join(flatten(item) for item in value)
        return str(value)

    response.data = {"error": flatten(response.data)}
    return response


class HasWorkspacePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        required = getattr(view, "workspace_permission", None)
        if request.method == "GET" and isinstance(view, (AssetsView, AssetDetailView)):
            required = None
        return request.user.is_authenticated and request.user.is_active and (not required or required in request.user.role.permissions)


@method_decorator(csrf_protect, name="dispatch")
class WorkspaceView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasWorkspacePermission]


def validated(serializer_class, request, instance=None):
    serializer = serializer_class(instance=instance, data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    return serializer


def session_payload(request):
    user = request.user if request.user.is_authenticated and request.user.is_active else None
    return {"user": UserReadSerializer(user).data if user else None, "csrfToken": get_token(request),
            "needsSetup": not User.objects.exists(), "setupTokenRequired": bool(settings.SETUP_TOKEN)}


class SessionView(WorkspaceView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(session_payload(request))


class ProfileView(WorkspaceView):
    def get(self, request):
        response = Response(UserReadSerializer(request.user).data)
        response["Cache-Control"] = "no-store, private"
        return response

    def put(self, request):
        serializer = validated(ProfileAvatarSerializer, request)
        request.user.avatar_data = serializer.validated_data["avatar"]
        request.user.save(update_fields=["avatar_data"])
        response = Response(UserReadSerializer(request.user).data)
        response["Cache-Control"] = "no-store, private"
        return response


class SetupView(WorkspaceView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        if User.objects.exists():
            return Response({"error": "Administrator account already exists"}, status=409)
        data = validated(SetupSerializer, request).validated_data
        if not settings.DEBUG and not settings.SETUP_TOKEN:
            raise exceptions.PermissionDenied("A SETUP_TOKEN must be configured for production setup")
        if settings.SETUP_TOKEN and not constant_time_compare(data.get("setupToken", ""), settings.SETUP_TOKEN):
            raise exceptions.PermissionDenied("Invalid setup token")
        with transaction.atomic():
            SetupLock.objects.filter(pk=1).update(id=F("id"))
            if User.objects.exists():
                return Response({"error": "Administrator account already exists"}, status=409)
            role = Role.objects.get(name="Administrator", system=True)
            user = User.objects.create_user(name=data["name"], email=data["email"], password=data["password"], role=role)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(session_payload(request))


class LoginView(WorkspaceView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        data = validated(LoginSerializer, request).validated_data
        user = authenticate(request, email=data["email"].strip().lower(), password=data["password"])
        if not user:
            return Response({"error": "Email or password is incorrect"}, status=401)
        login(request, user)
        return Response(session_payload(request))


class LogoutView(WorkspaceView):
    def post(self, request):
        logout(request)
        return Response({"ok": True})


class PasswordView(WorkspaceView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        data = validated(PasswordSerializer, request).validated_data
        if not request.user.check_password(data["currentPassword"]):
            raise exceptions.ValidationError("Current password is incorrect")
        request.user.set_password(data["password"])
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)
        return Response(session_payload(request))


class AssetsView(WorkspaceView):
    workspace_permission = "assets:write"

    def get(self, request):
        return Response(AssetSerializer(Asset.objects.select_related("owner").all(), many=True).data)

    def post(self, request):
        serializer = validated(AssetSerializer, request)
        asset = serializer.save()
        if "credentials" in serializer.validated_data:
            SecurityAuditEvent.objects.create(actor=request.user, asset=asset, action="credential_created")
        return Response(serializer.data, status=201)


class AssetDetailView(WorkspaceView):
    workspace_permission = "assets:write"

    def put(self, request, pk):
        asset = get_object_or_404(Asset, pk=pk)
        had_credentials = bool(asset.credentials_encrypted)
        serializer = validated(AssetSerializer, request, asset)
        asset = serializer.save()
        if "credentials" in serializer.validated_data:
            SecurityAuditEvent.objects.create(actor=request.user, asset=asset,
                                              action="credential_updated" if had_credentials else "credential_created")
        return Response(serializer.data)

    def delete(self, request, pk):
        get_object_or_404(Asset, pk=pk).delete()
        return Response({"ok": True})


class AssetCredentialsView(WorkspaceView):
    def credential_asset(self, request, pk, write=False):
        asset = get_object_or_404(Asset, pk=pk)
        manager = "assets:write" in request.user.role.permissions
        if not manager and (write or asset.owner_id != request.user.pk):
            raise exceptions.PermissionDenied("Only asset managers and the assigned user can view these credentials")
        return asset

    def get(self, request, pk):
        from .credentials import decrypt_credentials

        asset = self.credential_asset(request, pk)
        credentials = decrypt_credentials(asset)
        SecurityAuditEvent.objects.create(actor=request.user, asset=asset, action="credential_viewed")
        response = Response(credentials)
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        return response

    def put(self, request, pk):
        from .credentials import CredentialSerializer, encrypt_credentials

        asset = self.credential_asset(request, pk, write=True)
        data = validated(CredentialSerializer, request).validated_data
        action = "credential_updated" if asset.credentials_encrypted else "credential_created"
        asset.credentials_encrypted = encrypt_credentials(data, asset)
        asset.save(update_fields=["credentials_encrypted"])
        SecurityAuditEvent.objects.create(actor=request.user, asset=asset, action=action)
        return Response({"ok": True})

    def delete(self, request, pk):
        asset = self.credential_asset(request, pk, write=True)
        asset.credentials_encrypted = ""
        asset.save(update_fields=["credentials_encrypted"])
        SecurityAuditEvent.objects.create(actor=request.user, asset=asset, action="credential_removed")
        return Response({"ok": True})


class DirectoryView(WorkspaceView):
    def get(self, request):
        return Response(list(User.objects.filter(is_active=True).order_by("name").values("id", "name", "email")))


class UsersView(WorkspaceView):
    workspace_permission = "users:manage"

    def get(self, request):
        return Response(UserReadSerializer(User.objects.select_related("role").order_by("name"), many=True).data)

    def post(self, request):
        serializer = validated(UserWriteSerializer, request)
        user = serializer.save()
        return Response(UserReadSerializer(user).data, status=201)


class UserDetailView(WorkspaceView):
    workspace_permission = "users:manage"

    def put(self, request, pk):
        with transaction.atomic():
            SetupLock.objects.filter(pk=1).update(id=F("id"))
            user = get_object_or_404(User.objects.select_related("role"), pk=pk)
            serializer = validated(UserWriteSerializer, request, user)
            user = serializer.save()
        return Response(UserReadSerializer(user).data)


class RoleOptionsView(WorkspaceView):
    workspace_permission = "users:manage"

    def get(self, request):
        return Response(list(Role.objects.order_by("name").values("id", "name")))


class RolesView(WorkspaceView):
    workspace_permission = "roles:manage"

    def get(self, request):
        return Response(RoleSerializer(Role.objects.all(), many=True).data)

    def post(self, request):
        serializer = validated(RoleSerializer, request)
        serializer.save()
        return Response(serializer.data, status=201)


class RoleDetailView(WorkspaceView):
    workspace_permission = "roles:manage"

    def get_mutable_role(self, pk):
        role = get_object_or_404(Role, pk=pk)
        if role.system:
            raise exceptions.ValidationError("Built-in roles cannot be modified or deleted")
        return role

    def put(self, request, pk):
        serializer = validated(RoleSerializer, request, self.get_mutable_role(pk))
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        role = self.get_mutable_role(pk)
        if role.users.exists():
            raise exceptions.ValidationError("Reassign users before deleting this role")
        role.delete()
        return Response({"ok": True})


class ReminderSettingsSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()


class RemindersView(WorkspaceView):
    workspace_permission = "reminders:manage"

    def get(self, request):
        from .reminders import reminder_running

        options = ReminderSettings.objects.get(pk=1)
        return Response({"enabled": options.enabled, "configured": configured(),
                         "running": reminder_running(options), "schedule": "Daily at 08:00 UTC (scheduled task)",
                         "thresholds": [30, 15, 10, 5],
                         "deliveries": ReminderDeliverySerializer(ReminderDelivery.objects.select_related("asset")[:200], many=True).data})

    def put(self, request):
        data = validated(ReminderSettingsSerializer, request).validated_data
        ReminderSettings.objects.filter(pk=1).update(enabled=data["enabled"])
        return Response({"ok": True})


class RunRemindersView(WorkspaceView):
    workspace_permission = "reminders:manage"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "reminder"

    def post(self, request):
        from .reminders import send_reminders

        if not configured():
            raise exceptions.ValidationError("Configure SMTP before sending reminders")
        result = send_reminders()
        return Response(result, status=409 if result.get("skipped") == "already-running" else 200)


class EmailConfigView(WorkspaceView):
    workspace_permission = "reminders:manage"

    def get(self, request):
        response = Response(public_config())
        response["Cache-Control"] = "no-store"
        return response

    def put(self, request):
        data = validated(SMTPConfigSerializer, request).validated_data
        save_config(data)
        SecurityAuditEvent.objects.create(actor=request.user, action="smtp_destination_updated",
                                          metadata={"host": data["host"], "port": data["port"]})
        return Response({"ok": True})


class TestEmailSerializer(serializers.Serializer):
    recipient = serializers.EmailField(max_length=254)


class TestEmailView(WorkspaceView):
    workspace_permission = "reminders:manage"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "reminder"

    def post(self, request):
        from django.core.mail import EmailMessage

        data = validated(TestEmailSerializer, request).validated_data
        if not configured():
            raise exceptions.ValidationError("Save SMTP settings before sending a test email")
        try:
            connection, sender = email_connection()
            accepted = EmailMessage("Lifecycle: test email", "Your IT asset reminder email configuration is working.",
                                    sender, [data["recipient"]], connection=connection).send(fail_silently=False)
            if accepted != 1:
                raise RuntimeError("Not accepted")
        except Exception:
            return Response({"error": "Test delivery failed. Check the SMTP host, port, encryption, credentials, and provider permissions."}, status=400)
        return Response({"ok": True, "message": "Test email accepted by the mail server. Check your inbox and spam folder."})


def frontend(request):
    if (settings.BASE_DIR / "dist" / "index.html").exists():
        return render(request, "index.html")
    return JsonResponse({"error": "Run npm run build or open the Vite frontend at http://localhost:5173"}, status=503)


def not_found(request, exception=None):
    return JsonResponse({"error": "Not found"}, status=404)


def server_error(request):
    return JsonResponse({"error": "Unable to complete the request"}, status=500)