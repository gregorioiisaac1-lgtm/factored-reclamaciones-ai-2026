# Tu siguiente paso, Isaac

Esta actualización v15 incluye la app v14, el chat y el panel Agent Trace / Observability,
la auditoría de las tres tablas con dos gráficas para la presentación, la bandeja de revisión simulada y la regresión de
desarrollo. No necesitas
instalar Python en Windows para probar la demo.

1. Descomprime `Factored_codigo_v15.zip`. Para cumplir el nombre pedido,
   crea otro repositorio **público** llamado
   `factored-hackathon-2026-isaac-gregorio`. Mantén el repositorio y la app
   actuales mientras preparas y compruebas la nueva entrega.
2. Sube los archivos **que están dentro del ZIP**, todos a la raíz del nuevo repositorio,
   conservando sus nombres. Es un paquete completo: incluye `requirements.txt`,
   `analysis_evidence.json`, `figures/` con dos PNG, código, pruebas y documentación. No subas ZIP de
   datos, PDF con credenciales ni claves de AWS.
3. En Streamlit Community Cloud, despliega **una app nueva** desde el repositorio
   nuevo, rama `main`, archivo `streamlit_app.py`. La
   [demo anterior](https://factored-reclamaciones-ai-2026-cnvgspggr4zr78r9m2fteb.streamlit.app/)
   queda como respaldo. Una vez lista la nueva, comprueba el recorrido:
   La app inicia una sesión ficticia de Alicia; en «Cliente» pulsa «Mi folio»
   o escribe `R-101` en el chat. Verás estado y fecha completos; en «Siguiente
   paso» pulsa «Preparar derivación (demo)» y después confirma con
   **«Confirmar derivación»**. Aparecerá un ID `T-...` únicamente si la app
   guardó el ticket y lo leyó de vuelta. El estado se consulta de nuevo y se
   verifica el permiso antes de guardarlo; no se envía a una persona real.
4. En **«Mesa de revisión»**, entra como analista de prueba con el PIN público
   `8642`. Busca el ID `T-...` y pulsa **«Confirmar recepción de prueba»**.
   Regresa a «Cliente»: el cliente ve que la recepción quedó confirmada.
   La bandeja solo guarda paquetes ficticios, no texto libre ni solicitudes a
   una persona real.
5. Para probar seguridad, como Alicia consulta `R-201`: la pantalla no mostrará
   el estado de Bruno y el servicio devolverá `status: 403`, `code: FORBIDDEN`;
   un folio inexistente da la misma respuesta. Para probar Bruno, cámbialo en el
   selector lateral: se reinicia la sesión y `R-101` queda fuera de sus permisos.
   Prueba también idioma portugués, «Sin folio» y falla de consulta. En «Pruebas
   de fallas» marca «Simular fallo al guardar»: no debe aparecer ID. Desmárcala
   y confirma de nuevo. Abre «Agent Trace / Observability» para ver ruta, RBAC,
   la entrada/salida autorizada de herramienta, el ID y el JSON de derivación. El ticket
   queda temporalmente en la cola local de esta instancia; no llega a un agente.
6. Escribe en el chat «Onde posso mudar o endereço do meu cadastro?»:
   debe indicar fuera de alcance sin preguntar un folio ni crear una disputa.
   Consulta «Tenho uma reclamação em aberto, pode conferir?» y después `R-102`:
   debe pedir el folio y mostrar solo el expediente autorizado. El paquete
   de derivación muestra `customer_id`, `verified_facts`, `open_questions`,
   `reason_for_escalation`, `sentiment` y `ticket_id` al confirmarse.

**Por qué elegimos este enfoque:** hay 22 356 expedientes en los datos de 2025,
incluidos 4 123 bajo «Cargo no reconocido». De 4 903 transcripciones de enero,
todas incluyen «saldo», hay solo 42 textos de cliente distintos y las mismas frases
se asignan a múltiples categorías. Entrenar el modelo con esas etiquetas daría
una evaluación engañosa. Usamos 96 consultas ficticias escritas para entrenar
el enrutador local y otras 30 para probarlo.

**Auditoría añadida:** FCR marcado en interacciones: 76,60 %; tiempo medio de
resolución entre 5 324 expedientes con tiempos válidos: 15,64 días. El 5,14 %
figura como `Escalated` en una foto del estado, y el 9,96 % de las interacciones
marca escalamiento a supervisor; no equivalen a la proporción que acabó con
atención humana. País y ROI real quedan sin cifra porque faltan los datos
necesarios. Las dos gráficas están en `figures/` y las definiciones de los
indicadores en `analysis_evidence.json` y `README.md`.

**Resultados provisionales, sin exagerar:** intención 22/30 del modelo frente a
14/30 de reglas; flujo simulado completo 25/25 frente a 23/25. En los escenarios
de derivación se simula la confirmación y se exige guardar y leer un ticket
de prueba; ninguna persona real lo recibe. Cero divulgaciones indebidas
observadas en solo 25 escenarios; no implica seguridad demostrada a escala.
Las frases de esa evaluación ya se inspeccionaron durante el desarrollo. La
prueba adicional `synthetic_eval_cases_v11.json`, escrita por IA y etiquetada
antes de ejecutarse, encontró **35/40** intenciones y **14/18** flujos correctos
con el modelo, frente a **30/40** y **12/18** con reglas. Es el resultado
histórico previo a v12. Después corregimos el controlador y lo volvimos a
probar sobre **los mismos casos**: v12 obtuvo **15/18** flujos con modelo; v13
obtiene **18/18** tras corregir la prioridad de folios y el enrutamiento ES/PT.
Ambas cifras posteriores son regresiones de desarrollo sobre casos conocidos,
no evaluaciones independientes. El modelo ML sigue siendo el mismo. Se necesitan preguntas
nuevas etiquetadas por personas para medir calidad real.

**Lo que aún falta antes de operar en un banco:** identidad real, permisos de una
fuente autorizada y actual, prueba nueva con preguntas de otras personas en ES/PT,
medición del tiempo y costo con red y hosting, y auditoría y retención protegidas.
Esta versión es una demo con datos ficticios, no un servicio bancario conectado.

**Entrega según el kickoff:** el repositorio nuevo debe seguir el nombre pedido
`factored-hackathon-2026-[nombre-del-equipo]`; incluye el enlace público del
repositorio y el de la app nueva. La presentación y el video se revisarán tras
comprobar que este código ya funciona en el despliegue. No renombres directamente
el repositorio de la app actual: Streamlit puede perder acceso de administración.

El archivo `README.md` contiene la arquitectura, los comandos y los resultados.
