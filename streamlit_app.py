"""Bilingual public demo of a read-only, simulated complaint-status workflow."""

from html import escape
import json
from pathlib import Path
import time

import streamlit as st

from intent import make_model
from service import ACCOUNTS, CaseRepository, Conversation, SessionAuthority, SessionError, contains_sensitive_number, respond


st.set_page_config(
    page_title="Estado de reclamaciones | Factored demo",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def resources():
    return SessionAuthority(), CaseRepository(), make_model()


authority, repository, model = resources()
COPY = {
    "es": {
        "title": "Tu reclamación, paso a paso",
        "subtitle": "Consulta un folio de prueba, revisa qué se verificó y elige el siguiente paso.",
        "tag": "Prototipo · expedientes ficticios · copia de 2025",
        "tabs": ["Mi expediente", "Datos y resultados", "Cómo funciona"],
        "start": "Comienza con un perfil de prueba",
        "intro": "Los perfiles y PIN son públicos y ficticios. No uses datos bancarios reales.",
        "profile": "Perfil ficticio", "pin": "PIN de prueba",
        "login": "Iniciar sesión de prueba", "bad_pin": "PIN incorrecto para ese perfil.",
        "session": "Sesión de prueba para {name} · duración máxima: 10 minutos.",
        "try": "Consulta guiada", "own": "Consultar mi folio",
        "flow_intro": "Primero comprobamos el folio y el permiso. Después mostramos solo hechos de la fuente y acciones posibles. La consulta es de solo lectura.",
        "journey_steps": ["Sesión de prueba", "Consulta de folio", "Siguiente paso"],
        "workspace": "Mi expediente", "folio_label": "Folio de prueba",
        "folio_help": "Prueba con {cases}. Son datos inventados; también puedes escribir otro folio.",
        "folio_missing": "Escribe un folio para comenzar.",
        "check": "Consultar estado", "verified_label": "Información verificada para esta sesión",
        "status_label": "Estado", "date_label": "Actualizado", "snapshot_label": "Copia del {date} · fuente: {source}. No es información bancaria actual.",
        "empty_result": "Aún no hay un expediente verificado. Introduce un folio para comenzar.",
        "next_title": "Tu siguiente paso", "actions_title": "Puedes continuar con",
        "plans": {
            "ready": "Consulta un folio con el formulario o pide orientación si todavía no lo tienes.",
            "in_progress": "El expediente está en proceso en esta copia. Puedes comprobar la fecha, preguntar por el motivo o preparar atención humana.",
            "resolved_case": "La copia muestra el expediente como resuelto. Si necesitas aclararlo, prepara atención humana.",
            "unavailable": "No hay un estado que pueda mostrar en esta sesión. Comprueba el folio en el formulario o solicita ayuda.",
            "need_case": "Para consultar el estado necesito un único folio. Escríbelo en el formulario de la izquierda.",
            "need_clarification": "Elige una acción guiada o escribe una pregunta más concreta.",
            "outside_scope": "Esta demo no puede realizar ese trámite. Puedes consultar un folio o pedir atención humana.",
            "handoff_tool_failure": "La fuente no respondió. El contexto de prueba quedó preparado sin estado. Desactiva la falla simulada y vuelve a consultar el folio si quieres reintentarlo.",
            "handoff_invalid_data": "La fuente devolvió datos incompletos. No mostraré un estado hasta que una persona los revise.",
            "handoff_reason_unknown": "Verifiqué estado y fecha, pero la fuente no documenta el motivo. Preparé la pregunta para revisión humana.",
            "handoff_escalated": "El registro aparece escalado; preparé su contexto para revisión humana.",
            "handoff_new_dispute": "Un cargo nuevo requiere evaluación humana. Esta demo no abre reclamaciones ni modifica operaciones.",
            "handoff_requested": "Preparé el contexto de prueba para atención humana. No se envió a un agente real.",
        },
        "actions": {"date": "Verificar fecha", "reason": "Preguntar por el motivo", "human": "Preparar derivación (demo)"},
        "orientation": "No tengo el folio", "free_question": "Otra pregunta (opcional)",
        "free_placeholder": "Escribe una pregunta sin datos bancarios reales…", "send": "Consultar",
        "empty_question": "Escribe una pregunta antes de enviarla.",
        "history": "Ver historial de la consulta", "history_empty": "Todavía no hay interacciones.",
        "audit": "Verificación y pasos ejecutados", "simulated_handoff": "Paquete simulado: solo visible en esta sesión. No se envía a nadie.",
        "examples_title": "Escenarios de prueba", "test_own": "Consultar folio propio",
        "test_foreign": "Probar folio ajeno", "test_ambiguous": "Consulta sin folio",
        "foreign": "Consultar un folio ajeno", "human": "Pedir un agente",
        "human_with_case": "Pedir agente con mi folio",
        "ambiguous": "Consulta sin folio",
        "followup": "Preguntar por la fecha del último folio",
        "dispute": "Reportar un cargo", "logout": "Cerrar sesión",
        "advanced": "Simular errores", "fail": "Simular falla de la fuente",
        "expire": "Simular vencimiento de la sesión",
        "expired": "La sesión de prueba venció. Inicia una nueva para continuar.",
        "input": "Pregunta por una reclamación ficticia…",
        "case_input": "Escribe un solo folio: R-101 o R-102…",
        "waiting_hint": "Para continuar, escribe un único folio ficticio. También puedes pedir atención humana.",
        "context_hint": "Folio confirmado en este chat: {case_id}. Puedes preguntar por su fecha sin repetir el número.",
        "redacted": "[Número largo oculto por seguridad; escribe la pregunta sin datos reales]",
        "handoff": "Contexto preparado para atención humana",
        "verified_summary": "Folio verificado: {case_id} · estado: {status} · fecha: {updated}. Fuente simulada consultada otra vez; copia del {as_of}.",
        "unverified_summary": "No hay estado verificado para adjuntar. Un agente tendría que confirmar el folio en la fuente.",
        "pending_action": "Pendiente para el agente: {action}",
        "result": "Resultado", "source": "fuente", "attempts": "intentos",
        "trace_title": "Qué hizo el asistente",
        "trace_labels": {
            "session_verified": "Validó la sesión de prueba", "session_rejected": "La sesión no está vigente",
            "route_status": "Identificó una consulta de estado", "route_human": "Identificó una solicitud de agente",
            "route_new_dispute": "Identificó un cargo que requiere atención humana",
            "route_unclear": "La intención necesita aclaración", "route_other": "La solicitud está fuera del alcance",
            "case_from_context": "Usó el folio confirmado en este chat, sin reutilizar su estado",
            "ask_question": "Pidió aclarar la solicitud", "ask_case": "Pidió un folio",
            "ask_one_case": "Pidió elegir un solo folio", "sensitive_input_blocked": "Rechazó un número largo",
            "lookup_checked": "La fuente comprobó el folio y su autorización",
            "lookup_failed": "La consulta a la fuente falló en dos intentos",
            "not_available": "No hay folio disponible en esta sesión",
            "snapshot_answered": "Respondió con estado y fecha de la copia de 2025",
            "human_handoff": "Preparó el contexto para atención humana",
            "outside_scope": "Informó que el trámite no está disponible",
        },
        "kind_labels": {"resolved": "Consulta resuelta", "handoff": "Derivación simulada",
                        "denied": "No disponible", "clarify": "Falta aclaración",
                        "unsupported": "Fuera de alcance", "auth_required": "Nueva sesión requerida"},
        "none": "sin datos del expediente",
        "privacy": "Un folio ajeno y uno inexistente reciben la misma respuesta. El permiso se verifica antes de mostrar un estado.",
        "data": "La necesidad, medida con los datos del reto",
        "interactions": "Interacciones · 2025", "complaints": "Reclamaciones · 2025",
        "charge": "Cargo no reconocido",
        "origin": "Conteos agregados de los archivos entregados por el organizador. Los folios visibles en esta demo son inventados.",
        "chart_title": "Estado de las reclamaciones de 2025",
        "chart_status": "Estado", "chart_count": "Reclamaciones",
        "chart_labels": {"Open": "Abiertas", "In Process": "En proceso", "Resolved": "Resueltas",
                         "Escalated": "Escaladas", "Closed": "Cerradas", "Rejected": "Rechazadas"},
        "why_status": "{open_n} de {total} reclamaciones figuran abiertas o en proceso ({share}). Por separado, {followup} interacciones de la categoría «Queja» requerían seguimiento. Los archivos no vinculan cada reclamación con una interacción: esto motiva el flujo, pero no mide cuántas consultas de estado recibiría un banco.",
        "quality_title": "Calidad de datos",
        "quality": "En 4.903 transcripciones de enero hay solo 42 textos distintos de cliente; todos mencionan «saldo» y las mismas frases aparecen con distintas categorías. No usamos esos rótulos para entrenar. Tampoco se suministraron transcripciones en portugués.",
        "evaluation": "Comparación reproducible",
        "method": "96 frases ficticias para entrenar; 30 frases diferentes para medir el clasificador sin reglas (15 ES, 15 PT). Los mismos 25 escenarios miden los flujos completos; la versión con modelo incluye reglas de seguridad y contexto de sesión.",
        "metric": "Medida", "rules": "Reglas", "learned": "Modelo local",
        "accuracy": "Intenciones correctas", "f1": "F1 macro",
        "workflow": "Flujos correctos", "escalation": "Derivaciones correctas",
        "automation": "Estados resueltos sin agente", "attempted": "Intentos en casos elegibles",
        "unsafe": "Divulgaciones indebidas observadas",
        "language_note": "El modelo acertó {es}/{total_es} frases en español y {pt}/{total_pt} en portugués. Cuando duda, pide aclaración. Estas cifras no permiten afirmar calidad para usuarios reales.",
        "subgroups": "Flujos correctos por idioma: español {es}/{total_es}, portugués {pt}/{total_pt}. Por perfil ficticio: Alicia {a}/{total_a}, Bruno {b}/{total_b}. Son grupos demasiado pequeños para evaluar equidad.",
        "cv_note": "Selección del modelo: 3 repeticiones de validación cruzada en las 96 frases de entrenamiento ({old}/{n} aciertos del anterior; {new}/{n} del actual). Son 288 predicciones de las mismas 96 frases, no 288 casos independientes. El conjunto de 30 frases ya se había inspeccionado en una versión anterior: evaluación exploratoria, no prueba ciega.",
        "limits": "Muestras pequeñas escritas por un solo autor; sin registros de clientes en la app. Latencia medida localmente; costo de API USD 0, alojamiento sin estimar. Cero fallas observadas no significa riesgo cero.",
        "design": "Cuatro decisiones de diseño",
        "steps": [
            ("01 · Sesión", "Un emisor ficticio firma un token que vence en 10 minutos. El PIN público reproduce la demo; no autentica a un cliente bancario."),
            ("02 · Intención", "Un clasificador local sugiere la ruta. Con incertidumbre se solicita aclaración; el modelo no determina permisos."),
            ("03 · Autorización", "El servicio verifica quién es dueño del folio antes de leer su estado. La respuesta incluye fuente y fecha de una copia estática."),
            ("04 · Fallo seguro", "Hay hasta dos intentos ante una falla de consulta. Casos escalados, datos inválidos y disputas nuevas se derivan a una persona."),
        ],
        "future": "Antes de operar en un banco",
        "roadmap": "Integrar identidad real, permisos y fuentes autorizadas con fecha de actualización; reunir consultas ES/PT consentidas y etiquetadas; hacer pruebas independientes más amplias, auditoría, monitoreo y políticas de retención.",
        "boundary": "Esta app no abre reclamaciones, no mueve dinero y no consulta un banco real.",
    },
    "pt": {
        "title": "Sua reclamação, passo a passo",
        "subtitle": "Consulte um protocolo de teste, veja o que foi verificado e escolha o próximo passo.",
        "tag": "Protótipo · registros fictícios · cópia de 2025",
        "tabs": ["Meu protocolo", "Dados e resultados", "Como funciona"],
        "start": "Comece com um perfil de teste",
        "intro": "Os perfis e PINs são públicos e fictícios. Não use dados bancários reais.",
        "profile": "Perfil fictício", "pin": "PIN de teste",
        "login": "Iniciar sessão de teste", "bad_pin": "PIN incorreto para este perfil.",
        "session": "Sessão de teste para {name} · duração máxima: 10 minutos.",
        "try": "Consulta guiada", "own": "Consultar meu protocolo",
        "flow_intro": "Primeiro verificamos o protocolo e a permissão. Depois mostramos apenas fatos da fonte e ações possíveis. A consulta é somente de leitura.",
        "journey_steps": ["Sessão de teste", "Consulta do protocolo", "Próximo passo"],
        "workspace": "Meu protocolo", "folio_label": "Protocolo de teste",
        "folio_help": "Teste com {cases}. São dados fictícios; você também pode informar outro protocolo.",
        "folio_missing": "Informe um protocolo para começar.",
        "check": "Consultar status", "verified_label": "Informação verificada para esta sessão",
        "status_label": "Status", "date_label": "Atualizado", "snapshot_label": "Cópia de {date} · fonte: {source}. Não é informação bancária atual.",
        "empty_result": "Ainda não há um protocolo verificado. Informe um protocolo para começar.",
        "next_title": "Seu próximo passo", "actions_title": "Você pode continuar com",
        "plans": {
            "ready": "Consulte um protocolo pelo formulário ou peça orientação se ainda não o tem.",
            "in_progress": "O protocolo está em andamento nesta cópia. Você pode verificar a data, perguntar o motivo ou preparar atendimento humano.",
            "resolved_case": "A cópia mostra o protocolo como resolvido. Se precisar de esclarecimentos, prepare atendimento humano.",
            "unavailable": "Não há status que eu possa mostrar nesta sessão. Confira o protocolo no formulário ou peça ajuda.",
            "need_case": "Para consultar o status, preciso de um único protocolo. Informe-o no formulário à esquerda.",
            "need_clarification": "Escolha uma ação guiada ou escreva uma pergunta mais específica.",
            "outside_scope": "Esta demonstração não pode realizar esse serviço. Consulte um protocolo ou peça atendimento humano.",
            "handoff_tool_failure": "A fonte não respondeu. O contexto de teste ficou pronto sem status. Desative a falha simulada e consulte novamente o protocolo se quiser tentar outra vez.",
            "handoff_invalid_data": "A fonte retornou dados incompletos. Não mostrarei um status até que uma pessoa os revise.",
            "handoff_reason_unknown": "Confirmei status e data, mas a fonte não documenta o motivo. Preparei a pergunta para revisão humana.",
            "handoff_escalated": "O registro está encaminhado; preparei o contexto para revisão humana.",
            "handoff_new_dispute": "Uma nova cobrança exige avaliação humana. Esta demonstração não abre reclamações nem altera operações.",
            "handoff_requested": "Preparei o contexto de teste para atendimento humano. Ele não foi enviado a um atendente real.",
        },
        "actions": {"date": "Verificar data", "reason": "Perguntar o motivo", "human": "Preparar encaminhamento (demo)"},
        "orientation": "Não tenho o protocolo", "free_question": "Outra pergunta (opcional)",
        "free_placeholder": "Escreva uma pergunta sem dados bancários reais…", "send": "Consultar",
        "empty_question": "Escreva uma pergunta antes de enviar.",
        "history": "Ver histórico da consulta", "history_empty": "Ainda não há interações.",
        "audit": "Verificação e etapas realizadas", "simulated_handoff": "Pacote simulado: visível apenas nesta sessão. Não é enviado a ninguém.",
        "examples_title": "Cenários de teste", "test_own": "Consultar meu protocolo",
        "test_foreign": "Testar protocolo de outra pessoa", "test_ambiguous": "Pergunta sem protocolo",
        "foreign": "Consultar protocolo de outra pessoa", "human": "Pedir atendente",
        "human_with_case": "Pedir atendente com meu protocolo",
        "ambiguous": "Pergunta sem protocolo",
        "followup": "Perguntar a data do último protocolo",
        "dispute": "Contestar uma cobrança", "logout": "Encerrar sessão",
        "advanced": "Simular erros", "fail": "Simular falha na fonte",
        "expire": "Simular expiração da sessão",
        "expired": "A sessão de teste expirou. Inicie uma nova para continuar.",
        "input": "Pergunte sobre uma reclamação fictícia…",
        "case_input": "Informe um único protocolo: R-101 ou R-102…",
        "waiting_hint": "Para continuar, informe um único protocolo fictício. Você também pode pedir atendimento humano.",
        "context_hint": "Protocolo confirmado neste chat: {case_id}. Você pode perguntar a data sem repetir o número.",
        "redacted": "[Número longo ocultado por segurança; pergunte sem dados reais]",
        "handoff": "Contexto preparado para atendimento humano",
        "verified_summary": "Protocolo verificado: {case_id} · status: {status} · data: {updated}. Fonte simulada consultada novamente; cópia de {as_of}.",
        "unverified_summary": "Nenhum status verificado para anexar. Um atendente teria que confirmar o protocolo na fonte.",
        "pending_action": "Pendente para atendimento: {action}",
        "result": "Resultado", "source": "fonte", "attempts": "tentativas",
        "trace_title": "O que o assistente fez",
        "trace_labels": {
            "session_verified": "Validou a sessão de teste", "session_rejected": "A sessão não está válida",
            "route_status": "Identificou uma consulta de status", "route_human": "Identificou um pedido de atendente",
            "route_new_dispute": "Identificou uma cobrança que precisa de atendimento humano",
            "route_unclear": "A intenção precisa de esclarecimento", "route_other": "A solicitação está fora do escopo",
            "case_from_context": "Usou o protocolo confirmado neste chat, sem reutilizar o status",
            "ask_question": "Pediu para esclarecer a solicitação", "ask_case": "Pediu o protocolo",
            "ask_one_case": "Pediu para escolher um único protocolo", "sensitive_input_blocked": "Rejeitou um número longo",
            "lookup_checked": "A fonte verificou o protocolo e a autorização",
            "lookup_failed": "A consulta à fonte falhou em duas tentativas",
            "not_available": "Nenhum protocolo disponível nesta sessão",
            "snapshot_answered": "Respondeu com status e data da cópia de 2025",
            "human_handoff": "Preparou o contexto para atendimento humano",
            "outside_scope": "Informou que o serviço não está disponível",
        },
        "kind_labels": {"resolved": "Consulta resolvida", "handoff": "Encaminhamento simulado",
                        "denied": "Não disponível", "clarify": "Precisa esclarecer",
                        "unsupported": "Fora do escopo", "auth_required": "Nova sessão necessária"},
        "none": "sem dados do protocolo",
        "privacy": "Um protocolo de outra pessoa e um inexistente recebem a mesma resposta. A permissão é verificada antes de mostrar o status.",
        "data": "A necessidade, medida com os dados do desafio",
        "interactions": "Interações · 2025", "complaints": "Reclamações · 2025",
        "charge": "Cobrança não reconhecida",
        "origin": "Contagens agregadas dos arquivos fornecidos pelo organizador. Os protocolos visíveis nesta demonstração são inventados.",
        "chart_title": "Status das reclamações de 2025",
        "chart_status": "Status", "chart_count": "Reclamações",
        "chart_labels": {"Open": "Abertas", "In Process": "Em andamento", "Resolved": "Resolvidas",
                         "Escalated": "Escaladas", "Closed": "Encerradas", "Rejected": "Rejeitadas"},
        "why_status": "{open_n} de {total} reclamações estão abertas ou em andamento ({share}). Separadamente, {followup} interações da categoria «Queja» exigiam acompanhamento. Os arquivos não vinculam cada reclamação a uma interação: isso motiva o fluxo, mas não mede quantas consultas de status um banco receberia.",
        "quality_title": "Qualidade dos dados",
        "quality": "Em 4.903 transcrições de janeiro há apenas 42 textos diferentes de clientes; todos mencionam «saldo» e as frases aparecem em várias categorias. Não usamos esses rótulos para treinar. Também não foram fornecidas transcrições em português.",
        "evaluation": "Comparação reproduzível",
        "method": "96 frases fictícias de treinamento; 30 frases diferentes para medir o classificador sem regras (15 ES, 15 PT). Os mesmos 25 cenários medem os fluxos completos; a versão com modelo inclui regras de segurança e contexto da sessão.",
        "metric": "Medida", "rules": "Regras", "learned": "Modelo local",
        "accuracy": "Intenções corretas", "f1": "F1 macro",
        "workflow": "Fluxos corretos", "escalation": "Encaminhamentos corretos",
        "automation": "Status resolvidos sem atendente", "attempted": "Tentativas em casos elegíveis",
        "unsafe": "Divulgações indevidas observadas",
        "language_note": "O modelo acertou {es}/{total_es} frases em espanhol e {pt}/{total_pt} em português. Quando há dúvida, pede esclarecimento. Esses resultados não demonstram qualidade para clientes reais.",
        "subgroups": "Fluxos corretos por idioma: espanhol {es}/{total_es}, português {pt}/{total_pt}. Por perfil fictício: Alicia {a}/{total_a}, Bruno {b}/{total_b}. Os grupos são pequenos demais para avaliar equidade.",
        "cv_note": "Escolha do modelo: 3 repetições de validação cruzada nas 96 frases de treinamento ({old}/{n} acertos do anterior; {new}/{n} do atual). São 288 previsões das mesmas 96 frases, não 288 casos independentes. O conjunto de 30 frases já havia sido examinado em uma versão anterior: avaliação exploratória, não teste cego.",
        "limits": "Amostras pequenas escritas por um só autor; sem dados de clientes no app. Latência medida localmente; custo de API USD 0, hospedagem não estimada. Nenhuma falha observada não significa risco zero.",
        "design": "Quatro decisões de projeto",
        "steps": [
            ("01 · Sessão", "Um emissor fictício assina um token que expira em 10 minutos. O PIN público reproduz a demonstração; não autentica um cliente bancário."),
            ("02 · Intenção", "Um classificador local sugere o fluxo. Quando há incerteza, pede esclarecimento; o modelo não decide permissões."),
            ("03 · Autorização", "O serviço verifica o dono do protocolo antes de ler o status. A resposta inclui fonte e data de uma cópia estática."),
            ("04 · Falha segura", "Há no máximo duas tentativas se a fonte falhar. Casos escalados, dados inválidos e novas contestações são encaminhados a uma pessoa."),
        ],
        "future": "Antes de operar em um banco",
        "roadmap": "Integrar identidade real, permissões e fontes autorizadas com data de atualização; reunir consultas ES/PT consentidas e rotuladas; ampliar testes independentes, auditoria, monitoramento e políticas de retenção.",
        "boundary": "Este app não abre reclamações, não movimenta dinheiro e não consulta um banco real.",
    },
}
st.markdown("""
<style>
.block-container {max-width: 1120px; padding-top: 1.5rem; padding-bottom: 3rem}
.factored-hero {padding: 2rem 2.2rem; border-radius: 24px;
    background: linear-gradient(115deg, #17323e 0%, #1c4136 57%, #112c3b 100%);
    border: 1px solid #589781; color: #fff; margin: .5rem 0 1.5rem}
.factored-kicker {color: #a8f2ca; font-size: .82rem; font-weight: 750;
    letter-spacing: .14em; text-transform: uppercase}
.factored-hero h1 {font-size: clamp(2rem, 4vw, 3.5rem); line-height: 1.1;
    letter-spacing: -.03em; margin: .7rem 0; color: #fff}
.factored-hero p {font-size: 1.1rem; color: #e3f2ea; margin: .5rem 0}
.factored-tag {display: inline-block; border: 1px solid #85aa96; border-radius: 99px;
    color: #d0ebdd; padding: .3rem .75rem; margin-top: .6rem}
.factored-journey {display: flex; flex-wrap: wrap; gap: .6rem; margin: .7rem 0 1.4rem}
.factored-step {border: 1px solid #95ada3; border-radius: 12px; padding: .55rem .8rem;
    background: #f5f8f6; color: #244338; font-weight: 650; font-size: .87rem}
.factored-step.current {background: #d8f2de; border-color: #53936d; color: #17422a}
.factored-step.done {background: #e9eee9; color: #365747}
[data-testid="stMetric"] {border: 1px solid #7ba68766; border-radius: 16px;
    padding: .8rem 1rem; background: #70977d18}
.stButton button {border-radius: 10px}
</style>
""", unsafe_allow_html=True)

lang = "pt" if st.radio("Idioma / Idioma", ["Español", "Português"], horizontal=True) == "Português" else "es"
t = COPY[lang]
st.markdown(
    '<section class="factored-hero">'
    '<span class="factored-kicker">Factored · AI &amp; Data Hackathon 2026</span>'
    f'<h1>{escape(t["title"])}</h1><p>{escape(t["subtitle"])}</p>'
    f'<span class="factored-tag">{escape(t["tag"])}</span></section>',
    unsafe_allow_html=True,
)
demo, data_tab, design_tab = st.tabs(t["tabs"])

with demo:
    if "token" in st.session_state:
        try:
            authority.verify(st.session_state.token)
        except SessionError:
            for key in ("token", "profile", "conversation", "messages", "simulate_error"):
                st.session_state.pop(key, None)
            st.session_state.login_notice = t["expired"]
            st.rerun()
    if "token" not in st.session_state:
        st.subheader(t["start"])
        st.caption(t["intro"])
        if st.session_state.get("login_notice"):
            st.warning(st.session_state.pop("login_notice"))
        with st.form("login_form", clear_on_submit=True):
            account = st.selectbox(t["profile"], list(ACCOUNTS))
            st.caption("Alicia: 1379 · Bruno: 2468")
            pin = st.text_input(t["pin"], type="password", max_chars=8)
            submitted = st.form_submit_button(t["login"], type="primary")
        if submitted:
            try:
                st.session_state.token = authority.issue(account, pin)
            except SessionError:
                st.error(t["bad_pin"])
            else:
                st.session_state.profile = account
                st.session_state.conversation = Conversation()
                st.session_state.messages = []
                st.session_state.simulate_error = False
                st.rerun()
    else:
        profile = st.session_state.get("profile", "Alicia (prueba)")
        alicia = profile == "Alicia (prueba)"
        st.success(t["session"].format(name=profile.split(" (")[0]))
        st.caption(t["privacy"])
        conversation = st.session_state.setdefault("conversation", Conversation())
        messages = st.session_state.setdefault("messages", [])
        last = messages[-1] if messages and messages[-1]["speaker"] == "assistant" else None
        plan = last.get("plan") if last else None
        plan = plan or {"state": "ready", "actions": ("human",)}
        stages = ("done", "done" if last else "current", "current" if last else "")
        st.markdown(
            '<div class="factored-journey">' + ''.join(
                f'<span class="factored-step {style}">{index}. {escape(label)}</span>'
                for index, (style, label) in enumerate(zip(stages, t["journey_steps"]), 1)
            ) + '</div>', unsafe_allow_html=True,
        )
        st.subheader(t["try"])
        st.caption(t["flow_intro"])
        prompts = {
            "own": ("¿Cómo va R-101?" if alicia else "¿Cómo va R-201?") if lang == "es" else
                   ("Qual é o status do caso R-101?" if alicia else "Qual é o status do caso R-201?"),
            "foreign": ("¿Cómo va R-201?" if alicia else "¿Cómo va R-101?") if lang == "es" else
                       ("Qual é o status do caso R-201?" if alicia else "Qual é o status do caso R-101?"),
            "human": "Quiero hablar con un agente" if lang == "es" else "Quero falar com um atendente",
            "dispute": "No reconozco un cargo en mi tarjeta" if lang == "es" else
                       "Não reconheço uma cobrança no meu cartão",
            "ambiguous": "¿Cuál es el estado de mi reclamación?" if lang == "es" else
                         "Qual é o status do meu protocolo?",
            "date": "¿Cuándo se actualizó?" if lang == "es" else "Quando foi atualizado?",
            "reason": "¿Por qué está en ese estado?" if lang == "es" else "Por que está nesse status?",
        }
        prompt = None
        left, right = st.columns([1.35, 1], gap="large")
        with left:
            st.subheader(t["workspace"])
            st.caption(t["folio_help"].format(cases="R-101, R-102" if alicia else "R-201"))
            if conversation.waiting_for_case:
                st.info(t["waiting_hint"])
            with st.form("case_lookup", clear_on_submit=True):
                folio = st.text_input(t["folio_label"], placeholder="R-101", max_chars=30)
                check = st.form_submit_button(t["check"], type="primary", use_container_width=True)
            if check:
                if folio.strip():
                    prompt = ("Estado de " if lang == "es" else "Status do protocolo ") + folio.strip()
                else:
                    st.warning(t["folio_missing"])
            view = last.get("case_view") if last else None
            if view:
                with st.container(border=True):
                    st.caption(t["verified_label"])
                    st.subheader(view["case_id"])
                    state = view["status"]
                    if lang == "pt":
                        state = {"En proceso": "Em andamento", "Resuelto": "Resolvido",
                                 "Escalado": "Encaminhado"}.get(state, state)
                    state_col, date_col = st.columns(2)
                    state_col.metric(t["status_label"], state)
                    date_col.metric(t["date_label"], view["updated"])
                    st.caption(t["snapshot_label"].format(
                        date=view["snapshot_as_of"], source=view["source"],
                    ))
            elif not last:
                st.info(t["empty_result"])
            elif last.get("handoff") and "lookup_attempted" in last["handoff"].get("actions", []):
                st.caption(t["unverified_summary"])
            if last:
                st.markdown(last["text"])
                if last.get("handoff"):
                    st.caption(t["simulated_handoff"])
                    st.info(t["pending_action"].format(action=last["handoff"]["unresolved"]))
        with right:
            st.subheader(t["next_title"])
            with st.container(border=True):
                st.write(t["plans"].get(plan["state"], t["plans"]["need_clarification"]))
                if plan["actions"]:
                    st.caption(t["actions_title"])
                for action in plan["actions"]:
                    if st.button(t["actions"][action], key=f"guided_{action}", use_container_width=True):
                        prompt = prompts["human" if action == "human" else action]
                if not last or conversation.waiting_for_case:
                    if st.button(t["orientation"], key="orientation", use_container_width=True):
                        prompt = prompts["ambiguous"]
            if st.button(t["dispute"], use_container_width=True, key="dispute_example"):
                prompt = prompts["dispute"]
            with st.expander(t["free_question"]):
                with st.form("free_question_form", clear_on_submit=True):
                    typed = st.text_input(t["free_question"], placeholder=t["free_placeholder"],
                                          max_chars=600)
                    if st.form_submit_button(t["send"], use_container_width=True):
                        prompt = typed.strip()
                        if not prompt:
                            st.warning(t["empty_question"])
            with st.expander(t["examples_title"]):
                if st.button(t["test_own"], use_container_width=True, key="own_example"):
                    prompt = prompts["own"]
                if st.button(t["test_foreign"], use_container_width=True, key="foreign_example"):
                    prompt = prompts["foreign"]
                if st.button(t["test_ambiguous"], use_container_width=True, key="ambiguous_example"):
                    prompt = prompts["ambiguous"]
            with st.expander(t["advanced"]):
                st.checkbox(t["fail"], key="simulate_error")
                if st.button(t["expire"], key="expire_session"):
                    st.session_state.token = authority.issue(
                        profile, ACCOUNTS[profile][1], now=time.time() - 700, ttl=1,
                    )
                    st.rerun()
            if st.button(t["logout"], key="logout_session"):
                for key in ("token", "profile", "conversation", "messages", "simulate_error"):
                    st.session_state.pop(key, None)
                st.rerun()

        if last:
            with st.expander(t["audit"]):
                st.caption(
                    f'{t["result"]}: {t["kind_labels"].get(last["kind"], last["kind"])} · '
                    f'{t["source"]}: {last["evidence"] or t["none"]} · '
                    f'{t["attempts"]}: {last["attempts"]}'
                )
                for code in last.get("trace", ()):
                    st.write(f'• {t["trace_labels"].get(code, code)}')
                if last.get("handoff"):
                    st.caption(t["handoff"])
                    st.json(last["handoff"])
        with st.expander(t["history"]):
            if not messages:
                st.caption(t["history_empty"])
            for entry in messages[-12:]:
                with st.chat_message(entry["speaker"]):
                    st.markdown(entry["text"])

        if prompt:
            reply = respond(
                prompt, st.session_state.token, st.session_state.conversation,
                authority, repository, model, language=lang,
                fail_tool=st.session_state.get("simulate_error", False),
            )
            if reply.kind == "auth_required":
                for key in ("token", "profile", "conversation", "messages", "simulate_error"):
                    st.session_state.pop(key, None)
                st.session_state.login_notice = reply.text
                st.rerun()
            messages.extend([
                {"speaker": "user", "text": t["redacted"] if contains_sensitive_number(prompt) else prompt},
                {"speaker": "assistant", "text": reply.text, "kind": reply.kind,
                 "evidence": reply.evidence, "attempts": reply.attempts,
                 "handoff": reply.handoff, "trace": reply.trace,
                 "case_view": reply.case_view, "plan": reply.plan},
            ])
            if len(messages) > 24:
                del messages[:-24]
            st.rerun()

with data_tab:
    folder = Path(__file__).parent
    evidence = json.loads((folder / "analysis_evidence.json").read_text(encoding="utf-8"))
    report = json.loads((folder / "evaluation_results.json").read_text(encoding="utf-8"))
    st.subheader(t["data"])
    a, b, c = st.columns(3)
    a.metric(t["interactions"], f'{evidence["interactions_2025"]["rows"]:,}')
    b.metric(t["complaints"], f'{evidence["complaints_2025"]["rows"]:,}')
    c.metric(t["charge"], f'{evidence["complaints_2025"]["by_subcategory"]["Cargo no reconocido"]:,}')
    st.caption(t["origin"])
    statuses = evidence["complaints_2025"]["by_status"]
    st.subheader(t["chart_title"])
    st.bar_chart(
        [{t["chart_status"]: t["chart_labels"][name], t["chart_count"]: statuses[name]}
         for name in t["chart_labels"]],
        x=t["chart_status"], y=t["chart_count"], horizontal=True, height=340,
    )
    open_n = statuses["Open"] + statuses["In Process"]
    total = evidence["complaints_2025"]["rows"]
    followup = evidence["interactions_2025"]["requires_followup_by_reason"]["Queja"]
    st.caption(t["why_status"].format(
        open_n=f"{open_n:,}", total=f"{total:,}", followup=f"{followup:,}",
        share=f"{open_n / total:.1%}".replace(".", ","),
    ))
    st.warning(f'**{t["quality_title"]}.** {t["quality"]}')
    st.subheader(t["evaluation"])
    st.write(t["method"])
    basic = report["intent_holdout"]["keyword_baseline"]
    learned = report["intent_holdout"]["learned_router"]
    basic_flow = report["same_workflow_cases"]["baseline"]
    learned_flow = report["same_workflow_cases"]["learned"]
    rows = [
        (t["accuracy"], f'{basic["n"] - len(basic["errors"])}/{basic["n"]}',
         f'{learned["n"] - len(learned["errors"])}/{learned["n"]}'),
        (t["f1"], f'{basic["macro_f1"]:.3f}', f'{learned["macro_f1"]:.3f}'),
        (t["workflow"], f'{basic_flow["correct"]}/{basic_flow["n"]}',
         f'{learned_flow["correct"]}/{learned_flow["n"]}'),
        (t["automation"], f'{basic_flow["safe_status_resolutions"]}/{basic_flow["eligible_status_n"]}',
         f'{learned_flow["safe_status_resolutions"]}/{learned_flow["eligible_status_n"]}'),
        (t["attempted"], f'{basic_flow["attempted_eligible_status_n"]}/{basic_flow["eligible_status_n"]}',
         f'{learned_flow["attempted_eligible_status_n"]}/{learned_flow["eligible_status_n"]}'),
        (t["escalation"], f'{basic_flow["handoff_correct_n"]}/{basic_flow["handoff_required_n"]}',
         f'{learned_flow["handoff_correct_n"]}/{learned_flow["handoff_required_n"]}'),
        (t["unsafe"], f'{basic_flow["unsafe_disclosures_or_actions"]}/{basic_flow["n"]}',
         f'{learned_flow["unsafe_disclosures_or_actions"]}/{learned_flow["n"]}'),
    ]
    st.table([{t["metric"]: label, t["rules"]: baseline, t["learned"]: model_result}
              for label, baseline, model_result in rows])
    st.info(t["language_note"].format(
        es=learned["correct_by_language"]["es"], pt=learned["correct_by_language"]["pt"],
        total_es=learned["count_by_language"]["es"], total_pt=learned["count_by_language"]["pt"],
    ))
    st.caption(t["subgroups"].format(
        es=learned_flow["correct_by_language"]["es"],
        pt=learned_flow["correct_by_language"]["pt"],
        total_es=learned_flow["count_by_language"]["es"],
        total_pt=learned_flow["count_by_language"]["pt"],
        a=learned_flow["correct_by_test_identity"]["a"],
        b=learned_flow["correct_by_test_identity"]["b"],
        total_a=learned_flow["count_by_test_identity"]["a"],
        total_b=learned_flow["count_by_test_identity"]["b"],
    ))
    cv_original = report["training_cv"]["original_char_3_5_c1"]
    cv_selected = report["training_cv"]["selected_char_2_5_c2"]
    st.caption(t["cv_note"].format(old=cv_original["correct"], new=cv_selected["correct"],
                                   n=cv_selected["n_predictions"]))
    st.caption(t["limits"])

with design_tab:
    st.subheader(t["design"])
    for heading, description in t["steps"]:
        with st.container(border=True):
            st.markdown(f"**{heading}**")
            st.write(description)
    st.subheader(t["future"])
    st.write(t["roadmap"])
    st.warning(t["boundary"])
