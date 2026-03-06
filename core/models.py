from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    def __str__(self):
        return self.email
    class Meta:
        db_table = "users"


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"


class Organization(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "organizations"
        ordering = ["-created_at"]


class Membership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)

    def __str__(self):
        return f"Membership(user={self.user.email}, org={self.organization.name}, role={self.role})"
    class Meta:
        db_table = "memberships"
        unique_together = [["user", "organization"]]
        indexes = [
            models.Index(fields=["organization", "role"]),
        ]


class Item(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="items"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_items"
    )
    details = models.JSONField(default=dict) 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Item {self.id} - {self.organization.name} - {self.created_by.email}"
    class Meta:
        db_table = "items"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_by"]),
        ]


class AuditLog(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="audit_logs"
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_actions"
    )
    action = models.CharField(max_length=255)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} - {self.organization.name} - {self.created_at}"
    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
        ]   
