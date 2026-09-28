"""Server-side mock identity, case ownership, workflow, and traceable outcomes.

All records and PINs in this module are solo participant-authored demo fixtures, never bank data.
"""

from dataclasses import dataclass, field
import base64
import binascii
from collections.abc import Mapping
from datetime import datetime
import hashlib
import hmac
import json
import re
import secrets
import time

from intent import baseline, fold, learned_with_score
from handoff_store import TicketConflictError, TicketStore, TicketStoreError
from routing import route
from tenancy import TenantMiddleware


AS_OF = "31/12/2025"
ACCOUNTS = {"Alicia (prueba)": ("test-a", "1379"), "Bruno (prueba)": ("test-b", "2468")}
REVIEWER = ("test-reviewer", "8642")
CASES = {
    "R-101": {"owner": "test-a", "status": "En proceso", "updated": "15/12/2025", "topic": "Cargo no reconocido"},
    "R-102": {"owner": "test-a", "status": "Resuelto", "updated": "20/12/2025", "topic": "Cargo no reconocido"},
    "R-201": {"owner": "test-b", "status": "Escalado", "updated": "22/12/2025", "topic": "Cargo no reconocido"},
    "R-301": {"owner": "test-a", "status": "Dato inválido", "updated": "", "topic": "Cargo no reconocido"},
}
SENSITIVE_NUMBER_RE = re.compile(r"(?<!\d)(?:\d[\s-]?){11,18}\d(?!\d)")


class SessionError(Exception):
    pass


class ToolError(Exception):
    pass


class SessionAuthority:
    def __init__(self, key=None):
        self.key = key or secrets.token_bytes(32)

    def issue(self, name, pin, now=None, ttl=600):
        account = ACCOUNTS.get(name)
        if account is None or not hmac.compare_digest(pin, account[1]):
            raise SessionError("Credenciales de prueba incorrectas")
        payload = {"sub": account[0], "exp": int(time.time() if now is None else now) + ttl, "iss": "mock-idp"}
        return self._seal(payload)

    def issue_reviewer(self, pin, now=None, ttl=600):
        """Public reviewer identity only for sanitized, fictitious demo tickets."""
        if not isinstance(pin, str) or not hmac.compare_digest(pin, REVIEWER[1]):
            raise SessionError("Credenciales de prueba incorrectas")
        payload = {"sub": REVIEWER[0], "role": "reviewer", "iss": "mock-idp",
                   "exp": int(time.time() if now is None else now) + ttl}
        return self._seal(payload)

    def _seal(self, payload):
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        mac = hmac.new(self.key, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{mac}"

    def _verified_payload(self, token, now=None):
        try:
            if not isinstance(token, str) or len(token) > 4096:
                raise SessionError("Sesión inválida")
            body, mac = token.split(".", 1)
            expected = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(mac, expected):
                raise SessionError("Sesión inválida")
            payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            if not isinstance(payload, dict) or payload.get("iss") != "mock-idp":
                raise SessionError("Sesión inválida")
            if payload.get("exp", 0) <= (time.time() if now is None else now):
                raise SessionError("Sesión vencida")
            return payload
        except (ValueError, TypeError, KeyError, UnicodeError, AttributeError, binascii.Error) as exc:
            raise SessionError("Sesión inválida") from exc

    def verify(self, token, now=None):
        payload = self._verified_payload(token, now)
        if payload.get("sub") not in {a[0] for a in ACCOUNTS.values()} or payload.get("role"):
            raise SessionError("Sesión inválida")
        return payload["sub"]

    def verify_reviewer(self, token, now=None):
        payload = self._verified_payload(token, now)
        if payload.get("sub") != REVIEWER[0] or payload.get("role") != "reviewer":
            raise SessionError("Sesión inválida")
        return payload["sub"]


class CaseRepository:
    def __init__(self) -> None:
        self._tenant = TenantMiddleware(CASES)

    def lookup(self, customer: str, case_id: str, *, fail: bool = False) -> dict | None:
        if fail:
            raise ToolError("No disponible")
        return self._tenant.read_owned(customer, case_id)


@dataclass
class Conversation:
    waiting_for_case: bool = False
    last_verified_case: str = ""
    last_verified_status: str = ""
    bound_subject: str = ""
    bound_session: str = ""
    ticket_scope: str = field(default_factory=lambda: secrets.token_hex(16))
    pending_handoff: dict | None = None
    pending_key: str = ""
    turns: list = field(default_factory=list)
    last_route: dict | None = None


@dataclass
class Reply:
    kind: str
    text: str
    intent: str = ""
    case_id: str = ""
    evidence: str = ""
    attempts: int = 0
    handoff: dict | None = None
    trace: tuple[str, ...] = ()
    case_view: dict | None = None
    plan: dict | None = None
    status_code: int = 200
    error: dict | None = None


@dataclass
class TicketResult:
    kind: str
    text: str
    ticket_id: str = ""
    packet: dict | None = None
    case_view: dict | None = None
    trace: tuple[str, ...] = ()


def say(es, pt, language):
    return pt if language == "pt" else es


def contains_sensitive_number(message):
    """Catch likely account/card numbers before keeping or handing off demo text."""
    return bool(SENSITIVE_NUMBER_RE.search(message))


def _finish(reply, steps, *outcomes):
    """Expose completed workflow steps, never hidden classifier reasoning."""
    reply.trace = tuple(steps) + outcomes
    if reply.kind == "resolved":
        state = "in_progress" if reply.case_view["status"] == "En proceso" else "resolved_case"
        actions = ("date", "reason", "human") if state == "in_progress" else ("date", "human")
    elif reply.kind == "ticket_status":
        state, actions = "ticket_created", ()
    elif reply.kind == "handoff":
        state = f"handoff_{reply.handoff['reason']}"
        actions = ()  # A handoff has already been prepared; no second handoff button.
    elif reply.kind == "denied":
        state, actions = "unavailable", ("human",)
    elif reply.kind == "clarify":
        state, actions = ("need_case" if "ask_case" in outcomes or "ask_one_case" in outcomes
                          else "need_clarification"), ("human",)
    else:
        state, actions = "outside_scope", ("human",)
    reply.plan = {"state": state, "actions": actions}
    return reply


def _forget_case(conversation):
    conversation.last_verified_case = ""
    conversation.last_verified_status = ""


def _lookup_with_retries(repository, subject, case_id, fail_tool):
    """Check ownership in the source on every use of a case, retrying tool errors once."""
    for attempts in (1, 2):
        try:
            return repository.lookup(subject, case_id, fail=fail_tool), attempts, False
        except ToolError:
            pass
    return None, 2, True


def _usable_record(record):
    """Reject invalid/future source values before presenting them as verified facts."""
    if not isinstance(record, Mapping) or record.get("status") not in (
        "En proceso", "Resuelto", "Escalado",
    ):
        return False
    updated = record.get("updated")
    if not isinstance(updated, str) or not re.fullmatch(r"\d{2}/\d{2}/\d{4}", updated):
        return False
    try:
        value = datetime.strptime(updated, "%d/%m/%Y").date()
    except ValueError:
        return False
    return value <= datetime.strptime(AS_OF, "%d/%m/%Y").date()


def _case_view(case_id, record):
    """Produce a displayable case only from a validated, authorized source result."""
    return {"case_id": case_id, "status": record["status"], "updated": record["updated"],
            "source": f"mock-case:{case_id}", "snapshot_as_of": AS_OF}


def _forbidden(language: str, intent: str = "status") -> Reply:
    """Identical 403 for a missing or foreign reference prevents enumeration."""
    message = say(
        "Acceso denegado: el folio no está disponible para esta sesión de prueba.",
        "Acesso negado: o protocolo não está disponível para esta sessão de teste.",
        language,
    )
    return Reply("denied", message, intent, status_code=403,
                 error={"status": 403, "code": "FORBIDDEN", "message": message})


def _sentiment_label(message: str) -> str:
    """Bounded lexical hint from this request only; no diagnosis or raw text."""
    normalized = fold(message)
    if re.search(r"\b(urgente|urgencia|frustrad\w*|molest\w*|enojad\w*|irritad\w*|"
                 r"preocupad\w*|irritado|preocupado|chatead\w*)\b", normalized):
        return "expressed_concern"
    return "unknown"


def respond(message: str, token: str, conversation: Conversation,
            authority: SessionAuthority, repository: CaseRepository, model: object, *,
            language: str = "es", router: str = "learned", fail_tool: bool = False,
            now: float | None = None, ticket_store: TicketStore | None = None) -> Reply:
    """Return verified facts only; classifier may suggest a route but cannot use tools."""
    language = "pt" if language == "pt" else "es"
    message = message.strip()[:600]
    try:
        subject = authority.verify(token, now=now)
    except SessionError:
        return Reply("auth_required", say("Inicia una nueva sesión de prueba para continuar.",
                                          "Inicie uma nova sessão de teste para continuar.", language),
                     trace=("session_rejected",))
    session_id = hashlib.sha256(token.encode()).hexdigest()
    if conversation.bound_subject != subject or conversation.bound_session != session_id:
        conversation.waiting_for_case = False
        conversation.turns.clear()
        _forget_case(conversation)
        conversation.bound_subject = subject
        conversation.bound_session = session_id
        conversation.ticket_scope = secrets.token_hex(16)
    conversation.last_route = None
    conversation.pending_handoff = None
    conversation.pending_key = ""
    if not message:
        return Reply("clarify", say("Escribe tu consulta.", "Escreva sua solicitação.", language),
                     trace=("session_verified", "ask_question"))
    if contains_sensitive_number(message):
        return Reply("clarify", say(
            "No escribas números de tarjeta o cuenta reales en esta demo. Vuelve a preguntar sin ellos.",
            "Não informe números reais de cartão ou conta nesta demonstração. Pergunte novamente sem eles.",
            language,
        ), trace=("session_verified", "sensitive_input_blocked"))
    decision = route(message, lambda text: learned_with_score(text, model) if router == "learned"
                     else baseline(text))
    case_ids = [ref.identifier for ref in decision.references if ref.kind == "claim"]
    ticket_ids = [ref.identifier for ref in decision.references if ref.kind == "ticket"]
    case_id = case_ids[0] if case_ids else ""
    normalized = fold(message)
    date_requested = bool(re.search(r"\b(cuando|quando|fecha|data|actualiz\w*|atualiz\w*|ultima)\b", normalized))
    reason_requested = bool(re.search(r"\b(por que|porque|motivo|razon|razao)\b", normalized))
    new_case_requested = bool(re.search(r"\b(otro|otra|outro|outra|nuevo|nova)\b", normalized))
    intent = decision.intent
    using_context = False
    if not decision.references and (decision.source != "policy" or decision.intent == "status"):
        if (conversation.last_verified_case and not new_case_requested and
                (date_requested or reason_requested)):
            case_id = conversation.last_verified_case
            using_context = True
            intent = "status"
    conversation.last_route = {"intent": intent,
                               "source": "context" if using_context else decision.source,
                               "confidence": None if using_context else decision.confidence}
    steps = ["session_verified", f"route_{intent}"]
    if using_context:
        steps.append("case_from_context")
    # Context needs the route, not a second copy of arbitrary visitor prose.
    conversation.turns.append({"role": "customer", "language": language, "intent": intent})
    if len(conversation.turns) > 12:
        conversation.turns = conversation.turns[-12:]
    if intent == "status":
        if len(decision.references) > 1:
            conversation.waiting_for_case = True
            _forget_case(conversation)
            return _finish(Reply("clarify", say(
                "Veo varios folios. Indica solo uno para consultar su estado.",
                "Vejo vários protocolos. Informe apenas um para consultar o status.",
                language,
            ), intent), steps, "ask_one_case")
        if ticket_ids:
            conversation.waiting_for_case = False
            _forget_case(conversation)
            packet = (read_handoff_ticket(token, conversation, authority, repository,
                                         ticket_store, ticket_ids[0], now=now)
                      if ticket_store is not None else None)
            if packet is None:
                return _finish(_forbidden(language, intent), steps, "lookup_checked", "not_available")
            return _finish(Reply("ticket_status", say(
                f"El ticket de prueba {ticket_ids[0]} está guardado y verificado en la cola temporal. No implica atención de un banco real.",
                f"O ticket de teste {ticket_ids[0]} está salvo e confirmado na fila temporária. Não significa atendimento bancário real.",
                language), intent, evidence="mock-ticket-store", attempts=1),
                           steps, "lookup_checked", "ticket_read_back")
        if not case_id:
            conversation.waiting_for_case = True
            _forget_case(conversation)
            return _finish(Reply("clarify", say("Indica el folio de tu reclamación (por ejemplo, R-101).",
                                                  "Informe o número da sua reclamação (por exemplo, R-101).", language),
                                 intent), steps, "ask_case")
        conversation.waiting_for_case = False
        _forget_case(conversation)
        record, attempts, source_unavailable = _lookup_with_retries(
            repository, subject, case_id, fail_tool,
        )
        if source_unavailable:
            return _finish(_handoff(conversation, "tool_failure", intent, subject, case_id, None,
                                    language, message, attempts), steps, "lookup_failed", "human_handoff")
        if record is None:
            denied = _forbidden(language, intent)
            denied.attempts = attempts
            return _finish(denied, steps, "lookup_checked", "not_available")
        if not _usable_record(record):
            return _finish(_handoff(conversation, "invalid_data", intent, subject, case_id, None,
                                    language, message, attempts), steps, "lookup_checked", "human_handoff")
        conversation.last_verified_case = case_id
        conversation.last_verified_status = record["status"]
        if record["status"] == "Escalado":
            return _finish(_handoff(conversation, "escalated", intent, subject, case_id, record,
                                    language, message, attempts), steps, "lookup_checked", "human_handoff")
        if reason_requested:
            return _finish(_handoff(conversation, "reason_unknown", intent, subject, case_id, record,
                                    language, message, attempts), steps, "lookup_checked", "human_handoff")
        if language == "pt":
            status = {"En proceso": "Em andamento", "Resuelto": "Resolvido"}.get(record["status"], record["status"])
            body = f"No registro fictício {case_id}, o status era **{status}** em {record['updated']}. Fonte: sistema simulado de reclamações. Cópia de {AS_OF}; não é o estado atual de um banco."
        else:
            body = f"En el expediente ficticio {case_id}, el estado era **{record['status']}** al {record['updated']}. Fuente: sistema simulado de reclamaciones. Copia del {AS_OF}; no es el estado actual de un banco."
        return _finish(Reply("resolved", body, intent, case_id,
                             f"mock-case:{case_id}; updated={record['updated']}", attempts,
                             case_view=_case_view(case_id, record)),
                       steps, "lookup_checked", "snapshot_answered")
    conversation.waiting_for_case = False
    if intent == "human":
        # A requested agent can receive the last case from this session, or one
        # explicitly named by the customer, only after a fresh authorized lookup.
        target = (case_id if len(set(case_ids)) == 1 else
                  conversation.last_verified_case if not case_ids else "")
        if target and not case_ids:
            steps.append("case_from_context")
        _forget_case(conversation)
        if target:
            record, attempts, source_unavailable = _lookup_with_retries(
                repository, subject, target, fail_tool,
            )
            if source_unavailable:
                return _finish(_handoff(conversation, "tool_failure", intent, subject, target, None,
                                        language, message, attempts), steps, "lookup_failed", "human_handoff")
            if record is not None and not _usable_record(record):
                return _finish(_handoff(conversation, "invalid_data", intent, subject, target, None,
                                        language, message, attempts), steps, "lookup_checked", "human_handoff")
            return _finish(_handoff(conversation, "requested", intent, subject, target, record,
                                    language, message, attempts), steps, "lookup_checked", "human_handoff")
        return _finish(_handoff(conversation, "requested", intent, subject, "", None,
                                language, message, 0), steps, "human_handoff")
    _forget_case(conversation)
    if intent == "new_dispute":
        # New disputes need a human; this prototype cannot create or reverse transactions.
        return _finish(_handoff(conversation, "new_dispute", intent, subject, "", None,
                                language, message, 0), steps, "human_handoff")
    if intent == "unclear":
        return _finish(Reply("clarify", say(
            "¿Quieres consultar el estado de una reclamación, reportar un cargo o hablar con una persona?",
            "Quer consultar o andamento de uma reclamação, contestar uma cobrança ou falar com uma pessoa?",
            language), intent), steps, "ask_question")
    return _finish(Reply("unsupported", say(
        "Ese trámite no está disponible en esta demo. Pide atención humana si necesitas ayuda.",
        "Esse serviço não está disponível nesta demonstração. Peça atendimento humano se precisar de ajuda.",
        language), intent), steps, "outside_scope")


def _handoff(conversation: Conversation, reason: str, intent: str, subject: str,
             case_id: str, record: dict[str, str] | None, language: str,
             message: str, attempts: int) -> Reply:
    questions = {
        "tool_failure": ("Verificar disponibilidad de la fuente y consultar el estado antes de informar al cliente",
                         "Verificar a disponibilidade da fonte e consultar o status antes de informar o cliente"),
        "escalated": ("Revisar el motivo de la escalación y comunicar el siguiente paso",
                      "Revisar o motivo do encaminhamento e informar o próximo passo"),
        "new_dispute": ("Confirmar los detalles del cargo y decidir la apertura del reclamo bajo política",
                        "Confirmar os dados da cobrança e avaliar a abertura da reclamação conforme a política"),
        "requested": ("Confirmar la ayuda requerida y el siguiente paso con el cliente",
                      "Confirmar a ajuda necessária e o próximo passo com o cliente"),
        "invalid_data": ("Corregir el estado o la fecha de la fuente antes de informar al cliente",
                         "Corrigir o status ou a data da fonte antes de informar o cliente"),
        "reason_unknown": ("Buscar el motivo documentado en un sistema autorizado antes de informar al cliente",
                           "Buscar o motivo documentado em uma fonte autorizada antes de informar o cliente"),
    }
    # Do not store arbitrary visitor text in the ticket queue of a public demo.
    request_labels = {
        "tool_failure": ("Consultar estado tras una falla de la fuente", "Consultar o status após falha na fonte"),
        "invalid_data": ("Revisar datos incompletos", "Revisar dados incompletos"),
        "escalated": ("Revisar un expediente escalado", "Revisar um protocolo encaminhado"),
        "reason_unknown": ("Explicar el motivo del estado", "Explicar o motivo do status"),
        "requested": ("Solicita atención humana", "Solicita atendimento humano"),
        "new_dispute": ("Reportar cargo no reconocido", "Contestar cobrança não reconhecida"),
    }
    unresolved = questions[reason][1 if language == "pt" else 0]
    facts = (_case_view(case_id, record) if record is not None else {})
    packet = {"reason": reason, "reason_for_escalation": reason,
              "customer_id": subject, "ticket_id": None,
              "verified_facts": facts, "open_questions": [unresolved],
              "sentiment": _sentiment_label(message), "test_subject": subject,
              "request": request_labels[reason][1 if language == "pt" else 0],
              "verified_case": case_id if record is not None else None,
              "verified_status": record["status"] if record is not None else None,
              "verified_updated": record["updated"] if record is not None else None,
              "snapshot_as_of": AS_OF if record is not None else None,
              "source": f"mock-case:{case_id}" if record is not None else None,
              "actions": ["read_only_lookup"] if record is not None else
                         ["lookup_attempted"] if attempts else [],
              "unresolved": unresolved}
    conversation.pending_handoff = packet
    conversation.pending_key = secrets.token_hex(16)
    if reason == "reason_unknown":
        phrase = say("Verifiqué el estado y la fecha, pero la fuente no indica el motivo. Preparé una derivación de prueba; no se modificó ninguna reclamación.",
                     "Confirmei o status e a data, mas a fonte não informa o motivo. Preparei um encaminhamento de teste; nenhuma reclamação foi alterada.", language)
    else:
        phrase = say("Preparé una derivación de prueba a un agente; no se creó ni modificó ninguna reclamación.",
                     "Preparei um encaminhamento de teste para atendimento humano; nenhuma reclamação foi criada ou alterada.", language)
    return Reply("handoff", phrase, intent, case_id if record else "",
                 packet["source"] or "", attempts, packet,
                 case_view=_case_view(case_id, record) if record is not None else None)


def _ticket_subject(token, conversation, authority, *, now=None):
    try:
        subject = authority.verify(token, now=now)
    except SessionError:
        return None
    if (subject != conversation.bound_subject or
            hashlib.sha256(token.encode()).hexdigest() != conversation.bound_session):
        return None
    return subject


def create_handoff_ticket(token: str, conversation: Conversation, authority: SessionAuthority,
                          repository: CaseRepository, ticket_store: TicketStore, *,
                          language: str = "es", now: float | None = None,
                          fail_tool: bool = False, fail_write: bool = False,
                          fail_read: bool = False) -> TicketResult:
    """Confirm an explicit request with fresh authorization, write, and readback."""
    language = "pt" if language == "pt" else "es"
    subject = _ticket_subject(token, conversation, authority, now=now)
    if not subject:
        return TicketResult("auth_required", say("Inicia una nueva sesión de prueba.",
                                                 "Inicie uma nova sessão de teste.", language))
    if not conversation.pending_handoff or not conversation.pending_key:
        return TicketResult("unavailable", say("Prepara otra derivación para continuar.",
                                               "Prepare outro encaminhamento para continuar.", language))
    packet = {**conversation.pending_handoff,
              "actions": list(conversation.pending_handoff["actions"])}
    packet.pop("ticket_id", None)  # Generated by the store and included in its committed readback.
    view = None
    if packet["verified_case"]:
        case_id = packet["verified_case"]
        record, attempts, failed = _lookup_with_retries(repository, subject, case_id, fail_tool)
        if failed or not _usable_record(record):
            return TicketResult("unavailable", say(
                "No pude confirmar el folio antes de crear el ticket. Vuelve a consultar la fuente.",
                "Não consegui confirmar o protocolo antes de criar o ticket. Consulte a fonte novamente.", language),
                trace=("ticket_authorization_failed",))
        view = _case_view(case_id, record)
        packet.update(verified_status=record["status"], verified_updated=record["updated"],
                      snapshot_as_of=AS_OF, source=view["source"], verified_facts=view)
        packet["actions"].append("fresh_authorized_lookup")
    try:
        ticket_id, confirmed = ticket_store.create_and_verify(
            subject, conversation.ticket_scope, conversation.pending_key, packet,
            now=now, fail_write=fail_write, fail_read=fail_read,
        )
    except TicketConflictError:
        conversation.pending_handoff = None
        conversation.pending_key = ""
        return TicketResult("stale", say(
            "El expediente cambió desde que se guardó el ticket. No confirmé esta versión: consulta de nuevo el folio y prepara otra derivación.",
            "O protocolo mudou desde que o ticket foi salvo. Não confirmei esta versão: consulte novamente o protocolo e prepare outro encaminhamento.", language,
        ), trace=("ticket_stale",))
    except TicketStoreError:
        return TicketResult("unavailable", say(
            "No pude verificar que se guardara el ticket; inténtalo de nuevo.",
            "Não consegui confirmar que o ticket foi salvo; tente novamente.", language),
            trace=("ticket_unconfirmed",))
    if confirmed.get("ticket_id") != ticket_id or confirmed.get("customer_id") != subject:
        return TicketResult("unavailable", say(
            "No pude verificar el ticket; inténtalo de nuevo.",
            "Não consegui confirmar o ticket; tente novamente.", language),
            trace=("ticket_unconfirmed",))
    return TicketResult("created", say(
        "Ticket de prueba guardado y comprobado. No se envió a una persona real.",
        "Ticket de teste salvo e confirmado. Não foi enviado a uma pessoa real.", language),
        ticket_id=ticket_id, packet=confirmed, case_view=view,
        trace=("ticket_saved", "ticket_read_back"))


def read_handoff_ticket(token: str, conversation: Conversation, authority: SessionAuthority,
                        repository: CaseRepository, ticket_store: TicketStore, ticket_id: str,
                        *, now: float | None = None,
                        fail_tool: bool = False) -> dict | None:
    """Only the current mock session can see its ticket; recheck any case ownership."""
    subject = _ticket_subject(token, conversation, authority, now=now)
    if not subject:
        return None
    try:
        packet = ticket_store.read(subject, conversation.ticket_scope, ticket_id, now=now)
    except TicketStoreError:
        return None
    if packet and (packet.get("customer_id") != subject or packet.get("ticket_id") != ticket_id):
        return None
    if packet and packet.get("verified_case"):
        record, _, failed = _lookup_with_retries(
            repository, subject, packet["verified_case"], fail_tool,
        )
        if failed or not _usable_record(record):
            return None
        if (record["status"] != packet.get("verified_status") or
                record["updated"] != packet.get("verified_updated")):
            return None
    return packet


def reviewer_inbox(token, authority, ticket_store, *, now=None):
    """Reviewer role sees only the sanitized, fictitious packets in this instance."""
    authority.verify_reviewer(token, now=now)
    return ticket_store.list_recent(now=now)


def read_handoff_review(token, conversation, authority, repository, ticket_store,
                        ticket_id, *, now=None):
    """Customer can verify only the review receipt of an accessible ticket."""
    subject = _ticket_subject(token, conversation, authority, now=now)
    if not subject or read_handoff_ticket(token, conversation, authority, repository,
                                          ticket_store, ticket_id, now=now) is None:
        return None
    return ticket_store.review_status(subject, conversation.ticket_scope, ticket_id, now=now)


def review_handoff_ticket(token, authority, ticket_store, ticket_id, *, now=None):
    """Acknowledge a demo ticket and return only its committed review receipt."""
    reviewer = authority.verify_reviewer(token, now=now)
    return ticket_store.acknowledge(ticket_id, reviewer, now=now)
