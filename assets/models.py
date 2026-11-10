from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

PERMISSIONS = ("assets:write", "users:manage", "roles:manage", "reminders:manage")


class Role(models.Model):
    name = models.CharField(max_length=60, unique=True)
    permissions = models.JSONField(default=list)
    system = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("name"), name="role_name_case_insensitive")]
        ordering = ["-system", "name"]


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        role, _ = Role.objects.get_or_create(name="Administrator", defaults={"permissions": list(PERMISSIONS), "system": True})
        extra_fields.setdefault("role", role)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    avatar_data = models.TextField(blank=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users")
    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="user_email_case_insensitive")]


class Asset(models.Model):
    CATEGORIES = [(value, value) for value in ("Hardware", "Software", "License", "Subscription", "Certificate", "Other")]
    name = models.CharField(max_length=150)
    tag = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    vendor = models.CharField(max_length=100, blank=True)
    registration_date = models.DateField()
    expiry_date = models.DateField(db_index=True)
    renewal_date = models.DateField()
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assets", null=True, blank=True)
    notification_email = models.EmailField(blank=True)
    credentials_encrypted = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    asset_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    renewal_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    depreciation_acquisition_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    depreciation_salvage_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    depreciation_useful_life_months = models.PositiveSmallIntegerField(null=True, blank=True)
    depreciation_method = models.CharField(max_length=32, choices=[
        ("straight_line", "Straight-line"),
        ("double_declining_balance", "Double-declining balance"),
    ], blank=True)
    depreciation_start_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=10, choices=[("active", "Active"), ("retired", "Retired")], default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expiry_date", "id"]
        constraints = [
            models.UniqueConstraint(Lower("tag"), name="asset_tag_case_insensitive"),
            models.CheckConstraint(condition=models.Q(expiry_date__gte=models.F("registration_date")), name="expiry_after_registration"),
            models.CheckConstraint(condition=models.Q(renewal_date__gte=models.F("registration_date")), name="renewal_after_registration"),
            models.CheckConstraint(condition=models.Q(cost__gte=0), name="asset_nonnegative_cost"),
            models.CheckConstraint(condition=models.Q(asset_price__isnull=True) | models.Q(asset_price__gte=0), name="asset_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(renewal_price__isnull=True) | models.Q(renewal_price__gte=0), name="renewal_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(depreciation_acquisition_cost__isnull=True) | models.Q(depreciation_acquisition_cost__gte=0), name="depreciation_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(depreciation_salvage_value__isnull=True) | models.Q(depreciation_salvage_value__gte=0), name="depreciation_salvage_nonnegative"),
            models.CheckConstraint(condition=models.Q(depreciation_salvage_value__isnull=True) | models.Q(depreciation_acquisition_cost__isnull=False, depreciation_salvage_value__lte=models.F("depreciation_acquisition_cost")), name="depreciation_salvage_below_cost"),
            models.CheckConstraint(condition=models.Q(depreciation_useful_life_months__isnull=True) | models.Q(depreciation_useful_life_months__gte=1, depreciation_useful_life_months__lte=1200), name="depreciation_life_range"),
            models.CheckConstraint(condition=models.Q(category="Hardware") | models.Q(depreciation_acquisition_cost__isnull=True, depreciation_salvage_value__isnull=True, depreciation_useful_life_months__isnull=True, depreciation_method="", depreciation_start_date__isnull=True), name="depreciation_hardware_only"),
        ]


class ReminderDelivery(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="deliveries")
    expiry_date = models.DateField()
    threshold = models.PositiveSmallIntegerField()
    recipient = models.EmailField()
    state = models.CharField(max_length=10, choices=[("sent", "Sent"), ("failed", "Failed")])
    error = models.CharField(max_length=100, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempted_at = models.DateTimeField()

    class Meta:
        ordering = ["-attempted_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["asset", "expiry_date", "threshold", "recipient"], name="unique_reminder_delivery")]


class ReminderSettings(models.Model):
    enabled = models.BooleanField(default=True)
    smtp_config = models.TextField(blank=True)
    lock_token = models.CharField(max_length=64, blank=True)
    lock_until = models.DateTimeField(null=True, blank=True)


class SecurityAuditEvent(models.Model):
    ACTIONS = [(value, value.replace("_", " ").title()) for value in (
        "credential_viewed", "credential_created", "credential_updated", "credential_removed", "smtp_destination_updated",
    )]
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="security_audit_events")
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name="security_audit_events")
    action = models.CharField(max_length=32, choices=ACTIONS)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class SetupLock(models.Model):
    pass