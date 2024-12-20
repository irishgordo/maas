# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.workflows.msm import MachinesCountByStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.machines import MachinesRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.machines import Machine, PciDevice, UsbDevice
from maasservicelayer.services.machines import MachinesService
from maasservicelayer.services.secrets import SecretsService


@pytest.mark.asyncio
class TestMachinesService:
    async def test_list(self) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        machines_repository_mock.list.return_value = ListResult[Machine](
            items=[], next_token=None
        )
        machines_service = MachinesService(
            context=Context(connection=Mock(AsyncConnection)),
            secrets_service=Mock(SecretsService),
            machines_repository=machines_repository_mock,
        )
        machines_list = await machines_service.list(token=None, size=1)
        machines_repository_mock.list.assert_called_once_with(
            token=None, size=1, query=None
        )
        assert machines_list.next_token is None
        assert machines_list.items == []

    async def test_list_machine_usb_devices(self) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        machines_repository_mock.list_machine_usb_devices.return_value = (
            ListResult[UsbDevice](items=[], next_token=None)
        )
        machines_service = MachinesService(
            context=Context(connection=Mock(AsyncConnection)),
            secrets_service=Mock(SecretsService),
            machines_repository=machines_repository_mock,
        )
        usb_devices_list = await machines_service.list_machine_usb_devices(
            system_id="dummy", token=None, size=1
        )
        machines_repository_mock.list_machine_usb_devices.assert_called_once_with(
            system_id="dummy", token=None, size=1
        )
        assert usb_devices_list.next_token is None
        assert usb_devices_list.items == []

    async def test_list_machine_pci_devices(self) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        machines_repository_mock.list_machine_pci_devices.return_value = (
            ListResult[PciDevice](items=[], next_token=None)
        )
        machines_service = MachinesService(
            context=Context(connection=Mock(AsyncConnection)),
            secrets_service=Mock(SecretsService),
            machines_repository=machines_repository_mock,
        )
        pci_devices_list = await machines_service.list_machine_pci_devices(
            system_id="dummy", token=None, size=1
        )
        machines_repository_mock.list_machine_pci_devices.assert_called_once_with(
            system_id="dummy", token=None, size=1
        )
        assert pci_devices_list.next_token is None
        assert pci_devices_list.items == []

    async def test_count_machines_by_statuses(self) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        return_value = Mock(MachinesCountByStatus)
        machines_repository_mock.count_machines_by_statuses.return_value = (
            return_value
        )
        machines_service = MachinesService(
            context=Context(connection=Mock(AsyncConnection)),
            secrets_service=Mock(SecretsService),
            machines_repository=machines_repository_mock,
        )
        result = await machines_service.count_machines_by_statuses()
        assert result is return_value
        machines_repository_mock.count_machines_by_statuses.assert_called_once()
