# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.spaces import SpacesRepository
from maasservicelayer.models.spaces import Space
from tests.fixtures.factories.spaces import create_test_space_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSpacesRepository(RepositoryCommonTests[Space]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> SpacesRepository:
        return SpacesRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Space]:
        created_spaces = [
            await create_test_space_entry(
                fixture, name=str(i), description=str(i)
            )
            for i in range(num_objects)
        ]
        return created_spaces

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Space:
        return await create_test_space_entry(
            fixture, name="name", description="description"
        )
