"""Sprint 1: org onboarding, JWT login, RBAC, tenant-scoped user management."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, RoleCode, User
from apps.accounts.services import OnboardingService, UserService
from core.context import use_tenant
from core.exceptions import BusinessRuleError

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _make_org(name: str) -> tuple:
    return OnboardingService().create_organization(
        org_name=name, admin_username=f"admin_{name}", admin_password="supersecret123"
    )


def test_signup_creates_active_user_ready_to_login(client: APIClient):
    """Auto-cadastro entra direto: conta ativa, sem etapa de aprovação."""
    tenant, _ = _make_org("Base")  # organização precisa existir
    resp = client.post(
        "/api/auth/signup",
        {
            "full_name": "João da Silva",
            "nome_guerra": "SILVA",
            "posto_graduacao": "Cap",
            "cpf": "111.444.777-35",
            "birth_date": "1990-05-10",
            "email": "joao@ex.com",
            "email_confirm": "joao@ex.com",
            "phone": "(11) 99999-9999",
            "password": "supersecret123",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    u = User.objects.get(email="joao@ex.com")
    assert u.tenant_id == tenant.id
    assert u.is_active and u.has_role(RoleCode.USER)
    assert u.cpf == "11144477735"  # armazenado só com dígitos
    assert client.post(
        "/api/auth/token", {"username": "joao@ex.com", "password": "supersecret123"}, format="json"
    ).status_code == 200


def test_signup_rejects_invalid_cpf_and_mismatched_email(client: APIClient):
    _make_org("Base0")
    base = {
        "full_name": "Maria",
        "nome_guerra": "SOUZA",
        "posto_graduacao": "Sd EP",
        "birth_date": "1990-05-10",
        "email": "maria@ex.com",
        "email_confirm": "maria@ex.com",
        "password": "supersecret123",
    }
    cpf_ruim = client.post(
        "/api/auth/signup", {**base, "cpf": "111.111.111-11"}, format="json"
    )
    assert cpf_ruim.status_code == 400
    emails = client.post(
        "/api/auth/signup",
        {**base, "cpf": "111.444.777-35", "email_confirm": "outro@ex.com"},
        format="json",
    )
    assert emails.status_code == 400


def test_admin_creates_user_with_full_registration(client: APIClient):
    tenant, admin = _make_org("Base")
    client.force_authenticate(admin)
    resp = client.post(
        "/api/users",
        {
            "full_name": "João da Silva",
            "nome_guerra": "SILVA",
            "posto_graduacao": "Cap",
            "cpf": "111.444.777-35",  # CPF válido
            "birth_date": "1990-05-10",
            "email": "joao@ex.com",
            "phone": "(11) 99999-9999",
            "password": "supersecret123",
            "role_codes": ["user"],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    u = User.objects.get(email="joao@ex.com")
    assert u.tenant_id == tenant.id
    assert u.has_role(RoleCode.USER)
    assert u.full_name == "João da Silva"
    assert u.cpf == "11144477735"  # armazenado só com dígitos
    assert u.username == "joao@ex.com"  # sem login explícito, o e-mail vira o usuário
    # login por e-mail funciona
    tok = client.post(
        "/api/auth/token",
        {"username": "joao@ex.com", "password": "supersecret123"},
        format="json",
    )
    assert tok.status_code == 200


def test_admin_user_creation_rejects_invalid_cpf(client: APIClient):
    _tenant, admin = _make_org("Base2")
    client.force_authenticate(admin)
    resp = client.post(
        "/api/users",
        {
            "full_name": "Maria",
            "nome_guerra": "SOUZA",
            "posto_graduacao": "Sd EP",
            "cpf": "111.111.111-11",  # inválido
            "email": "maria@ex.com",
            "password": "supersecret123",
        },
        format="json",
    )
    assert resp.status_code == 400


def test_admin_user_creation_rejects_duplicate_email(client: APIClient):
    _tenant, admin = _make_org("Base3")
    client.force_authenticate(admin)
    payload = {"email": "dup@ex.com", "password": "supersecret123", "nome_guerra": "DUP"}
    assert client.post("/api/users", payload, format="json").status_code == 201
    assert client.post("/api/users", payload, format="json").status_code == 400


def test_admin_creates_person_without_access(client: APIClient):
    """Cadastro sem acesso: existe para reserva/cautela, mas não entra no sistema."""
    tenant, admin = _make_org("semacesso")
    client.force_authenticate(admin)
    resp = client.post(
        "/api/users",
        {
            "full_name": "Visitante da Silva",
            "nome_guerra": "VISITANTE",
            "posto_graduacao": "Sd EP",
            "is_active": False,
            "role_codes": ["user"],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["is_active"] is False
    user = User.objects.get(pk=resp.data["id"])
    assert user.tenant_id == tenant.id
    assert not user.has_usable_password()
    assert user.username  # login gerado a partir do nome
    # não consegue entrar de jeito nenhum
    assert client.post(
        "/api/auth/token", {"username": user.username, "password": ""}, format="json"
    ).status_code == 400
    # e serve de solicitante numa reserva feita pelo gestor
    assert user.display_name == "Sd EP VISITANTE"


def test_person_without_access_needs_a_name(client: APIClient):
    _tenant, admin = _make_org("semnome")
    client.force_authenticate(admin)
    resp = client.post("/api/users", {"is_active": False}, format="json")
    assert resp.status_code == 400


def test_user_with_access_requires_password(client: APIClient):
    _tenant, admin = _make_org("compass")
    client.force_authenticate(admin)
    resp = client.post("/api/users", {"email": "sem.senha@ex.com"}, format="json")
    assert resp.status_code == 400


def test_admin_edits_user_and_changes_role(client: APIClient):
    tenant, admin = _make_org("edituser")
    with use_tenant(tenant.id):
        alvo = UserService().create_user(
            username="alvo", password="supersecret123", email="alvo@ex.com",
            nome_guerra="ALVO", role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    resp = client.patch(
        f"/api/users/{alvo.id}",
        {
            "full_name": "Alvo Corrigido",
            "nome_guerra": "CORRIGIDO",
            "posto_graduacao": "2º Sgt",
            "email": "novo@ex.com",
            "phone": "(61) 90000-0000",
            "role_codes": ["director"],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.data
    alvo.refresh_from_db()
    assert alvo.full_name == "Alvo Corrigido"
    assert alvo.display_name == "2º Sgt CORRIGIDO"
    assert alvo.email == "novo@ex.com"
    assert [r.code for r in alvo.roles.all()] == ["director"]


def test_admin_cannot_remove_own_admin_role_or_access(client: APIClient):
    _tenant, admin = _make_org("selfguard")
    client.force_authenticate(admin)
    demote = client.patch(f"/api/users/{admin.id}", {"role_codes": ["user"]}, format="json")
    assert demote.status_code == 422
    assert demote.data["error"]["code"] == "cannot_demote_self"
    off = client.patch(f"/api/users/{admin.id}", {"is_active": False}, format="json")
    assert off.status_code == 422
    assert off.data["error"]["code"] == "cannot_deactivate_self"
    admin.refresh_from_db()
    assert admin.is_active and admin.has_role(RoleCode.ADMIN)


def test_admin_resets_password_of_another_user(client: APIClient):
    tenant, admin = _make_org("reset")
    with use_tenant(tenant.id):
        alvo = UserService().create_user(
            username="esquecido", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    resp = client.post(
        f"/api/users/{alvo.id}/reset-password", {"new_password": "novasenha456"}, format="json"
    )
    assert resp.status_code == 204, resp.data
    alvo.refresh_from_db()
    assert alvo.check_password("novasenha456")


def test_user_list_search_and_filters(client: APIClient):
    tenant, admin = _make_org("busca")
    with use_tenant(tenant.id):
        svc = UserService()
        svc.create_user(
            username="sgt.pereira", password="supersecret123", nome_guerra="PEREIRA",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        svc.create_user(
            username="cb.lima", password="supersecret123", nome_guerra="LIMA",
            role_codes=[RoleCode.INVENTORY], tenant_id=tenant.id,
        )
        svc.create_user(
            full_name="Convidado Sem Acesso", is_active=False,
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)

    por_nome = client.get("/api/users?q=pereira").data["results"]
    assert {u["username"] for u in por_nome} == {"sgt.pereira"}

    por_perfil = client.get("/api/users?role=inventory").data["results"]
    assert {u["username"] for u in por_perfil} == {"cb.lima"}

    sem_acesso = client.get("/api/users?is_active=false").data["results"]
    assert [u["full_name"] for u in sem_acesso] == ["Convidado Sem Acesso"]

    ativos = client.get("/api/users?is_active=true").data["count"]
    assert ativos == 3  # admin + os dois com acesso


def test_admin_deletes_user_without_history(client: APIClient):
    tenant, admin = _make_org("excluiuser")
    with use_tenant(tenant.id):
        alvo = UserService().create_user(
            username="descartavel", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(admin)
    assert client.delete(f"/api/users/{alvo.id}").status_code == 204
    assert not User.objects.filter(pk=alvo.pk).exists()


def test_cannot_delete_user_with_bookings(client: APIClient):
    """Quem já movimentou bem não some: o rastro de responsabilidade some junto."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.assets.services import AssetService

    tenant, admin = _make_org("comhistorico")
    with use_tenant(tenant.id):
        dono = UserService().create_user(
            username="comreserva", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        asset = AssetService().create_asset(name="Bem reservado")
    client.force_authenticate(dono)
    agora = timezone.now()
    client.post(
        "/api/bookings",
        {
            "asset": str(asset.id),
            "start_at": (agora + timedelta(days=1)).isoformat(),
            "end_at": (agora + timedelta(days=2)).isoformat(),
        },
        format="json",
    )
    client.force_authenticate(admin)
    resp = client.delete(f"/api/users/{dono.id}")
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "user_has_history"
    assert User.objects.filter(pk=dono.pk).exists()


def test_cannot_delete_self_or_last_admin(client: APIClient):
    tenant, admin = _make_org("ultimoadmin")
    client.force_authenticate(admin)
    proprio = client.delete(f"/api/users/{admin.id}")
    assert proprio.status_code == 422
    assert proprio.data["error"]["code"] == "cannot_delete_self"

    with use_tenant(tenant.id):
        outro_admin = UserService().create_user(
            username="admin2", password="supersecret123",
            role_codes=[RoleCode.ADMIN], tenant_id=tenant.id,
        )
    # com dois admins, o segundo pode ser excluído
    assert client.delete(f"/api/users/{outro_admin.id}").status_code == 204


def test_delete_user_is_admin_only(client: APIClient):
    tenant, admin = _make_org("excluirbac")
    with use_tenant(tenant.id):
        comum = UserService().create_user(
            username="comum_rbac", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
        alvo = UserService().create_user(
            username="alvo_rbac", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
        )
    client.force_authenticate(comum)
    assert client.delete(f"/api/users/{alvo.id}").status_code == 403


def test_login_returns_jwt_with_tenant_and_roles(client: APIClient):
    tenant, _ = _make_org("orgx")
    resp = client.post(
        "/api/auth/token",
        {"username": "admin_orgx", "password": "supersecret123"},
        format="json",
    )
    assert resp.status_code == 200
    assert "access" in resp.data and "refresh" in resp.data


def test_admin_can_create_user(client: APIClient):
    tenant, admin = _make_org("orga")
    client.force_authenticate(admin)
    resp = client.post(
        "/api/users",
        {"username": "invA", "password": "supersecret123", "role_codes": ["inventory"]},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["roles"] == ["inventory"]


def test_create_user_with_rank_and_war_name(client: APIClient):
    tenant, admin = _make_org("rank")
    client.force_authenticate(admin)
    resp = client.post(
        "/api/users",
        {
            "username": "sd_souza",
            "password": "supersecret123",
            "nome_guerra": "SOUZA",
            "posto_graduacao": "Sd EP",
            "role_codes": ["user"],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["nome_guerra"] == "SOUZA"
    assert resp.data["display_name"] == "Sd EP SOUZA"


def test_non_admin_cannot_create_user(client: APIClient):
    tenant, admin = _make_org("orgb")
    with use_tenant(tenant.id):
        plain = UserService().create_user(
            username="plain", password="supersecret123", role_codes=[RoleCode.USER],
            tenant_id=tenant.id,
        )
    client.force_authenticate(plain)
    resp = client.post(
        "/api/users",
        {"username": "hacker", "password": "supersecret123"},
        format="json",
    )
    assert resp.status_code == 403


def test_user_list_is_tenant_scoped(client: APIClient):
    tenant_a, admin_a = _make_org("aaa")
    tenant_b, admin_b = _make_org("bbb")
    client.force_authenticate(admin_a)
    resp = client.get("/api/users")
    usernames = {u["username"] for u in resp.data["results"]}
    assert usernames == {"admin_aaa"}
    assert "admin_bbb" not in usernames


def test_me_returns_current_user(client: APIClient):
    tenant, admin = _make_org("meorg")
    client.force_authenticate(admin)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.data["username"] == "admin_meorg"


def _member(email: str = "perfil@ex.com", password: str = "supersecret123") -> User:
    """Usuário comum criado pelo administrador (login por e-mail)."""
    tenant, _admin = OnboardingService().create_organization(
        org_name="perfilorg", admin_username="admin_perfilorg", admin_password=password
    )
    with use_tenant(tenant.id):
        return UserService().create_user(
            username=email,
            password=password,
            email=email,
            full_name="Ana Souza",
            nome_guerra="SOUZA",
            posto_graduacao="Sd EP",
            cpf="11144477735",
            birth_date="1990-05-10",
            role_codes=[RoleCode.USER],
            tenant_id=tenant.id,
        )


def test_user_updates_own_profile(client: APIClient):
    user = _member()
    client.force_authenticate(user)
    resp = client.patch(
        "/api/auth/me",
        {"phone": "(61) 98888-7777", "nome_guerra": "SOUZA JR", "email": "Nova@Ex.com"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    user.refresh_from_db()
    assert user.phone == "(61) 98888-7777"
    assert user.nome_guerra == "SOUZA JR"
    assert user.email == "nova@ex.com"
    # quando o login é o e-mail, o username acompanha a troca
    assert user.username == "nova@ex.com"
    assert client.post(
        "/api/auth/token", {"username": "nova@ex.com", "password": "supersecret123"}, format="json"
    ).status_code == 200


def test_profile_rejects_email_already_used(client: APIClient):
    user = _member()
    with use_tenant(user.tenant_id):
        other = UserService().create_user(
            username="outro", password="supersecret123", email="ocupado@ex.com",
            tenant_id=user.tenant_id,
        )
    client.force_authenticate(user)
    resp = client.patch("/api/auth/me", {"email": other.email}, format="json")
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "email_taken"


def test_profile_does_not_expose_restricted_fields(client: APIClient):
    """CPF e nome completo identificam a pessoa: só a administração muda.

    Posto/graduação saiu desta lista de propósito — muda com promoção e quem
    sabe da mudança é a própria pessoa (ver update_profile).
    """
    user = _member()
    client.force_authenticate(user)
    resp = client.patch(
        "/api/auth/me",
        {"cpf": "52998224725", "full_name": "Outro Nome", "role_codes": ["admin"]},
        format="json",
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.cpf == "11144477735"
    assert user.full_name == "Ana Souza"
    assert not user.has_role(RoleCode.ADMIN)


def test_user_changes_own_password(client: APIClient):
    user = _member()
    client.force_authenticate(user)
    resp = client.post(
        "/api/auth/me/password",
        {"current_password": "supersecret123", "new_password": "novasenha456"},
        format="json",
    )
    assert resp.status_code == 204, resp.data
    user.refresh_from_db()
    assert user.check_password("novasenha456")


def test_password_change_requires_current_password(client: APIClient):
    user = _member()
    client.force_authenticate(user)
    resp = client.post(
        "/api/auth/me/password",
        {"current_password": "errada123", "new_password": "novasenha456"},
        format="json",
    )
    assert resp.status_code == 422
    assert resp.data["error"]["code"] == "invalid_password"
    user.refresh_from_db()
    assert user.check_password("supersecret123")


def test_user_can_change_their_own_rank(client: APIClient):
    """Promoção é do dia a dia: quem sabe da mudança é a própria pessoa."""
    tenant, admin = OnboardingService().create_organization(
        org_name="posto1", admin_username="admin_posto1", admin_password="supersecret123"
    )
    with use_tenant(tenant.id):
        pessoa = UserService().create_user(
            username="sd_promo", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant.id,
            posto_graduacao="Sd EP", nome_guerra="PROMO",
        )
    client.force_authenticate(pessoa)

    resp = client.patch("/api/auth/me", {"posto_graduacao": "Cb"}, format="json")
    assert resp.status_code == 200, resp.data
    assert resp.data["posto_graduacao"] == "Cb"

    pessoa.refresh_from_db()
    assert pessoa.posto_graduacao == "Cb"
    assert pessoa.display_name.startswith("Cb")


def test_barbershop_client_role_is_seeded():
    assert RoleCode.BARBERSHOP_CLIENT == "barbershop_client"
    assert Role.objects.filter(code=RoleCode.BARBERSHOP_CLIENT).exists()


def test_create_user_with_soldado_rank_forces_barbershop_client_role(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="soldado1",
            password="supersecret123",
            posto_graduacao="Sd EP",
            role_codes=[RoleCode.ADMIN],
            tenant_id=tenant_a.id,
        )
    assert list(user.roles.values_list("code", flat=True)) == [RoleCode.BARBERSHOP_CLIENT]


def test_update_user_rank_change_to_cabo_overrides_role(tenant_a):
    with use_tenant(tenant_a.id):
        admin = UserService().create_user(
            username="admin_ta", password="supersecret123",
            role_codes=[RoleCode.ADMIN], tenant_id=tenant_a.id,
        )
        target = UserService().create_user(
            username="diretor1", password="supersecret123",
            role_codes=[RoleCode.DIRECTOR], tenant_id=tenant_a.id,
        )
        UserService().update_user(user=target, actor=admin, posto_graduacao="Cb")
        target.refresh_from_db()
    assert list(target.roles.values_list("code", flat=True)) == [RoleCode.BARBERSHOP_CLIENT]


def test_update_user_cannot_self_demote_via_rank_change(tenant_a):
    with use_tenant(tenant_a.id):
        admin = UserService().create_user(
            username="admin_ta2", password="supersecret123",
            role_codes=[RoleCode.ADMIN], tenant_id=tenant_a.id,
        )
        with pytest.raises(BusinessRuleError):
            UserService().update_user(user=admin, actor=admin, posto_graduacao="Sd EP")


def test_update_profile_rank_change_to_soldado_overrides_role(tenant_a):
    with use_tenant(tenant_a.id):
        user = UserService().create_user(
            username="usuario1", password="supersecret123",
            role_codes=[RoleCode.USER], tenant_id=tenant_a.id,
        )
        UserService().update_profile(user=user, posto_graduacao="Sd EP")
        user.refresh_from_db()
    assert list(user.roles.values_list("code", flat=True)) == [RoleCode.BARBERSHOP_CLIENT]


def test_signup_with_soldado_rank_gets_barbershop_client_role(client: APIClient):
    _make_org("BaseSd")
    resp = client.post(
        "/api/auth/signup",
        {
            "full_name": "Soldado Teste",
            "nome_guerra": "TESTE",
            "posto_graduacao": "Sd EP",
            "cpf": "111.444.777-35",
            "birth_date": "1990-05-10",
            "email": "soldado@ex.com",
            "email_confirm": "soldado@ex.com",
            "phone": "(11) 99999-9999",
            "password": "supersecret123",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    u = User.objects.get(email="soldado@ex.com")
    assert u.has_role(RoleCode.BARBERSHOP_CLIENT)
    assert not u.has_role(RoleCode.USER)


def test_update_profile_cannot_self_demote_via_rank_change(tenant_a):
    with use_tenant(tenant_a.id):
        admin = UserService().create_user(
            username="admin_ta3", password="supersecret123",
            role_codes=[RoleCode.ADMIN], tenant_id=tenant_a.id,
        )
        with pytest.raises(BusinessRuleError):
            UserService().update_profile(user=admin, posto_graduacao="Sd EP")
        admin.refresh_from_db()
    assert admin.has_role(RoleCode.ADMIN)


def test_patch_me_cannot_self_demote_via_rank_change(client: APIClient):
    tenant, admin = _make_org("SelfDemote")
    client.force_authenticate(admin)
    resp = client.patch("/api/auth/me", {"posto_graduacao": "Cb"}, format="json")
    assert resp.status_code != 200, resp.data
    admin.refresh_from_db()
    assert admin.has_role(RoleCode.ADMIN)
