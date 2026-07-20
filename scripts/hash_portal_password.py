"""Gera um hash scrypt para as senhas do portal sem armazenar a senha."""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.security import hash_password  # noqa: E402


def main() -> int:
    password = getpass.getpass("Senha: ")
    if not password:
        print("A senha não pode ser vazia.", file=sys.stderr)
        return 2
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
