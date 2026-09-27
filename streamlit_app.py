"""Factored demo: secure read-only synthetic complaint status workflow."""

import json
from pathlib import Path
import time

import streamlit as st

from intent import make_model
from service import ACCOUNTS, CaseRepository, Conversation, SessionAuthority, SessionError, respond


st.set_page_config(page_title="Estado de reclamaciones | demo", page_icon="🔎", layout="centered")


@st.cache_resource
def resources():
    return SessionAuthority(), CaseRepository(), make_model()


authority, repository, model = resources()
st.title("Estado de reclamaciones")
st.caption("Prototipo del hackathon Factored · expedientes, identidades y sesiones ficticios · copia de 2025")

with st.sidebar:
    st.header("Sesión de prueba")
    account = st.selectbox("Perfil ficticio", list(ACCOUNTS))
    st.caption("PIN Alicia: 1379 · PIN Bruno: 2468. Son códigos públicos de una simulación.")
    pin = st.text_input("PIN de prueba", type="password", max_chars=8)
    if st.button("Iniciar sesión", use_container_width=True):
        try:
            st.session_state.token = authority.issue(account, pin)
            st.session_state.conversation = Conversation()
            st.session_state.messages = []
            st.success("Sesión ficticia activa durante 10 minutos")
        except SessionError:
            st.error("PIN incorrecto para ese perfil")
    if st.button("Simular vencimiento", use_container_width=True):
        if "token" in st.session_state:
            st.session_state.token = authority.issue(account, ACCOUNTS[account][1], now=time.time()-700, ttl=1)
            st.success("Sesión vencida para la siguiente consulta")
    if st.button("Cerrar sesión", use_container_width=True):
        for key in ("token", "conversation", "messages"):
            st.session_state.pop(key, None)
        st.rerun()
    lang = st.radio("Idioma", ["Español", "Português"], horizontal=True)
    language = "pt" if lang == "Português" else "es"
    simulate_error = st.checkbox("Simular falla de consulta", value=False)
    st.caption("La lógica de autorización reside en el servidor. Este inicio de sesión abierto es solo un simulador, no una identidad bancaria.")

st.info("Prueba: Alicia puede consultar R-101 y R-102; Bruno, R-201. Intenta consultar el expediente del otro perfil.")
with st.expander("Alcance y evidencia"):
    st.write("Consulta de estado, aclaración de folio y derivación humana. Nunca se inician disputas, se autorizan pagos ni se actualizan casos.")
    file = Path(__file__).with_name("analysis_evidence.json")
    if file.exists():
        report = json.loads(file.read_text(encoding="utf-8"))
        st.write(f"Datos del reto: {report['interactions_2025']['rows']:,} interacciones y {report['complaints_2025']['rows']:,} reclamaciones en 2025; "
                 f"{report['transcripts_jan_2025']['rows']:,} transcripciones de enero con solo "
                 f"{report['transcripts_jan_2025']['distinct_customer_texts']} textos distintos de clientes.")
    st.caption("Los textos y estados visibles en esta aplicación fueron creados para la demo; no son expedientes del banco.")

if "token" not in st.session_state:
    st.warning("Ingresa con un perfil de prueba para consultar.")
else:
    st.session_state.setdefault("conversation", Conversation())
    st.session_state.setdefault("messages", [])
    for speaker, body in st.session_state.messages:
        with st.chat_message(speaker):
            st.markdown(body)
    prompt = st.chat_input("Pregunta por una reclamación ficticia…" if language == "es" else "Pergunte por uma reclamação fictícia…", max_chars=600)
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        reply = respond(prompt, st.session_state.token, st.session_state.conversation,
                        authority, repository, model, language=language, fail_tool=simulate_error)
        with st.chat_message("assistant"):
            st.markdown(reply.text)
            if reply.handoff:
                with st.expander("Paquete para agente / Contexto para atendente"):
                    st.json(reply.handoff)
        st.session_state.messages.extend([("user", prompt), ("assistant", reply.text)])
        st.caption(f"Resultado: {reply.kind} · consulta: {reply.evidence or 'sin datos de expediente'} · intentos: {reply.attempts}")
