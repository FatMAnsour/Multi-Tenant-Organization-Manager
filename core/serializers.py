from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Organization, Membership, Role, Item, AuditLog

User = get_user_model()


# --- Auth ---
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("email", "password", "full_name")

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


# --- Organization ---
class OrganizationCreateSerializer(serializers.Serializer):
    org_name = serializers.CharField(max_length=255, source="name")

    def create(self, validated_data):
        name = validated_data["name"]
        user = self.context["request"].user
        org = Organization.objects.create(name=name)
        Membership.objects.create(user=user, organization=org, role=Role.ADMIN)
        return org


class InviteUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[Role.MEMBER, Role.ADMIN])


class UserInOrgSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role")

    def get_role(self, obj):
        membership = getattr(obj, "_membership_role", None)
        return membership or ""


class MembershipUserSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="user.id")
    email = serializers.EmailField(source="user.email")
    full_name = serializers.CharField(source="user.full_name")
    role = serializers.CharField()

    class Meta:
        model = Membership
        fields = ("id", "email", "full_name", "role")


# --- Items ---
class ItemCreateSerializer(serializers.ModelSerializer):
    item_details = serializers.JSONField(source="details")
    org_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Item
        fields = ("item_details", "org_id")

    def create(self, validated_data):
        org_id = validated_data.pop("org_id")
        details = validated_data.get("details", {})
        user = self.context["request"].user
        org = Organization.objects.get(pk=org_id)
        return Item.objects.create(
            organization=org, created_by=user, details=details
        )


class ItemListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ("id", "details", "created_by_id", "created_at")


# --- Audit ---
class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = ("id", "action", "details", "user_email", "created_at")


class AskAuditSerializer(serializers.Serializer):
    question = serializers.CharField()
    stream = serializers.BooleanField(default=False)
