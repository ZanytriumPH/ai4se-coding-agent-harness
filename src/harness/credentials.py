from __future__ import annotations

from typing import Protocol


SERVICE_NAME = "coding-agent-harness"
ACCOUNT = "default"


class KeyringLike(Protocol):
    def set_password(self, service: str, account: str, password: str) -> None: ...
    def get_password(self, service: str, account: str) -> str | None: ...
    def delete_password(self, service: str, account: str) -> None: ...


class FakeKeyring:
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, account: str, password: str) -> None:
        self._store[(service, account)] = password

    def get_password(self, service: str, account: str) -> str | None:
        return self._store.get((service, account))

    def delete_password(self, service: str, account: str) -> None:
        self._store.pop((service, account), None)

    def get_secret(self) -> str | None:
        return self._store.get((SERVICE_NAME, ACCOUNT))


class CredentialStore:
    def __init__(self, keyring: KeyringLike | None = None) -> None:
        if keyring is None:
            import keyring as _k  # type: ignore[import-untyped]  # real runtime only

            keyring = _k.get_keyring()
        self.kr = keyring

    def store(self, key: str) -> None:
        self.kr.set_password(SERVICE_NAME, ACCOUNT, key)

    def get(self) -> str | None:
        return self.kr.get_password(SERVICE_NAME, ACCOUNT)

    def status(self) -> str:
        return "configured" if self.get() is not None else "not configured"

    def update(self, key: str) -> None:
        self.store(key)

    def clear(self) -> None:
        try:
            self.kr.delete_password(SERVICE_NAME, ACCOUNT)
        except Exception:
            pass