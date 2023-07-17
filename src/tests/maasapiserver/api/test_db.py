from typing import AsyncIterable

from fastapi import Depends, FastAPI
from httpx import AsyncClient
import pytest
from sqlalchemy import Column, insert, Integer, MetaData, select, Table
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.api.base import API, Handler, handler
from maasapiserver.api.db import db_conn
from maasapiserver.db import Database
from maasapiserver.main import create_app

METADATA = MetaData()


TestTable = Table(
    "testing",
    METADATA,
    Column("id", Integer, primary_key=True),
)


class MyException(Exception):
    """Boom"""


@pytest.fixture
async def insert_app(db: Database, db_connection: AsyncConnection) -> FastAPI:
    class InsertHandler(Handler):
        @handler(path="/success", methods=["GET"])
        async def success(
            self, conn: AsyncConnection = Depends(db_conn)
        ) -> None:
            await conn.execute(insert(TestTable).values(id=42))

        @handler(path="/failure", methods=["GET"])
        async def fail(self, conn: AsyncConnection = Depends(db_conn)) -> None:
            await conn.execute(insert(TestTable).values(id=42))
            raise MyException("boom")

    api_app = create_app(db=db)
    api = API(prefix="/insert", handlers=[InsertHandler()])
    api.register(api_app.router)

    async with db_connection.begin():
        await db_connection.run_sync(TestTable.create)
    return api_app


@pytest.fixture
async def insert_client(insert_app: FastAPI) -> AsyncIterable[AsyncClient]:
    async with AsyncClient(app=insert_app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.allow_transactions
class TestDBSession:
    async def test_commit(
        self, insert_client: AsyncClient, db_connection: AsyncConnection
    ) -> None:
        response = await insert_client.get("/insert/success")
        assert response.status_code == 200

        async with db_connection.begin():
            ids = await db_connection.scalars(select(TestTable.c.id))
        assert list(ids) == [42]

    async def test_rollback(
        self, insert_client: AsyncClient, db_connection: AsyncConnection
    ) -> None:
        with pytest.raises(MyException):
            await insert_client.get("/insert/failure")

        async with db_connection.begin():
            ids = await db_connection.scalars(select(TestTable.c.id))
        assert list(ids) == []
