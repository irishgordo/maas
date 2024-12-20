#  Copyright 2023-2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC
from dataclasses import dataclass

from maasservicelayer.context import Context
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import MaasBaseModel


@dataclass(slots=True)
class ServiceCache(ABC):
    """Base cache for a service."""

    def clear(self):
        for field in list(self.__slots__):
            self.__setattr__(field, None)

    async def close(self):
        """Shutdown operations to be performed when destroying the cache."""


class Service(ABC):
    """Base class for services."""

    def __init__(self, context: Context, cache: ServiceCache | None = None):
        self.context = context
        self.cache = cache

    def etag_check(
        self, model: MaasBaseModel, etag_if_match: str | None = None
    ):
        """
        Raises a PreconditionFailedException if the etag does not match.
        """
        if etag_if_match is not None and model.etag() != etag_if_match:
            raise PreconditionFailedException(
                details=[
                    BaseExceptionDetail(
                        type=ETAG_PRECONDITION_VIOLATION_TYPE,
                        message=f"The resource etag '{model.etag()}' did not match '{etag_if_match}'.",
                    )
                ]
            )

    @staticmethod
    def build_cache_object() -> ServiceCache:
        """Return the cache specific to the service."""
        raise NotImplementedError(
            "build_cache_object must be overridden in the service."
        )

    @staticmethod
    def from_cache_or_execute(attr: str):
        """Decorator to search `attr` through the cache before executing the method.

        The logic is as follows:
            - you have a Service and a related ServiceCache
            - in the ServiceCache you must define all the values that you want
                to cache as an attribute with a type and that defaults to None.
            - wrap the method in the Service that is responsible to retrieve that value
            - now the ServiceCache will be checked before executing the Service method
                and if there is a value, it will return it otherwise it will execute
                the method, populate the ServiceCache and return that value.

        Note: This decorator doesn't take into account *args and **kwargs, so don't
            expect it to cache different values for different function calls.
        """

        def inner_decorator(fn):
            async def wrapped(self, *args, **kwargs):
                if self.cache is None:
                    return await fn(self, *args, **kwargs)
                if self.cache.__getattribute__(attr) is None:  # Cache miss
                    value = await fn(self, *args, **kwargs)
                    self.cache.__setattr__(attr, value)
                return self.cache.__getattribute__(attr)

            return wrapped

        return inner_decorator
