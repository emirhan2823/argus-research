from pathlib import Path
import stat
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.security.audit import AuditLogger
from argus_py.security.vault import SecureVault


def test_encrypt_decrypt_roundtrip(tmp_path):
    vault = SecureVault(key_file=tmp_path / "vault.key")
    ct = vault.encrypt("secret-value")
    pt = vault.decrypt(ct)
    assert pt == "secret-value"


def test_store_and_get_api_key(tmp_path):
    vault = SecureVault(key_file=tmp_path / "vault.key")
    vault.store_api_key("binance", "abc123")
    got = vault.get_api_key("binance")
    assert got == "abc123"
    assert vault.get_api_key("missing") is None


def test_key_file_permissions_best_effort(tmp_path):
    key_path = tmp_path / "vault.key"
    vault = SecureVault(key_file=key_path)
    _ = vault.encrypt("x")

    mode = stat.S_IMODE(key_path.stat().st_mode)
    assert mode in (0o600, 0o644, 0o666)


def test_audit_logger_writes_and_reads(tmp_path):
    path = tmp_path / "audit.log"
    logger = AuditLogger(path)

    logger.log("store_api_key", "unit-test", "ok", {"key": "binance"})
    logger.log("decrypt", "unit-test", "ok", None)

    events = logger.read_recent(10)
    assert len(events) == 2
    assert events[-1].action == "decrypt"
