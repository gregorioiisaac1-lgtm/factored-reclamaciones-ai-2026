"""Pure bilingual routing policy. References are extracted before model inference.

The model is deliberately only a fallback for requests outside explicit,
deterministic routes; it never authorizes access or executes a tool.
"""

from dataclasses import dataclass
import re
from typing import Callable, Literal

from intent import baseline, fold


Intent = Literal["status", "new_dispute", "human", "other", "unclear"]
ReferenceType = Literal["claim", "ticket"]

CLAIM_RE = re.compile(r"\bR[\s\-–]?(\d{3})\b", re.IGNORECASE)
TICKET_RE = re.compile(r"\bT-([0-9a-f]{16})\b", re.IGNORECASE)
GENERAL_PRODUCT_RE = re.compile(
    r"\b(direccion|direcciones|endereco|enderecos|domicilio|cadastro|"
    r"comision|comisiones|comissao|comissoes|tarifa|tarifas|"
    r"cajero|cajeros|caixa eletronico|atm|tarjeta|tarjetas|"
    r"cartao|cartoes|senha|contrasena)\b"
)
EXISTING_CASE_RE = re.compile(r"\b(reclamacion|reclamacao|reclamo|queja|protocolo|tramite|caso)\b")
STATUS_CUE_RE = re.compile(
    r"\b(estado|status|andamento|abierto|aberta|aberto|em aberto|conferir|"
    r"verificar|seguimiento|acompanhar|consulta|consultar)\b"
)


@dataclass(frozen=True)
class Reference:
    kind: ReferenceType
    identifier: str


@dataclass(frozen=True)
class Route:
    intent: Intent
    references: tuple[Reference, ...]
    source: Literal["regex", "policy", "model"]
    confidence: float | None = None


def extract_references(message: str) -> tuple[Reference, ...]:
    """Canonicalize unique R case folios and T ticket IDs in textual order."""
    matches: list[tuple[int, Reference]] = []
    matches.extend((m.start(), Reference("claim", f"R-{m.group(1)}"))
                   for m in CLAIM_RE.finditer(message))
    matches.extend((m.start(), Reference("ticket", f"T-{m.group(1).upper()}"))
                   for m in TICKET_RE.finditer(message))
    seen: set[Reference] = set()
    result: list[Reference] = []
    for _, reference in sorted(matches, key=lambda pair: pair[0]):
        if reference not in seen:
            result.append(reference)
            seen.add(reference)
    return tuple(result)


def route(message: str, classifier: Callable[[str], str | tuple[str, float]]) -> Route:
    """Choose a bounded flow without invoking ML when a safe rule applies."""
    references = extract_references(message)
    if references:
        # An explicit reference always starts a read-only status route. A
        # different action requires a separate, confirmed request without it.
        return Route("status", references, "regex")
    normalized = fold(message)
    explicit = baseline(message)
    if explicit in ("new_dispute", "human"):
        return Route(explicit, (), "policy")
    if GENERAL_PRODUCT_RE.search(normalized):
        return Route("other", (), "policy")
    if EXISTING_CASE_RE.search(normalized) and STATUS_CUE_RE.search(normalized):
        return Route("status", (), "policy")
    classified = classifier(message)
    predicted, score = classified if isinstance(classified, tuple) else (classified, None)
    if predicted not in ("status", "new_dispute", "human", "other", "unclear"):
        return Route("unclear", (), "policy")
    return Route(predicted, (), "model", score)
