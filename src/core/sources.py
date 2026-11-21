"""Fontes de dados usadas em uma resposta (proveniência vinda do servidor MCP).

O servidor MCP devolve, em toda ferramenta, `source`, `source_url`, `retrieved_at`,
`data_timestamp`, `freshness`, `status`, `attribution`, `license` e `limitations`.
Aqui esses campos viram uma lista de fontes para o frontend e um rodapé de atribuição.
"""

from typing import Any

from pydantic import BaseModel, Field

# Fonte que falhou não é "fonte consultada": fica fora da lista.
_EXCLUDED_STATUS = {"unavailable"}


class SourceRef(BaseModel):
    tool: str
    name: str
    url: str | None = None
    retrieved_at: str | None = None  # ISO 8601, UTC
    data_timestamp: str | None = None  # a que momento o dado se refere
    status: str | None = None
    freshness: str | None = None
    attribution: str | None = None
    license: str | None = None
    limitations: list[str] = Field(default_factory=list)


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


class SourceRecorder:
    """Acumula as fontes das ferramentas chamadas em UMA pergunta."""

    def __init__(self) -> None:
        self._sources: dict[tuple[str, str | None], SourceRef] = {}

    def record(self, tool_name: str, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        name = _text(payload.get("source"))
        if name is None or payload.get("status") in _EXCLUDED_STATUS:
            return
        limitations = payload.get("limitations")
        ref = SourceRef(
            tool=tool_name,
            name=name,
            url=_text(payload.get("source_url")),
            retrieved_at=_text(payload.get("retrieved_at")),
            data_timestamp=_text(payload.get("data_timestamp")),
            status=_text(payload.get("status")),
            freshness=_text(payload.get("freshness")),
            attribution=_text(payload.get("attribution")),
            license=_text(payload.get("license")),
            limitations=[x for x in limitations if isinstance(x, str)]
            if isinstance(limitations, list)
            else [],
        )
        self._sources.setdefault((ref.name, ref.url), ref)

    @property
    def sources(self) -> list[SourceRef]:
        return list(self._sources.values())

    def attribution_footer(self) -> str:
        """Atribuições exigidas pelas fontes (ex.: Open-Meteo, Global Fishing Watch).

        Anexada pelo código, e não pelo modelo, porque é obrigação de licença.
        """
        seen: list[str] = []
        for ref in self._sources.values():
            if ref.attribution and ref.attribution not in seen:
                seen.append(ref.attribution)
        return ("\n\nAtribuição: " + "; ".join(seen)) if seen else ""
