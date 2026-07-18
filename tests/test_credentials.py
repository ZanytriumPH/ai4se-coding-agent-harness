from harness.credentials import CredentialStore, FakeKeyring


def test_store_then_status_configured():
    kr = FakeKeyring()
    cs = CredentialStore(keyring=kr)
    cs.store("sk-secret")
    assert cs.status() == "configured"
    assert kr.get_secret() == "sk-secret"


def test_status_not_configured():
    cs = CredentialStore(keyring=FakeKeyring())
    assert cs.status() == "not configured"


def test_get_does_not_leak_via_status():
    cs = CredentialStore(keyring=FakeKeyring())
    cs.store("sk-secret")
    assert "sk-secret" not in cs.status()


def test_update_overwrites():
    kr = FakeKeyring()
    cs = CredentialStore(keyring=kr)
    cs.store("old")
    cs.update("new")
    assert kr.get_secret() == "new"


def test_clear():
    kr = FakeKeyring()
    cs = CredentialStore(keyring=kr)
    cs.store("x")
    cs.clear()
    assert cs.status() == "not configured"