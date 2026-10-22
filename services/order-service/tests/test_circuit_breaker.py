import urllib.error

import pytest
from fastapi.testclient import TestClient

from app import main
from app.circuit_breaker import CircuitBreaker, CircuitOpenError, State


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def boom():
    raise RuntimeError("down")


def make(threshold=3, timeout=10):
    clock = FakeClock()
    return CircuitBreaker(failure_threshold=threshold, recovery_timeout=timeout, clock=clock), clock


def trip(cb, n):
    for _ in range(n):
        with pytest.raises(RuntimeError):
            cb.call(boom)


def test_threshold_opens_and_rejects():
    cb, _ = make()
    trip(cb, 2)
    assert cb.state is State.CLOSED
    trip(cb, 1)
    assert cb.state is State.OPEN
    with pytest.raises(CircuitOpenError):
        cb.call(lambda: "ok")


def test_success_resets_failure_count():
    cb, _ = make()
    trip(cb, 2)
    cb.call(lambda: "ok")
    trip(cb, 2)
    assert cb.state is State.CLOSED


def test_timeout_half_open_then_success_closes():
    cb, clock = make()
    trip(cb, 3)
    clock.t = 9.9
    assert cb.state is State.OPEN
    clock.t = 10
    assert cb.state is State.HALF_OPEN
    assert cb.call(lambda: "ok") == "ok"
    assert cb.state is State.CLOSED


def test_failure_in_half_open_reopens():
    cb, clock = make()
    trip(cb, 3)
    clock.t = 10
    trip(cb, 1)
    assert cb.state is State.OPEN
    clock.t = 15
    assert cb.state is State.OPEN  # timeout restarts from the reopen


def test_transition_callback_and_reject_callback():
    events, rejects = [], []
    cb = CircuitBreaker(1, 5, clock=FakeClock(), on_state_change=lambda o, n: events.append((o, n)),
                        on_reject=lambda: rejects.append(1))
    trip(cb, 1)
    with pytest.raises(CircuitOpenError):
        cb.call(lambda: "ok")
    assert events == [(State.CLOSED, State.OPEN)]
    assert rejects == [1]


def test_pay_endpoint_opens_circuit_and_fails_fast(monkeypatch):
    clock = FakeClock()
    cb = CircuitBreaker(2, 30, clock=clock, on_state_change=main._on_state_change)
    monkeypatch.setattr(main, "payment_breaker", cb)

    def down():
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(main, "call_payment_service", down)
    client = TestClient(main.app)
    assert client.post("/orders/101/pay").status_code == 502
    assert client.post("/orders/101/pay").status_code == 502
    assert client.post("/orders/101/pay").status_code == 503
    assert client.get("/circuit-breaker").json()["state"] == "open"
    assert 'circuit_breaker_state{service="order-service",target="payment-service"} 1.0' in client.get("/metrics").text

    monkeypatch.setattr(main, "call_payment_service", lambda: {"status": "healthy"})
    clock.t = 30
    r = client.post("/orders/101/pay")
    assert r.status_code == 200 and r.json()["status"] == "paid"
    assert client.get("/circuit-breaker").json()["state"] == "closed"


def test_pay_unknown_order_404():
    assert TestClient(main.app).post("/orders/9999/pay").status_code == 404
