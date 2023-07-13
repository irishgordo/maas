from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncIterable, Callable, Iterable, Iterator

from django.core import signing
from fastapi import FastAPI
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.db import Database
from maasapiserver.main import create_app
from maasapiserver.models.v1.entities.user import User

from .db import Fixture


@contextmanager
def override_dependencies(
    app: FastAPI,
    dependencies_map: dict[Callable[..., Any], Callable[..., Any]],
) -> Iterator[None]:
    """Context manager to override app dependencies in tests."""
    for orig_func, override_func in dependencies_map.items():
        app.dependency_overrides[orig_func] = override_func
    yield
    for orig_func in dependencies_map:
        del app.dependency_overrides[orig_func]


@pytest.fixture
def api_app(db: Database, db_connection: AsyncConnection) -> Iterable[FastAPI]:
    """The API application."""

    from maasapiserver.api.db import db_conn as orig_db_conn

    deps_map = {orig_db_conn: lambda: db_connection}

    app = create_app(db=db)
    with override_dependencies(app, deps_map):
        yield app


@pytest.fixture
async def api_client(api_app: FastAPI) -> AsyncIterable[AsyncClient]:
    """Client for the API."""
    async with AsyncClient(app=api_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def user_session_id(fixture: Fixture) -> Iterable[str]:
    """API user session ID."""
    yield fixture.random_string()


@pytest.fixture
async def authenticated_user(
    fixture: Fixture,
    user_session_id: str,
) -> AsyncIterable[User]:
    user_details = {
        "username": "user",
        "first_name": "Some",
        "last_name": "User",
        "email": "user@example.com",
        "password": "secret",
        "is_superuser": False,
        "is_staff": False,
        "is_active": True,
        "date_joined": datetime.utcnow(),
    }
    [user_details] = await fixture.create("auth_user", user_details)
    user = User(**user_details)
    await _create_user_session(fixture, user, user_session_id)
    yield user


async def _create_user_session(
    fixture: Fixture, user: User, session_id: str
) -> None:
    key = "<UNUSED>"
    salt = "django.contrib.sessions.SessionStore"
    algorithm = "sha256"
    signer = signing.TimestampSigner(key, salt=salt, algorithm=algorithm)
    session_data = signer.sign_object(
        {"_auth_user_id": str(user.id)}, serializer=signing.JSONSerializer
    )
    await fixture.create(
        "django_session",
        {
            "session_key": session_id,
            "session_data": session_data,
            "expire_date": datetime.utcnow() + timedelta(days=20),
        },
    )


@pytest.fixture
async def authenticated_api_client(
    api_app: FastAPI, authenticated_user: User, user_session_id: str
) -> AsyncIterable[AsyncClient]:
    """Authenticated client for the API."""
    async with AsyncClient(app=api_app, base_url="http://test") as client:
        client.cookies.set("sessionid", user_session_id)
        yield client