from decimal import Decimal
import base64
import binascii
import io
import warnings

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import PERMISSIONS, Asset, ReminderDelivery, Role, User


def validate_new_password(value, user=None):
    if len(value) > 128:
        raise serializers.ValidationError("Password must be at most 128 characters")
    try:
        password_validation.validate_password(value, user)
    except DjangoValidationError as error:
        raise serializers.ValidationError(error.messages) from error
    return value


class UserReadSerializer(serializers.ModelSerializer):
    role_id = serializers.IntegerField(read_only=True)
    role = serializers.CharField(source="role.name", read_only=True)
    permissions = serializers.JSONField(source="role.permissions", read_only=True)
    active = serializers.BooleanField(source="is_active", read_only=True)
    avatar = serializers.CharField(source="avatar_data", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "email", "role_id", "role", "permissions", "active", "avatar"]


class ProfileAvatarSerializer(serializers.Serializer):
    avatar = serializers.CharField(required=True, allow_blank=True, allow_null=True, max_length=7_000_000)

    def validate_avatar(self, value):
        if value in (None, ""):
            return ""
        header, separator, encoded = value.partition(",")
        formats = {"data:image/jpeg;base64": "JPEG", "data:image/png;base64": "PNG", "data:image/webp;base64": "WEBP"}
        image_format = formats.get(header.lower())
        if not separator or not image_format or not encoded:
            raise serializers.ValidationError("Choose a JPEG, PNG, or WebP image")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError("The uploaded image data is invalid") from None
        if not image_bytes or len(image_bytes) > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image must be smaller than 5 MB")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(image_bytes)) as source:
                    if source.format != image_format:
                        raise serializers.ValidationError("The image content does not match its file type")
                    source.verify()
                with Image.open(io.BytesIO(image_bytes)) as source:
                    if source.width > 10000 or source.height > 10000:
                        raise serializers.ValidationError("Image dimensions are too large")
                    image = ImageOps.exif_transpose(source).convert("RGB")
                    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.save(output, format="JPEG", quality=85, optimize=True)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise serializers.ValidationError("The uploaded file is not a safe, valid image") from None
        return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")


class UserWriteSerializer(serializers.ModelSerializer):
    role_id = serializers.PrimaryKeyRelatedField(source="role", queryset=Role.objects.all())
    active = serializers.BooleanField(source="is_active", required=False, default=True)
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, max_length=128)
    name = serializers.CharField(min_length=2, max_length=100)

    class Meta:
        model = User
        fields = ["name", "email", "role_id", "active", "password"]

    def validate_email(self, value):
        value = value.strip().lower()
        query = User.objects.filter(email__iexact=value)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("This email address already exists")
        return value

    def validate(self, attrs):
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "An initial password is required"})
        if "password" in attrs:
            candidate = User(name=attrs.get("name", ""), email=attrs.get("email", ""))
            validate_new_password(attrs["password"], candidate)
        if self.instance and self.instance.is_active and self.instance.role.system and self.instance.role.name == "Administrator":
            if not attrs.get("is_active", True) or attrs["role"].pk != self.instance.role_id:
                if User.objects.filter(role=self.instance.role, is_active=True).count() <= 1:
                    raise serializers.ValidationError("At least one active administrator must remain")
        return attrs

    def create(self, validated_data):
        raw_password = validated_data.pop("password")
        return User.objects.create_user(password=raw_password, **validated_data)

    def update(self, instance, validated_data):
        raw_password = validated_data.pop("password", None)
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        if raw_password:
            instance.set_password(raw_password)
        instance.save()
        return instance


class SetupSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=100)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128, trim_whitespace=False)
    setupToken = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    PERSONAL_EMAIL_DOMAINS = frozenset({
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "ymail.com", "rocketmail.com",
        "outlook.com", "hotmail.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
        "aol.com", "proton.me", "protonmail.com", "pm.me", "gmx.com", "gmx.net", "mail.com",
        "yandex.com", "yandex.ru", "qq.com", "163.com", "126.com", "hey.com", "fastmail.com",
    })

    def validate_email(self, value):
        normalized = value.strip().lower()
        domain = normalized.rsplit("@", 1)[-1].rstrip(".")
        if any(domain == personal or domain.endswith(f".{personal}") for personal in self.PERSONAL_EMAIL_DOMAINS):
            raise serializers.ValidationError("Use your organization's email address, not a personal email provider.")
        return normalized

    def validate(self, attrs):
        attrs["email"] = attrs["email"].strip().lower()
        validate_new_password(attrs["password"], User(name=attrs["name"], email=attrs["email"]))
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class PasswordSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(max_length=128, trim_whitespace=False)
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_password(self, value):
        return validate_new_password(value, self.context["request"].user)


class RoleSerializer(serializers.ModelSerializer):
    name = serializers.CharField(min_length=2, max_length=60)
    permissions = serializers.ListField(child=serializers.ChoiceField(choices=PERMISSIONS), max_length=4)

    class Meta:
        model = Role
        fields = ["id", "name", "permissions", "system"]
        read_only_fields = ["id", "system"]

    def validate_name(self, value):
        query = Role.objects.filter(name__iexact=value)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("This role name already exists")
        return value

    def validate_permissions(self, value):
        return list(dict.fromkeys(value))


from .credentials import CredentialSerializer, encrypt_credentials


class AssetSerializer(serializers.ModelSerializer):
    credentials = CredentialSerializer(write_only=True, required=False)
    has_credentials = serializers.SerializerMethodField()
    owner_id = serializers.PrimaryKeyRelatedField(source="owner", queryset=User.objects.filter(is_active=True), allow_null=True, required=False)
    owner_name = serializers.CharField(source="owner.name", read_only=True, default=None)
    owner_email = serializers.EmailField(source="owner.email", read_only=True, default=None)
    name = serializers.CharField(min_length=2, max_length=150)
    cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("1000000000"), coerce_to_string=False, required=False)
    asset_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("1000000000"), coerce_to_string=False, required=False, allow_null=True)
    renewal_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("1000000000"), coerce_to_string=False, required=False, allow_null=True)
    depreciation_acquisition_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("1000000000"), coerce_to_string=False, required=False, allow_null=True)
    depreciation_salvage_value = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("1000000000"), coerce_to_string=False, required=False, allow_null=True)
    depreciation_useful_life_months = serializers.IntegerField(min_value=1, max_value=1200, required=False, allow_null=True)
    depreciation_method = serializers.ChoiceField(choices=["straight_line", "double_declining_balance"], required=False, allow_blank=True)
    depreciation_start_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    class Meta:
        model = Asset
        fields = ["id", "name", "tag", "category", "vendor", "registration_date", "expiry_date", "renewal_date",
                  "owner_id", "owner_name", "owner_email", "notification_email", "cost", "asset_price", "renewal_price", "depreciation_acquisition_cost", "depreciation_salvage_value", "depreciation_useful_life_months", "depreciation_method", "depreciation_start_date", "notes", "status", "created_at", "credentials", "has_credentials"]
        read_only_fields = ["id", "created_at"]

    def get_has_credentials(self, asset):
        return bool(asset.credentials_encrypted)

    def create(self, validated_data):
        credentials = validated_data.pop("credentials", None)
        if credentials is not None:
            validated_data["credentials_encrypted"] = encrypt_credentials(credentials)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        credentials = validated_data.pop("credentials", None)
        if credentials is not None:
            validated_data["credentials_encrypted"] = encrypt_credentials(credentials, instance)
        if validated_data.get("category", instance.category) != "Hardware":
            validated_data.update({
                "depreciation_acquisition_cost": None,
                "depreciation_salvage_value": None,
                "depreciation_useful_life_months": None,
                "depreciation_method": "",
                "depreciation_start_date": None,
            })
        return super().update(instance, validated_data)

    def validate_tag(self, value):
        query = Asset.objects.filter(tag__iexact=value)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("This asset tag already exists")
        return value

    def validate(self, attrs):
        if attrs["expiry_date"] < attrs["registration_date"]:
            raise serializers.ValidationError({"expiry_date": "Expiry cannot precede registration"})
        if attrs["renewal_date"] < attrs["registration_date"]:
            raise serializers.ValidationError({"renewal_date": "Renewal cannot precede registration"})
        if attrs.get("status", "active") == "active" and not attrs.get("owner") and not attrs.get("notification_email"):
            raise serializers.ValidationError("Assign an owner or enter a notification email for reminders")
        depreciation_fields = ("depreciation_acquisition_cost", "depreciation_salvage_value", "depreciation_useful_life_months", "depreciation_method", "depreciation_start_date")
        category = attrs.get("category", self.instance.category if self.instance else None)
        provided_depreciation = any(field in attrs and attrs[field] is not None and attrs[field] != "" for field in depreciation_fields)
        if category != "Hardware" and provided_depreciation:
            raise serializers.ValidationError({"depreciation": "Depreciation fields are only available for Hardware assets"})
        if category == "Hardware":
            values = {field: attrs.get(field, getattr(self.instance, field, None) if self.instance else None) for field in depreciation_fields}
            configured = any(value is not None and value != "" for value in values.values())
            if configured:
                required = ("depreciation_acquisition_cost", "depreciation_useful_life_months", "depreciation_method", "depreciation_start_date")
                missing = [field for field in required if values[field] is None or values[field] == ""]
                if missing:
                    raise serializers.ValidationError({"depreciation": "Enter acquisition cost, useful life, method, and start date to configure depreciation"})
                salvage = values["depreciation_salvage_value"]
                acquisition = values["depreciation_acquisition_cost"]
                if salvage is not None and salvage > acquisition:
                    raise serializers.ValidationError({"depreciation_salvage_value": "Salvage value cannot exceed acquisition cost"})
                attrs.setdefault("depreciation_salvage_value", Decimal("0"))
        return attrs


class ReminderDeliverySerializer(serializers.ModelSerializer):
    asset_id = serializers.IntegerField(read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    asset_tag = serializers.CharField(source="asset.tag", read_only=True)

    class Meta:
        model = ReminderDelivery
        fields = ["id", "asset_id", "asset_name", "asset_tag", "expiry_date", "threshold", "recipient", "state", "error", "sent_at", "attempted_at"]