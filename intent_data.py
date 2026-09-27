"""Participant-authored synthetic utterances; none come from the challenge transcripts.

The held-out examples are separately written. They must not enter training.
"""

TRAIN = {
    "status": {
        "es": [
            "Quiero saber el estado de mi reclamación", "¿Cómo va el reclamo que presenté?",
            "Consulta el seguimiento de mi caso", "¿Ya resolvieron mi queja?",
            "Dime si mi solicitud sigue abierta", "¿Hay novedades sobre el expediente?",
            "Necesito ver el avance del reporte", "¿Qué pasó con el caso que abrí?",
            "Verifica el estado de mi disputa", "¿Mi reclamación está cerrada?",
            "Busco el resultado de mi reclamo", "¿En qué etapa está mi caso?",
            "Quiero consultar la respuesta al ticket", "¿Ya contestaron mi reclamación?",
            "Revisar mi queja pendiente", "¿Cuál es el progreso del trámite?",
        ],
        "pt": [
            "Quero saber o status da minha reclamação", "Como está o andamento do meu protocolo?",
            "Consulte o acompanhamento do meu caso", "Minha contestação já foi resolvida?",
            "Preciso verificar se minha solicitação está aberta", "Há novidades sobre minha queixa?",
            "Qual é a situação do chamado?", "Veja a resposta ao meu pedido",
            "Meu processo já foi encerrado?", "Gostaria de acompanhar minha contestação",
            "Qual o progresso da reclamação?", "Tem atualização do meu protocolo?",
            "Verificar resultado do atendimento", "O banco respondeu meu caso?",
            "Quero consultar minha demanda pendente", "Em que etapa está meu pedido?",
        ],
    },
    "new_dispute": {
        "es": [
            "No reconozco un cargo en mi tarjeta", "Quiero reclamar una compra que no hice",
            "Necesito abrir una disputa por un movimiento", "Me cobraron algo que desconozco",
            "Hay un pago no autorizado en mi cuenta", "Registrar un nuevo reclamo por cargo duplicado",
            "Tengo un cobro indebido reciente", "Quiero reportar una transacción sospechosa",
            "Ayúdame a impugnar una compra", "Me apareció un cargo fraudulento",
            "Deseo presentar una reclamación nueva", "Alguien usó mi tarjeta sin permiso",
        ],
        "pt": [
            "Não reconheço uma cobrança no cartão", "Quero contestar uma compra que não fiz",
            "Preciso abrir uma disputa de transação", "Fizeram uma cobrança desconhecida",
            "Há um pagamento não autorizado na conta", "Registrar reclamação por cobrança duplicada",
            "Tenho uma cobrança indevida recente", "Quero comunicar uma transação suspeita",
            "Preciso impugnar uma compra", "Apareceu um débito fraudulento",
            "Desejo apresentar uma nova reclamação", "Usaram meu cartão sem autorização",
        ],
    },
    "human": {
        "es": [
            "Quiero hablar con una persona", "Comunícame con un agente",
            "Necesito atención humana", "Pásame con un asesor",
            "Quisiera que un especialista revise esto", "Transfiéreme a soporte",
            "Prefiero llamar a un representante", "Deseo atención de un ejecutivo",
            "Quiero un operador real", "Me gustaría escalar con alguien del banco",
        ],
        "pt": [
            "Quero falar com uma pessoa", "Transfira para um atendente",
            "Preciso de atendimento humano", "Passe para um agente",
            "Gostaria que um especialista analisasse", "Encaminhe para o suporte",
            "Prefiro falar com um representante", "Quero atendimento de um funcionário",
            "Preciso de um operador de verdade", "Quero encaminhar para alguém do banco",
        ],
    },
    "other": {
        "es": [
            "¿Cuál es el saldo de mi cuenta?", "¿Qué tasa tiene un crédito hipotecario?",
            "Quiero cambiar mi contraseña", "¿Dónde está la sucursal más cercana?",
            "Necesito transferir dinero", "Quiero contratar un seguro",
            "¿Cuáles son los horarios de atención?", "Muéstrame mis movimientos recientes",
            "¿Puedo aumentar el límite de mi tarjeta?", "Quiero pagar un préstamo",
        ],
        "pt": [
            "Qual é o saldo da minha conta?", "Qual a taxa de um empréstimo imobiliário?",
            "Quero alterar minha senha", "Onde fica a agência mais próxima?",
            "Preciso transferir dinheiro", "Quero contratar um seguro",
            "Quais são os horários de atendimento?", "Mostre meus lançamentos recentes",
            "Posso aumentar o limite do cartão?", "Quero pagar um financiamento",
        ],
    },
}

HOLDOUT = [
    ("es", "status", "¿En qué quedó la inconformidad que ingresé?"),
    ("es", "status", "Revisemos el folio R-101, ¿sigue en trámite?"),
    ("es", "status", "¿Me dieron respuesta al radicado?"),
    ("es", "status", "Necesito saber si atendieron mi reporte previo"),
    ("es", "status", "Me interesa conocer la fase actual de la gestión"),
    ("pt", "status", "O que aconteceu com a manifestação que registrei?"),
    ("pt", "status", "O protocolo R-201 ainda está em análise?"),
    ("pt", "status", "Já recebi retorno sobre o registro anterior?"),
    ("pt", "status", "Poderia conferir a etapa atual dessa demanda?"),
    ("pt", "status", "O tratamento do meu pedido terminou?"),
    ("es", "new_dispute", "Aparece una compra extraña que no autoricé"),
    ("es", "new_dispute", "Desconozco ese débito y necesito denunciarlo"),
    ("es", "new_dispute", "Alguien pagó con mi plástico sin avisarme"),
    ("es", "new_dispute", "Abre un caso para devolver un cargo que no hice"),
    ("pt", "new_dispute", "Tem uma despesa estranha que eu não aprovei"),
    ("pt", "new_dispute", "Debitaram um valor que eu não autorizei"),
    ("pt", "new_dispute", "Quero contestar um lançamento desconhecido"),
    ("pt", "new_dispute", "Uma compra apareceu no extrato sem minha permissão"),
    ("es", "human", "¿Puede atenderme alguien del equipo?"),
    ("es", "human", "Conéctame directamente con un empleado"),
    ("es", "human", "Esto requiere revisión por un profesional"),
    ("pt", "human", "Me coloque em contato com um funcionário"),
    ("pt", "human", "Pode me encaminhar a uma pessoa?"),
    ("pt", "human", "Preciso de avaliação por um atendente"),
    ("es", "other", "¿Se puede retirar efectivo sin tarjeta?"),
    ("es", "other", "Quisiera información sobre puntos de recompensa"),
    ("es", "other", "¿Cómo actualizo mi dirección de correspondencia?"),
    ("pt", "other", "Existe saque sem usar o cartão?"),
    ("pt", "other", "Onde posso ver os pontos de recompensa?"),
    ("pt", "other", "Como mudar meu endereço cadastrado?"),
]
