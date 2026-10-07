import asyncio
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from cache_service.config import Settings
from cache_service.main import create_app
from tests.support import SpyTransformer, serve

SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
SAMPLE_OUTPUT = (
    "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
)


async def test_create_then_read_returns_the_interleaved_output(
    client: AsyncClient, spy: SpyTransformer
) -> None:
    created = await client.post("/payload", json=SAMPLE)

    assert created.status_code == 201
    payload_id = created.json()["id"]
    assert created.json() == {"id": payload_id, "message": "Payload created"}
    assert created.headers["location"] == f"/payload/{payload_id}"

    read = await client.get(created.headers["location"])

    assert read.status_code == 200
    assert read.json() == {"output": SAMPLE_OUTPUT}
    assert spy.calls.total() == 6


async def test_repeated_request_reuses_the_id_without_transforming(
    client: AsyncClient, spy: SpyTransformer
) -> None:
    first = await client.post("/payload", json=SAMPLE)
    spy.calls.clear()

    second = await client.post("/payload", json=SAMPLE)

    assert second.status_code == 200
    assert second.json() == {"id": first.json()["id"], "message": "Payload already exists"}
    assert "location" not in second.headers
    assert not spy.calls


async def test_overlapping_request_transforms_only_new_strings(
    client: AsyncClient, spy: SpyTransformer
) -> None:
    await client.post("/payload", json=SAMPLE)
    spy.calls.clear()

    created = await client.post(
        "/payload",
        json={"list_1": ["first string", "new string"], "list_2": ["last string", "first string"]},
    )
    read = await client.get(f"/payload/{created.json()['id']}")

    assert created.status_code == 201
    assert spy.calls == {"new string": 1}
    assert read.json() == {"output": "FIRST STRING, LAST STRING, NEW STRING, FIRST STRING"}


async def test_concurrent_identical_requests_create_one_payload(settings: Settings) -> None:
    spy = SpyTransformer(delay=0.05)

    async with serve(create_app(settings, transformer=spy)) as client:
        first, second = await asyncio.gather(
            client.post("/payload", json=SAMPLE), client.post("/payload", json=SAMPLE)
        )

    assert sorted([first.status_code, second.status_code]) == [200, 201]
    assert first.json()["id"] == second.json()["id"]
    assert spy.calls.total() == 6


async def test_payloads_and_cache_survive_a_restart(settings: Settings) -> None:
    async with serve(create_app(settings, transformer=SpyTransformer())) as client:
        first = await client.post("/payload", json=SAMPLE)
    spy = SpyTransformer()

    async with serve(create_app(settings, transformer=spy)) as client:
        second = await client.post("/payload", json=SAMPLE)
        read = await client.get(f"/payload/{first.json()['id']}")

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert read.json() == {"output": SAMPLE_OUTPUT}
    assert not spy.calls


async def test_read_unknown_payload_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/payload/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Payload not found"}


async def test_read_with_malformed_id_returns_422(client: AsyncClient) -> None:
    response = await client.get("/payload/not-a-uuid")

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        pytest.param('{"list_1": ["a", "b"], "list_2": ["c"]}', id="unequal-lengths"),
        pytest.param('{"list_1": [], "list_2": []}', id="empty-lists"),
        pytest.param('{"list_1": ["a"]}', id="missing-list"),
        pytest.param('{"list_1": ["a\\ud800"], "list_2": ["b"]}', id="lone-surrogate"),
        pytest.param("not json", id="malformed-json"),
    ],
)
async def test_invalid_body_is_rejected_before_transforming(
    client: AsyncClient, spy: SpyTransformer, body: str
) -> None:
    response = await client.post(
        "/payload", content=body, headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["detail"]
    assert not spy.calls


async def test_transformer_failure_returns_502_and_keeps_partial_results(
    client: AsyncClient, spy: SpyTransformer
) -> None:
    spy.fail_on = {"second string"}

    failed = await client.post("/payload", json=SAMPLE)

    assert failed.status_code == 502
    assert failed.json() == {"detail": "Transformer service failed"}

    spy.fail_on.clear()
    retried = await client.post("/payload", json=SAMPLE)

    assert retried.status_code == 201
    assert spy.calls["first string"] == 1
    assert spy.calls["second string"] == 2


async def test_unexpected_transformer_errors_return_500(settings: Settings) -> None:
    async def broken(text: str, /) -> str:
        raise ValueError("bug in the client")

    app = create_app(settings, transformer=broken)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with (
        LifespanManager(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.post("/payload", json=SAMPLE)

    assert response.status_code == 500
