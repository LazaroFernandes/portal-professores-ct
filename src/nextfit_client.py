"""Cliente HTTP da API pública do NextFit.

Todos os endpoints são GET paginados, retornando:
    { "items": [...], "temProximaPagina": bool }
"""
from __future__ import annotations

import time
from typing import Any, Iterator

import requests


class NextFitClient:
    def __init__(self, api_key: str, base_url: str, version: str = "1", page_size: int = 30):
        self.base_url = base_url.rstrip("/")
        self.version = version
        self.page_size = page_size
        self.session = requests.Session()
        self.session.headers.update({
            "X-Api-Key": api_key,
            "Accept": "application/json",
        })

    def _url(self, path: str) -> str:
        # A API usa /api/v{version}/... — substituímos {version} pelo valor configurado.
        path = path.lstrip("/")
        return f"{self.base_url}/api/v{self.version}/{path}"

    def _get_page(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = self._url(path)
        for attempt in range(3):
            resp = self.session.get(url, params=params, timeout=60)
            if resp.status_code == 429:
                # rate limit — espera e tenta de novo
                time.sleep(2 ** attempt)
                continue
            if not resp.ok:
                body = resp.text[:500] if resp.text else "(vazio)"
                raise RuntimeError(
                    f"HTTP {resp.status_code} em {resp.url}\n  corpo: {body}"
                )
            return resp.json()
        raise RuntimeError(f"Rate limit excedido apos retries em {url}")

    def paginate(self, path: str, extra_params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        """Itera sobre todos os items de um endpoint paginado."""
        skip = 0
        while True:
            params: dict[str, Any] = {"Skip": skip, "Take": self.page_size}
            if extra_params:
                params.update({k: v for k, v in extra_params.items() if v is not None})
            data = self._get_page(path, params)
            items = data.get("items") or []
            for item in items:
                yield item
            if not data.get("temProximaPagina"):
                break
            skip += self.page_size

    def fetch_all(self, path: str, extra_params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return list(self.paginate(path, extra_params))

    # --- atalhos pros endpoints conhecidos ---

    def clientes(self) -> list[dict[str, Any]]:
        return self.fetch_all("Pessoa/GetClientes")

    def leads(self) -> list[dict[str, Any]]:
        return self.fetch_all("Pessoa/GetLeads")

    def usuarios(self) -> list[dict[str, Any]]:
        return self.fetch_all("Pessoa/GetUsuarios")

    def contratos_base(self) -> list[dict[str, Any]]:
        return self.fetch_all("ContratoBase")

    def contratos_cliente(self) -> list[dict[str, Any]]:
        return self.fetch_all("ContratoCliente")

    def vendas(self) -> list[dict[str, Any]]:
        return self.fetch_all("Venda")

    def contas_receber(self) -> list[dict[str, Any]]:
        return self.fetch_all("ContaReceber")

    def movimentos_financeiros(self) -> list[dict[str, Any]]:
        return self.fetch_all("MovimentoFinanceiro")

    def oportunidades(self) -> list[dict[str, Any]]:
        return self.fetch_all("Oportunidade")

    def agenda(self) -> list[dict[str, Any]]:
        return self.fetch_all("Agenda")
