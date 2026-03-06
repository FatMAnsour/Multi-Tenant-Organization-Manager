"""
API views for Multi-Tenant Organization Manager.
"""
import json
import os
from groq import Groq
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.contrib.postgres.search import SearchVector, SearchQuery
from django.http import StreamingHttpResponse
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


from .models import Organization, Membership, Role, Item, AuditLog
from .serializers import *
from .permissions import IsOrgAdmin, IsOrgMember


User = get_user_model()


def _log_audit(organization_id, user, action, details=None):
    org = Organization.objects.get(pk=organization_id)
    AuditLog.objects.create(
        organization=org,
        user=user,
        action=action,
        details=details or {},
    )


# --- Auth ---
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    ser = RegisterSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    ser.save()
    return Response(
        {"id": ser.instance.id, "email": ser.instance.email},
        status=status.HTTP_201_CREATED,
    )


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["sub"] = str(user.id)
        return token


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    ser = LoginSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = User.objects.filter(email=ser.validated_data["email"]).first()
    if not user or not user.check_password(ser.validated_data["password"]):
        return Response(
            {"detail": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    refresh = CustomTokenObtainPairSerializer.get_token(user)
    return Response({
        "access_token": str(refresh.access_token),
        "token_type": "bearer",
    })


# --- Organization ---
class OrganizationCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = OrganizationCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        ser.is_valid(raise_exception=True)
        org = ser.save()
        _log_audit(
            org.id,
            request.user,
            "organization_created",
            {"org_name": org.name},
        )
        return Response({"org_id": str(org.id)}, status=status.HTTP_201_CREATED)


class OrganizationInviteUserView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request, id):
        org = Organization.objects.get(pk=id)
        ser = InviteUserSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]
        role = ser.validated_data["role"]
        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"detail": "User with this email does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if Membership.objects.filter(user=user, organization=org).exists():
            return Response(
                {"detail": "User already in organization"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        Membership.objects.create(user=user, organization=org, role=role)
        _log_audit(id, request.user, "user_invited", {"email": email, "role": role})
        return Response(status=status.HTTP_201_CREATED)


class OrganizationUsersListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    serializer_class = MembershipUserSerializer

    def get_queryset(self):
        org_id = self.kwargs["id"]
        return Membership.objects.filter(organization_id=org_id).select_related("user")


class OrganizationUsersSearchView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def get(self, request, id):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"results": []})

        org_id = id
        user_ids = list(Membership.objects.filter(organization_id=org_id).values_list("user_id", flat=True))
        if not user_ids:
            return Response({"results": []})

        # Search by email/full_name (PostgreSQL FTS) OR by role (e.g. "Member" returns users with role member)
        search_query = SearchQuery(q, config="english")
        users_by_text = (
            User.objects.filter(id__in=user_ids)
            .annotate(search=SearchVector("email", "full_name", config="english"))
            .filter(search=search_query)
        )
        users_by_role = User.objects.filter(
            id__in=user_ids,
            memberships__organization_id=org_id,
            memberships__role__icontains=q,
        )
        users = (users_by_text | users_by_role).distinct()
        memberships = {
            m.user_id: m.role
            for m in Membership.objects.filter(organization_id=org_id, user__in=users)
        }
        for u in users:
            u._membership_role = memberships.get(u.id, "")
        ser = UserInOrgSerializer(users, many=True)
        return Response({"results": ser.data})


# --- Items ---
class ItemListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request, id):
        org_id = id
        user = request.user
        membership = Membership.objects.filter(
            user=user, organization_id=org_id
        ).first()
        qs = Item.objects.filter(organization_id=org_id).select_related("created_by")
        if membership and membership.role == Role.MEMBER:
            qs = qs.filter(created_by=user)
        _log_audit(org_id, user, "items_listed", {})
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        page = qs[offset : offset + limit]
        ser = ItemListSerializer(page, many=True)
        return Response({"results": ser.data, "count": qs.count()})

    def post(self, request, id):
        org = Organization.objects.get(pk=id)
        data = dict(request.data)
        data["org_id"] = id
        ser = ItemCreateSerializer(data=data, context={"request": request})
        ser.is_valid(raise_exception=True)
        item = ser.save()
        _log_audit(
            id,
            request.user,
            "item_created",
            {"item_id": item.id, "details": item.details},
        )
        return Response({"item_id": str(item.id)}, status=status.HTTP_201_CREATED)


# --- Audit logs ---
class AuditLogListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        return AuditLog.objects.filter(organization_id=self.kwargs["id"]).select_related("user")


# --- Chatbot (LLM) ---
class AuditAskView(APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request, id):
        ser = AskAuditSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        question = ser.validated_data["question"]
        stream = ser.validated_data["stream"]

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        logs = AuditLog.objects.filter(
            organization_id=id,
            created_at__gte=today_start,
        ).select_related("user").order_by("created_at")

        log_lines = []
        for log in logs:
            log_lines.append(
                f"{log.created_at.isoformat()} | {log.action} | user={getattr(log.user, 'email', 'N/A')} | {json.dumps(log.details)}"
            )
        context = "\n".join(log_lines) if log_lines else "No activity today."

        if stream:
            return self._stream_response(question, context)
        return self._sync_response(question, context)

    def _sync_response(self, question, context):
        try:
            answer = self._call_llm_sync(question, context)
            if not answer or not answer.strip():
                answer = "No answer generated. (Tip: Set GROQ_API_KEY for AI answers.)"
            return Response({"answer": answer})
        except Exception as e:
            return Response(
                {"detail": "LLM error", "error": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    def _stream_response(self, question, context):
        def generate():
            try:
                for chunk in self._call_llm_stream(question, context):
                    if isinstance(chunk, str):
                        yield chunk
                    else:
                        yield json.dumps({"text": str(chunk)}) + "\n"
            except Exception as e:
                yield json.dumps({"error": str(e)}) + "\n"

        return StreamingHttpResponse(
            generate(),
            content_type="application/x-ndjson",
        )

    def _groq_model_name(self):
        return os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

    def _build_chat_prompt(self, question, context):
        return (
            "You are an assistant that answers questions about organization audit logs. "
            "Answer concisely based only on the provided log data.\n\n"
            f"Log data for today:\n{context}\n\nQuestion: {question}"
        )

    def _call_llm_sync(self, question, context):
        """Returns a string only (no generator). Used when stream=False."""
        api_key = (os.environ.get("GROQ_API_KEY") or "").strip()
        if not api_key:
            return "No GROQ_API_KEY configured. Summary of today's activity:\n" + (context[:2000] if context else "No activity today.")
        return self._call_groq_sync(question, context, api_key)

    def _call_llm_stream(self, question, context):
        """Generator: yields NDJSON lines. Used when stream=True."""
        api_key = (os.environ.get("GROQ_API_KEY") or "").strip()
        if not api_key:
            fallback_msg = "No GROQ_API_KEY configured. Summary of today's activity:\n" + (context[:2000] if context else "No activity today.")
            yield json.dumps({"text": fallback_msg}) + "\n"
            return
        yield from self._call_groq_stream(question, context, api_key)

    def _call_groq_sync(self, question, context, api_key):
        """Returns a plain string. Used when stream=False."""
        try:
            client = Groq(api_key=api_key)
            prompt = self._build_chat_prompt(question, context)
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self._groq_model_name(),
            )
            text = None
            if response.choices:
                msg = response.choices[0].message
                if msg and getattr(msg, "content", None):
                    text = msg.content
            if not (text and str(text).strip()):
                return "No response from model."
            return str(text).strip()
        except Exception as e:
            return f"Error calling Groq: {e}"

    def _call_groq_stream(self, question, context, api_key):
        """Generator: yields NDJSON lines. Used when stream=True."""
        try:
            client = Groq(api_key=api_key)
            prompt = self._build_chat_prompt(question, context)
            stream = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self._groq_model_name(),
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    part = chunk.choices[0].delta.content
                    if part:
                        yield json.dumps({"text": part}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
