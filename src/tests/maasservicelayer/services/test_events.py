# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.events import EventsRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.events import Event
from maasservicelayer.services.events import EventsService


@pytest.mark.asyncio
class TestEventsService:
    async def test_list(self) -> None:
        events_repository_mock = Mock(EventsRepository)
        events_repository_mock.list.return_value = ListResult[Event](
            items=[], next_token=None
        )
        events_service = EventsService(
            context=Context(),
            events_repository=events_repository_mock,
        )
        events_list = await events_service.list(token=None, size=1, query=None)
        events_repository_mock.list.assert_called_once_with(
            token=None, size=1, query=None
        )
        assert events_list.next_token is None
        assert events_list.items == []
