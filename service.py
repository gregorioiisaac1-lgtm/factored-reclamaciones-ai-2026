"""Server-side mock identity, case ownership, workflow, and traceable outcomes.

All records and PINs in this module are solo participant-authored demo fixtures, never bank data.
"""

from dataclasses import dataclass, field
import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import time

from intent import baseline, fold, learned
from handoff_store import TicketStoreError


AS_OF = "31/12/2025"
ACCOUNTS = {"Alicia (prueba)": ("test-a", "1379"), "Bruno (prueba)": ("test-b", "2468")}
CASES = {
    "R-101": {"owner": "test-a", "status": "En proceso", "updated": "15/12/2025", "topic": "Cargo no reconocido"},
    "R-102": {"owner": "test-a", "status": "Resuelto", "updated": "20/12/2025", "topic": "Cargo no reconocido"},
    "R-201": {"owner": "test-b", "status": "Escalado", "updated": "22/12/2025", "topic": "Cargo no reconocido"},
    "R-301": {"owner": "test-a", "status": "Dato inválido", "updated": "", "topic": "Cargo no reconocido"},
}
CASE_RE = re.compile(r"\bR[\s\-–]?\d{3}\b", re.IGNORECASE)
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
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        mac = hmac.new(self.key, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{mac}"

    def verify(self, token, now=None):
        try:
            body, mac = token.split(".", 1)
            expected = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(mac, expected):
                raise SessionError("Sesión inválida")
            payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            if payload.get("iss") != "mock-idp" or payload.get("sub") not in {a[0] for a in ACCOUNTS.values()}:
                raise SessionError("Sesión inválida")
            if payload.get("exp", 0) <= (time.time() if now is None else now):
                raise SessionError("Sesión vencida")
            return payload["sub"]
        except (ValueError, TypeError, KeyError, UnicodeError, AttributeError, binascii.Error) as exc:
            raise SessionError("Sesión inválida") from exc


class CaseRepository:
    def lookup(self, customer, case_id, *, fail=False):
        if fail:
            raise ToolError("No disponible")
        case = CASES.get(case_id)
        # The same result for nonexistent and another customer's case prevents enumeration.
        if case is None or case["owner"] != customer:
            return None
        return {k: v for k, v in case.items() if k != "owner"}


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
    return (record is not None and record.get("status") in ("En proceso", "Resuelto", "Escalado")
            and bool(record.get("updated")))


def _case_view(case_id, record):
    """Produce a displayable case only from a validated, authorized source result."""
    return {"case_id": case_id, "status": record["status"], "updated": record["updated"],
            "source": f"mock-case:{case_id}", "snapshot_as_of": AS_OF}


def respond(message, token, conversation, authority, repository, model, *, language="es", router="learned", fail_tool=False, now=None):
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
    case_ids = ["R-" + re.sub(r"\D", "", match.group()) for match in CASE_RE.finditer(message)]
    case_id = case_ids[0] if case_ids else ""
    normalized = fold(message)
    date_requested = bool(re.search(r"\b(cuando|quando|fecha|data|actualiz\w*|atualiz\w*|ultima)\b", normalized))
    reason_requested = bool(re.search(r"\b(por que|porque|motivo|razon|razao)\b", normalized))
    new_case_requested = bool(re.search(r"\b(otro|otra|outro|outra|nuevo|nova)\b", normalized))
    intent = (learned(message, model) if router == "learned" else baseline(message))
    explicit = baseline(message)
    # A request for a human or a new dispute takes precedence over prior status context.
    if router == "learned" and explicit in ("human", "new_dispute"):
        intent = explicit
    using_context = False
    if intent not in ("human", "new_dispute"):
        if len(set(case_ids)) > 1:
            intent = "status"
        elif CASE_RE.fullmatch(message) or (conversation.waiting_for_case and case_id):
            intent = "status"
        elif case_id and (date_requested or reason_requested):
            intent = "status"
        elif (not case_id and conversation.last_verified_case and not new_case_requested
              and (date_requested or reason_requested)):
            case_id = conversation.last_verified_case
            using_context = True
            intent = "status"
    steps = ["session_verified", f"route_{intent}"]
    if using_context:
        steps.append("case_from_context")
    conversation.turns.append({"role": "customer", "language": language, "text": message})
    if len(conversation.turns) > 12:
        conversation.turns = conversation.turns[-12:]
    if intent == "status":
        if len(set(case_ids)) > 1:
            conversation.waiting_for_case = True
            _forget_case(conversation)
            return _finish(Reply("clarify", say(
                "Veo varios folios. Indica solo uno para consultar su estado.",
                "Vejo vários protocolos. Informe apenas um para consultar o status.",
                language,
            ), intent), steps, "ask_one_case")
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
            return _finish(Reply("denied", say(
                "No encuentro ese folio en tu sesión de prueba. Comprueba el número o solicita atención humana.",
                "Não encontro esse protocolo na sua sessão de teste. Confira o número ou peça atendimento humano.",
                language), intent, attempts=attempts), steps, "lookup_checked", "not_available")
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


def _handoff(conversation, reason, intent, subject, case_id, record, language, message, attempts):
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
    packet = {"reason": reason, "test_subject": subject,
              "request": request_labels[reason][1 if language == "pt" else 0],
              "verified_case": case_id if record is not None else None,
              "verified_status": record["status"] if record is not None else None,
              "verified_updated": record["updated"] if record is not None else None,
              "snapshot_as_of": AS_OF if record is not None else None,
              "source": f"mock-case:{case_id}" if record is not None else None,
              "actions": ["read_only_lookup"] if record is not None else
                         ["lookup_attempted"] if attempts else [],
              "unresolved": questions[reason][1 if language == "pt" else 0]}
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


def create_handoff_ticket(token, conversation, authority, repository, ticket_store, *,
                          language="es", now=None, fail_tool=False, fail_write=False, fail_read=False):
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
                      snapshot_as_of=AS_OF, source=view["source"])
        packet["actions"].append("fresh_authorized_lookup")
    try:
        ticket_id, confirmed = ticket_store.create_and_verify(
            subject, conversation.ticket_scope, conversation.pending_key, packet,
            now=now, fail_write=fail_write, fail_read=fail_read,
        )
    except TicketStoreError:
        return TicketResult("unavailable", say(
            "No pude verificar que se guardara el ticket; inténtalo de nuevo.",
            "Não consegui confirmar que o ticket foi salvo; tente novamente.", language),
            trace=("ticket_unconfirmed",))
    return TicketResult("created", say(
        "Ticket de prueba guardado y comprobado. No se envió a una persona real.",
        "Ticket de teste salvo e confirmado. Não foi enviado a uma pessoa real.", language),
        ticket_id=ticket_id, packet=confirmed, case_view=view,
        trace=("ticket_saved", "ticket_read_back"))


def read_handoff_ticket(token, conversation, authority, repository, ticket_store, ticket_id,
                        *, now=None, fail_tool=False):
    """Only the current mock session can see its ticket; recheck any case ownership."""
    subject = _ticket_subject(token, conversation, authority, now=now)
    if not subject:
        return None
    try:
        packet = ticket_store.read(subject, conversation.ticket_scope, ticket_id, now=now)
    except TicketStoreError:
        return None
    if packet and packet.get("verified_case"):
        record, _, failed = _lookup_with_retries(
            repository, subject, packet["verified_case"], fail_tool,
        )
        if failed or not _usable_record(record):
            return None
    return packet
