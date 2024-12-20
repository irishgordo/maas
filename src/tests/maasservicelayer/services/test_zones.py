#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from maasapiserver.v3.constants import DEFAULT_ZONE_NAME
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.zones import ZonesRepository
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.zones import Zone
from maasservicelayer.services import (
    NodesService,
    VmClustersService,
    ZonesService,
)
from maasservicelayer.utils.date import utcnow

DEFAULT_ZONE = Zone(
    id=1,
    name=DEFAULT_ZONE_NAME,
    description="",
    created=utcnow(),
    updated=utcnow(),
)

TEST_ZONE = Zone(
    id=4,
    name="test_zone",
    description="test_description",
    created=utcnow(),
    updated=utcnow(),
)


@pytest.mark.asyncio
class TestZonesService:
    async def test_delete(self) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.delete.return_value = None
        zones_repository.find_by_id.side_effect = [TEST_ZONE, None]
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        await zones_service.delete(TEST_ZONE.id)
        assert (await zones_service.get_by_id(TEST_ZONE.id)) is None

    async def test_delete_etag(
        self,
        mocker: MockerFixture,
    ) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.delete.return_value = None
        zones_repository.find_by_id.side_effect = [TEST_ZONE, None]
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        mocker.patch(
            "maasservicelayer.models.zones.Zone.etag", return_value="my-etag"
        )

        await zones_service.delete(TEST_ZONE.id, "my-etag")
        assert (await zones_service.get_by_id(TEST_ZONE.id)) is None

    async def test_delete_etag_fail(
        self,
        mocker: MockerFixture,
    ) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.find_by_id.return_value = TEST_ZONE
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        mocker.patch(
            "maasservicelayer.models.zones.Zone.etag", return_value="my-etag"
        )

        with pytest.raises(PreconditionFailedException) as excinfo:
            await zones_service.delete(TEST_ZONE.id, "wrong-etag")
        assert (
            excinfo.value.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE
        )

    async def test_delete_default_zone(self) -> None:
        zones_repository = Mock(ZonesRepository)
        zones_repository.find_by_id.return_value = DEFAULT_ZONE
        zones_repository.get_default_zone.return_value = DEFAULT_ZONE
        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )

        with pytest.raises(BadRequestException) as excinfo:
            await zones_service.delete(DEFAULT_ZONE.id)
        assert (
            excinfo.value.details[0].type
            == CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE
        )

    async def test_delete_related_objects_are_moved_to_default_zone(
        self,
    ) -> None:
        nodes_service_mock = Mock(NodesService)
        vmclusters_service_mock = Mock(VmClustersService)
        zones_repository = Mock(ZonesRepository)
        zones_repository.find_by_id.return_value = TEST_ZONE
        zones_repository.get_default_zone.return_value = DEFAULT_ZONE
        zones_repository.delete.return_value = None

        zones_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository,
            nodes_service=nodes_service_mock,
            vmcluster_service=vmclusters_service_mock,
        )

        await zones_service.delete(TEST_ZONE.id)

        nodes_service_mock.move_to_zone.assert_called_once_with(
            TEST_ZONE.id, DEFAULT_ZONE.id
        )
        nodes_service_mock.move_bmcs_to_zone.assert_called_once_with(
            TEST_ZONE.id, DEFAULT_ZONE.id
        )
        vmclusters_service_mock.move_to_zone.assert_called_once_with(
            TEST_ZONE.id, DEFAULT_ZONE.id
        )

    async def test_list(self) -> None:
        zones_repository_mock = Mock(ZonesRepository)
        zones_repository_mock.list.return_value = ListResult[ZonesRepository](
            items=[], next_token=None
        )
        resource_pools_service = ZonesService(
            context=Context(),
            zones_repository=zones_repository_mock,
            nodes_service=Mock(NodesService),
            vmcluster_service=Mock(VmClustersService),
        )
        query_mock = Mock(QuerySpec)
        resource_pools_list = await resource_pools_service.list(
            token=None, size=1, query=query_mock
        )
        zones_repository_mock.list.assert_called_once_with(
            token=None, size=1, query=query_mock
        )
        assert resource_pools_list.next_token is None
        assert resource_pools_list.items == []
