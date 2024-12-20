#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import json
from json import dumps as _dumps
from unittest.mock import Mock, patch

from httpx import AsyncClient
from macaroonbakery.bakery import Macaroon
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.users import UserInfoResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import DischargeRequiredException
from maasservicelayer.models.users import User
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.external_auth import ExternalAuthService
from maasservicelayer.services.users import UsersService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestUsersApi:
    BASE_PATH = f"{V3_API_PREFIX}/users"

    # GET /users/me
    async def test_get_user_info(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.get.return_value = User(
            id=1,
            username="username",
            password="pass",
            is_superuser=False,
            first_name="",
            last_name="",
            is_staff=False,
            is_active=True,
            date_joined=utcnow(),
            email=None,
            last_login=None,
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/me",
        )
        assert response.status_code == 200

        user_info = UserInfoResponse(**response.json())
        assert user_info.id == 1
        assert user_info.username == "username"
        assert user_info.is_superuser is False

    async def test_get_user_info_admin(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.get.return_value = User(
            id=1,
            username="admin",
            password="pass",
            is_superuser=True,
            first_name="",
            last_name="",
            is_staff=True,
            is_active=True,
            date_joined=utcnow(),
            email=None,
            last_login=None,
        )
        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/me",
        )
        assert response.status_code == 200

        user_info = UserInfoResponse(**response.json())
        assert user_info.id == 1
        assert user_info.username == "admin"
        assert user_info.is_superuser is True

    async def test_get_user_info_unauthorized(
        self, mocked_api_client: AsyncClient
    ) -> None:
        response = await mocked_api_client.get(f"{self.BASE_PATH}/me")
        assert response.status_code == 401
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 401

    async def test_get_user_info_discharge_required(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_rbac: AsyncClient,
    ) -> None:
        """If external auth is enabled make sure we receive a discharge required response"""
        services_mock.external_auth = Mock(ExternalAuthService)
        services_mock.external_auth.raise_discharge_required_exception.side_effect = DischargeRequiredException(
            macaroon=Mock(Macaroon)
        )

        # we have to mock json.dumps as it doesn't know how to deal with Mock objects
        def custom_json_dumps(*args, **kwargs):
            return _dumps(*args, **(kwargs | {"default": lambda obj: "mock"}))

        with patch("json.dumps", custom_json_dumps):
            response = await mocked_api_client_rbac.get(f"{self.BASE_PATH}/me")

        assert response.status_code == 401
        discharge_response = json.loads(response.content.decode("utf-8"))
        assert discharge_response["Code"] == "macaroon discharge required"
        assert discharge_response["Info"]["Macaroon"] is not None
        assert discharge_response["Info"]["MacaroonPath"] == "/"
        assert discharge_response["Info"]["CookieNameSuffix"] == "maas"
