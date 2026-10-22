"""Small dependency-free circuit breaker (feature #17).

States: CLOSED (calls pass), OPEN (calls fail fast), HALF_OPEN (one trial call
allowed after the recovery timeout; success closes, failure reopens).
"""

import threading
import time
from enum import Enum
from typing import Callable, Optional


class State(Enum):
    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
        on_state_change: Optional[Callable[["State", "State"], None]] = None,
        on_reject: Optional[Callable[[], None]] = None,
    ):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._clock = clock
        self._on_state_change = on_state_change
        self._on_reject = on_reject
        self._lock = threading.Lock()
        self._state = State.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._trial_in_flight = False

    @property
    def state(self) -> State:
        with self._lock:
            self._maybe_half_open()
            return self._state

    def _transition(self, new: State) -> None:
        old, self._state = self._state, new
        if old is not new and self._on_state_change:
            self._on_state_change(old, new)

    def _maybe_half_open(self) -> None:
        if self._state is State.OPEN and self._clock() - self._opened_at >= self.recovery_timeout:
            self._transition(State.HALF_OPEN)
            self._trial_in_flight = False

    def _before_call(self) -> None:
        with self._lock:
            self._maybe_half_open()
            if self._state is State.OPEN or (self._state is State.HALF_OPEN and self._trial_in_flight):
                if self._on_reject:
                    self._on_reject()
                raise CircuitOpenError("circuit is open")
            if self._state is State.HALF_OPEN:
                self._trial_in_flight = True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._trial_in_flight = False
            if self._state is not State.CLOSED:
                self._transition(State.CLOSED)

    def record_failure(self) -> None:
        with self._lock:
            self._trial_in_flight = False
            self._failures += 1
            if self._state is State.HALF_OPEN or (
                self._state is State.CLOSED and self._failures >= self.failure_threshold
            ):
                self._opened_at = self._clock()
                self._transition(State.OPEN)

    def call(self, func: Callable, *args, **kwargs):
        self._before_call()
        try:
            result = func(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result
