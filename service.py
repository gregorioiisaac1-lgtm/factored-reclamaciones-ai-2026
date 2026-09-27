"""Server-side mock identity, case ownership, workflow, and traceable outcomes.

All records and PINs in this module are team-authored demo fixtures, never bank data.
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

from intent import baseline, learned


AS_OF = "31/12/2025"
ACCOUNTS = {"Alicia (prueba)": ("test-a", "1379"), "Bruno (prueba)": ("test-b", "2468")}
CASES = {
    "R-101": {"owner": "test-a", "status": "En proceso", "updated": "15/12/2025", "topic": "Cargo no reconocido"},
    "R-102": {"owner": "test-a", "status": "Resuelto", "updated": "20/12/2025", "topic": "Cargo no reconocido"},
    "R-201": {"owner": "test-b", "status": "Escalado", "updated": "22/12/2025", "topic": "Cargo no reconocido"},
    "R-301": {"owner": "test-a", "status": "Dato inválido", "updated": "", "topic": "Cargo no reconocido"},
}
CASE_RE = re.compile(r"\bR-\d{3}\b", re.IGNORECASE)


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


def say(es, pt, language):
    return pt if language == "pt" else es


def respond(message, token, conversation, authority, repository, model, *, language="es", router="learned", fail_tool=False, now=None):
    """Return verified facts only; classifier may suggest a route but cannot use tools."""
    language = "pt" if language == "pt" else "es"
    message = message.strip()[:600]
    try:
        subject = authority.verify(token, now=now)
    except SessionError:
        return Reply("auth_required", say("Inicia una nueva sesión de prueba para continuar.",
                                          "Inicie uma nova sessão de teste para continuar.", language))
    if not message:
        return Reply("clarify", say("Escribe tu consulta.", "Escreva sua solicitação.", language))
    match = CASE_RE.search(message)
    case_id = match.group().upper() if match else ""
    # Route a short case number as a continuation of a prior status question.
    if conversation.waiting_for_case and case_id and len(message) < 65:
        intent = "status"
    else:
        intent = (learned(message, model) if router == "learned" else baseline(message))
    conversation.turns.append({"role": "customer", "language": language, "text": message})
    if len(conversation.turns) > 12:
        conversation.turns = conversation.turns[-12:]
    if intent == "status":
        if not case_id:
            conversation.waiting_for_case = True
            return Reply("clarify", say("Indica el folio de tu reclamación (por ejemplo, R-101).",
                                         "Informe o número da sua reclamação (por exemplo, R-101).", language), intent)
        conversation.waiting_for_case = False
        record = None
        attempts = 0
        for attempts in (1, 2):
            try:
                record = repository.lookup(subject, case_id, fail=fail_tool)
                break
            except ToolError:
                pass
        if record is None and attempts == 2 and fail_tool:
            return _handoff("tool_failure", intent, subject, case_id, None, language, message, attempts)
        if record is None:
            return Reply("denied", say("No encuentro ese folio en tu sesión de prueba. Comprueba el número o solicita atención humana.",
                                       "Não encontro esse protocolo na sua sessão de teste. Confira o número ou peça atendimento humano.", language),
                         intent, attempts=attempts)
        if record["status"] not in ("En proceso", "Resuelto", "Escalado") or not record["updated"]:
            return _handoff("invalid_data", intent, subject, case_id, None, language, message, attempts)
        if record["status"] == "Escalado":
            return _handoff("escalated", intent, subject, case_id, record, language, message, attempts)
        if language == "pt":
            status = {"En proceso": "Em andamento", "Resuelto": "Resolvido"}.get(record["status"], record["status"])
            body = f"No registro fictício {case_id}, o status era **{status}** em {record['updated']}. Fonte: sistema simulado de reclamações. Cópia de {AS_OF}; não é o estado atual de um banco."
        else:
            body = f"En el expediente ficticio {case_id}, el estado era **{record['status']}** al {record['updated']}. Fuente: sistema simulado de reclamaciones. Copia del {AS_OF}; no es el estado actual de un banco."
        return Reply("resolved", body, intent, case_id, f"mock-case:{case_id}; updated={record['updated']}", attempts)
    conversation.waiting_for_case = False
    if intent in ("human", "new_dispute"):
        # New disputes need a human; this prototype cannot create or reverse transactions.
        return _handoff("new_dispute" if intent == "new_dispute" else "requested", intent,
                        subject, "", None, language, message, 0)
    if intent == "unclear":
        return Reply("clarify", say("¿Quieres consultar el estado de una reclamación, reportar un cargo o hablar con una persona?",
                                    "Quer consultar o andamento de uma reclamação, contestar uma cobrança ou falar com uma pessoa?", language), intent)
    return Reply("unsupported", say("Ese trámite no está disponible en esta demo. Pide atención humana si necesitas ayuda.",
                                     "Esse serviço não está disponível nesta demonstração. Peça atendimento humano se precisar de ajuda.", language), intent)


def _handoff(reason, intent, subject, case_id, record, language, message, attempts):
    questions = {
        "tool_failure": "Verificar disponibilidad de la fuente y consultar el estado antes de informar al cliente",
        "escalated": "Revisar el motivo de la escalación y comunicar el siguiente paso",
        "new_dispute": "Confirmar los detalles del cargo y decidir la apertura del reclamo bajo política",
        "requested": "Aclarar la solicitud concreta con el cliente",
        "invalid_data": "Corregir el estado o la fecha de la fuente antes de informar al cliente",
    }
    packet = {"reason": reason, "test_subject": subject, "request": message[:180],
              "verified_case": case_id if record is not None else None,
              "verified_status": record["status"] if record is not None else None,
              "source": f"mock-case:{case_id}" if record is not None else None,
              "actions": ["read_only_lookup"] if record is not None else [],
              "unresolved": questions[reason]}
    phrase = say("Preparé una derivación de prueba a un agente; no se creó ni modificó ninguna reclamación.",
                 "Preparei um encaminhamento de teste para atendimento humano; nenhuma reclamação foi criada ou alterada.", language)
    return Reply("handoff", phrase, intent, case_id if record else "",
                 packet["source"] or "", attempts, packet)
