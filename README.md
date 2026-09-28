# Consulta de reclamaciones · Factored AI & Data Hackathon 2026

Prototipo bilingüe y **simulado** para consultar el estado de una reclamación y guardar
un ticket de derivación en una cola local temporal. Modelo local
TF-IDF de n-gramas de caracteres + regresión logística para enrutar la intención;
orquestador con aclaraciones, seguimiento, planes de siguientes acciones y traza de pasos ejecutados;
sesiones de prueba firmadas; regla de folio `R-###` o ticket `T-...` antes del modelo;
control determinista del titular aplicado en el servicio de expedientes;
respuesta construida solo después de volver a consultar la fuente. El ticket requiere
confirmación y una escritura seguida de lectura. La versión 12 añadió una bandeja de
analista ficticio con sesión distinta, confirmación de recepción y comprobación de
que ningún reintento mezcle hechos de versiones distintas. La versión 13 añade abstención
explícita en temas ajenos, un 403 estructurado para folios ajenos o ausentes y un paquete
de derivación que contiene hechos comprobados, preguntas pendientes e ID verificado,
sin transcripción íntegra. No hay clientes reales, claves
AWS, respuestas del banco en vivo ni servicios externos de IA.

## Demo pública y prueba guiada

[Abrir la demo anterior](https://factored-reclamaciones-ai-2026-cnvgspggr4zr78r9m2fteb.streamlit.app/).
Esta URL aún no ejecuta necesariamente la versión 14 del paquete; hay que subir el
código y comprobar el despliegue antes de presentar sus funciones como públicas.
La versión 14 organiza la experiencia en **Cliente** (chat, ejemplos, tarjeta
verificada y acciones) y **Agent Trace / Observability** (ruta, RBAC, entrada y
salida autorizadas y métricas medidas). El selector lateral cambia entre Alicia
y Bruno y reinicia la sesión y su traza; el idioma cambia dinámicamente entre ES
y PT. La respuesta ya verificada se presenta con streaming visual; el modelo
local no genera texto. Otras pestañas conservan la revisión de prueba, resultados
del reto y límites de diseño.

1. La app abre automáticamente una sesión ficticia de Alicia. Pulsa **«Mi folio»**
   o escribe `R-101` en el chat. Verás estado y fecha completos, fuente y copia de 2025.
   El panel «Siguiente paso» ofrece «Verificar fecha», «Preguntar por el motivo»
   y «Preparar derivación (demo)» según la respuesta autorizada. Las consultas de
   hechos vuelven al servicio para revisar registro y permisos. Como el motivo no existe
   en la fuente, esa pregunta prepara una derivación sin inventar un motivo.
   Pulsa **«Confirmar derivación»** para confirmar la escritura; aparecerá `T-...`
   solo tras guardarlo y leerlo de vuelta. «Agent Trace / Observability» muestra
   la traza y el paquete autorizado. El ticket **no se envía** a un agente real.
   En **«Mesa de revisión»**, entra con el PIN público `8642`. Verás el paquete
   ficticio y podrás **confirmar recepción de prueba**. Al volver a «Cliente»
   se muestra esa recepción solo si la lectura de la cola y del expediente sigue
   siendo válida. Un usuario puede desempeñar ambos papeles para la demostración.
   Prueba `R-102`; cambia a **Bruno (prueba)** en el selector lateral y consulta
   `R-101` para comprobar el 403. Bruno puede consultar su propio `R-201`.
2. Abre «Pruebas de fallas» en la barra lateral para provocar una caída de la fuente.
   Pulsa «Sin folio» y escribe `R-102` en el chat; también puedes escribir
   `R-101 y R-201`: la app te exigirá elegir un solo folio.
   Marca «Simular fallo al guardar», prepara una derivación y comprueba
   que no aparece un ID hasta desmarcarla y confirmar de nuevo.
   Cambia a «Português» para repetir las preguntas en portugués. En observabilidad,
   comprueba que una decisión por regex no tiene score de modelo y que una ruta
   inferida muestra su probabilidad local sin afirmar calibración.
3. Para reproducir el despliegue, usa los archivos de este repositorio y elige
   `streamlit_app.py` como archivo principal en Streamlit Community Cloud.
   No subas los ZIP de datos ni documentos con credenciales.

Los PIN son públicos para reproducir el demo. Este formulario representa un emisor
de sesiones de prueba, **no** autenticación bancaria. El token firmado vence a los
10 minutos; la consulta valida propiedad antes de retornar estado. El selector
emite una sesión firmada nueva con las credenciales ficticias públicas;
no demuestra verificación de identidad de clientes reales.

El ZIP de entrega incluye los archivos de ejecución (`requirements.txt`, app,
clasificador, servicio, ejemplos), los agregados (`analysis_evidence.json`),
dos gráficas en `figures/`, la evaluación, las pruebas y los scripts de auditoría. No incluye los ZIP con
registros originales del organizador. Para comprobar que se puede ejecutar desde
una extracción nueva, instala dependencias, ejecuta los comandos siguientes y
selecciona `streamlit_app.py` como archivo principal al desplegar.

## Ejecutar localmente (opcional)

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
python evaluate.py
python evaluate_regression_v13.py
python -m unittest test_security.py test_handoff_ticket.py test_reviewer.py test_workflow_v13.py test_streamlit_ui.py test_audit_data.py
python update_fixture.py
```

El archivo `evaluation_results.json` registra las métricas del enrutador.
La actualización v15 agrega `audit_data.py`, `analysis_evidence.json` y dos PNG a 16:9
para la presentación. Para rehacer la auditoría con los datos locales del organizador,
usa el directorio **extraído** de interacciones y los ZIP válidos de las otras dos tablas:

```bash
python audit_data.py --interactions /ruta/a/interacciones_2025_extraidas --complaints /ruta/a/quejas_2025.zip --transcripts /ruta/a/transcripciones_2025_01.zip --output analysis_evidence.json --charts-dir figures
```

También admite CSV o ZIP íntegros por tabla. El ZIP de interacciones disponible en
nuestro entorno está dañado; la extracción local de sus 365 CSV sí fue legible.
Esas fuentes **no se incluyen** en el repositorio público. `audit_data.py` solo exporta
agregados. Si proporcionas una tabla de clientes con `customer_id,country` mediante
`--customers`, genera desglose por país después de vincular los IDs; de otro modo deja
los resultados por país como `null` y no deduce país de acento o moneda. Las gráficas
se guardan como `figures/complaints_category_subcategory.png` y
`figures/service_outcomes_by_channel.png`. En los datos originales de enero, todas las frases `customer_text` incluyen
«saldo» mientras los rótulos de contacto varían. Por ello **no** usamos esas
transcripciones como entrenamiento o prueba del clasificador. Los ejemplos de
`intent_data.py` y los expedientes de `service.py` son **creados por el autor**;
hay ejemplos separados de entrenamiento y prueba, aunque un único autor creó ambos.
El conjunto de prueba se revisó durante iteraciones previas; se trata de una
**evaluación exploratoria**, no de una prueba ciega independiente.

Los estados de los expedientes justifican explorar este flujo: 15 630 de 22 356
reclamaciones están abiertas o en proceso (69,9 %). En otro archivo, 24 582
interacciones de categoría «Queja» tienen la marca de seguimiento. No se pueden unir
las reclamaciones a esas interacciones porque falta el ID de origen en las 22 356;
no afirmamos que todas las interacciones fueran consultas de estado ni atribuimos
ahorros reales a la demo. La gráfica de la app muestra los seis estados agregados.

En las muestras, 175 460 de 229 056 interacciones están marcadas como resueltas
en primer contacto (76,60 % según `was_resolved`); 5 324 reclamaciones con estado
`Resolved` o `Closed` tienen un tiempo válido y promedian 15,64 días. El 9,96 %
de las interacciones indica escalamiento a **supervisor** y el 5,14 % de los
expedientes tiene estado **Escalated** en esta copia. Ninguna marca confirma qué
porcentaje de reclamaciones **terminó** en soporte humano: ese KPI permanece `null`.
No se pueden unir los canales de ambas tablas para calcular un FCR de expedientes.

El ROI de `analysis_evidence.json` es `null` por defecto: faltan costos medidos,
éxitos de automatización y minutos ahorrados. Para obtener un escenario explícito,
añade a la orden los seis parámetros `--human-cost-usd`,
`--llm-cost-per-attempt-usd`, `--automatable-share`,
`--automation-success-rate`, `--human-handling-minutes` y
`--fixed-platform-cost-usd`. La base se restringe a las 39 228 interacciones
etiquetadas `Queja` y la fracción automatizable también es un supuesto.
El ahorro neto es costo humano base menos (intentos LLM + fallos atendidos
por humanos + costo fijo). El ahorro porcentual divide por el costo base;
el ROI divide ese ahorro por la inversión LLM y plataforma. Las horas liberadas
son resoluciones automatizadas supuestas × minutos humanos supuestos / 60.
**No son ahorros observados** y el escenario no atribuye a la app actual capacidad
LLM que todavía no se haya medido.

## Contratos, decisiones y límites

| Parte | Contrato y decisión |
| --- | --- |
| Preparación | `audit_data.py` lee CSV, ZIP o directorio extraído, comprueba IDs únicos y empareja transcripciones con llamadas. Rechaza IDs duplicados. Solo se publica conteo agregado. |
| Intención | `routing.py` extrae `R-###` o `T-` y 16 hexadecimales antes de la inferencia: una referencia explícita va a lectura de estado; varias piden elegir una. Sin referencia, solicitudes explícitas de disputa o agente siguen su flujo. Una pregunta informativa sobre dirección, comisiones de cajero o tarjetas queda fuera de alcance en ES/PT con respuesta fija; para lo demás, el clasificador local propone `status`, `new_dispute`, `human`, `other` o `unclear`. La precisión de clasificación cruda y el flujo completo son medidas distintas. |
| Orquestación | El controlador conserva el último folio verificado solo para la misma sesión firmada y pide datos faltantes. Una pregunta por fecha o motivo reutiliza el folio, pero **vuelve a consultar la fuente** y a comprobar permiso; el estado anterior no se reutiliza. Una derivación tras un folio confirmado vuelve a verificar propiedad, estado y fecha. El servicio decide qué acciones ofrecer según el resultado: fecha, motivo o atención humana; los botones vuelven a ejecutar esas rutas y permisos. Nunca inventa un motivo ausente. Es un agente de flujo acotado, sin generación libre. El ticket necesita confirmación explícita en la pantalla. |
| Identidad | Una sesión firmada expira. La identidad no se deriva de un número de cliente escrito en el chat. PIN público significa **solo simulación**. |
| Privacidad de la demo | Se rechazan entradas con secuencias de 12 a 19 dígitos, con espacios o guiones opcionales, antes de guardarlas en el historial. El ticket almacena una descripción fija de la intención, **no** el texto libre del visitante. El contexto interno conserva solo la ruta y el último folio autorizado, sin duplicar la frase libre. La interfaz oculta números largos rechazados y muestra el texto del usuario sin interpretarlo como Markdown. El filtro no detecta todas las formas de información personal: usar solo datos ficticios. |
| Herramienta | `tenancy.py` comprueba `owner == sub` del token en el acceso al registro; `service.py` devuelve el mismo `Reply.error = {status: 403, code: FORBIDDEN, message: ...}` para caso ajeno o inexistente, sin llamar al modelo. En Streamlit es un contrato de respuesta estructurado dentro de la app, no un código HTTP de una API. Acepta `R-101`, `R101`, `R 101` y `R–101`. Con dos folios distintos solicita elegir uno antes de consultar la fuente. Dos fallos de la fuente causan derivación segura. |
| Respuesta | Estado y fecha proceden únicamente del registro de prueba. Se rechazan fechas inválidas y posteriores a la copia. Siempre indica que es una copia de 2025 y no estado actual. Caso escalado prepara una derivación simulada. Cambios de tarjeta, domicilio o contraseña quedan fuera del flujo de reclamaciones. |
| Acciones | Sin creación de reclamaciones, transferencias, reversos ni acceso a cuentas reales. Las escrituras son el ticket ficticio confirmado por el cliente y el acuse de revisión confirmado con un rol de analista de prueba. Ambas se leen de nuevo antes de reportar éxito. La cola SQLite queda en el disco temporal de la instancia; un reinicio puede borrarla y los tickets caducan a las 24 horas. No hay bandeja de agentes reales. |
| Trazabilidad | La respuesta guarda fuente, tipo de resultado, cantidad de intentos, un plan de acciones y los pasos **realmente ejecutados**. La pantalla muestra una tarjeta del expediente solo cuando el servicio devuelve una lectura autorizada. El paquete tiene `ticket_id` (nulo hasta guardarse), `customer_id`, `verified_facts`, `open_questions`, `reason_for_escalation` y `sentiment` (señal léxica limitada o `unknown`). No almacena el texto libre del visitante. Al confirmar, se verifica de nuevo el permiso, se guarda una sola vez por solicitud y se vuelve a leer el ticket con su ID; un reintento con datos distintos se rechaza. La lectura posterior oculta tickets con hechos ya cambiados. Un folio ajeno, inexistente, con datos inválidos o inaccesible por falla no aporta estado ni fecha. Un cargo nuevo no hereda el estado de un folio anterior. No muestra ni almacena razonamiento interno del modelo. |
| Observabilidad de interfaz | `streamlit_app.py` compone idioma, ruta, RBAC, herramienta, entrada/salida mínima y paquete de derivación a partir de respuestas reales. Las referencias decididas por regex o política no tienen score de modelo; la ruta inferida muestra la probabilidad real del clasificador local sin atribuirle calibración. La detección de idioma usa pistas léxicas o el selector y su proporción no es una probabilidad calibrada. La animación transmite solo el texto ya verificado. En esta demo hay 0 tokens de LLM externo y USD 0 de API; la latencia con `perf_counter` rodea cada llamada local al servicio o a la cola, y excluye streaming visual, red y hosting. La traza no incorpora el token de sesión ni la transcripción. |
| Actualización | Los archivos del reto son copia estática de 2025. Una integración real requiere origen autorizado, marcas de actualización, validaciones y prueba de cambios incrementales antes de mostrar actualidad. |

`update_fixture.py` prueba, solo con datos inventados, aplicar un evento nuevo, repetirlo
sin cambios, ignorar uno viejo y rechazar un cambio de propietario del expediente.

## Evaluación

`evaluate.py` compara los mismos **25 escenarios** para ambos enrutadores. Para
los casos etiquetados como derivación simula la confirmación explícita y exige
guardar y leer el ticket de prueba antes de contar el resultado como correcto.
Reporta exactitud/F1 de intención, rutas correctas, automatizaciones correctas,
divulgaciones indebidas detectadas y latencia local p50/p95. Incluye sesiones vencidas, token alterado,
expediente ajeno, folio inexistente, caída de herramienta, prompt injection y ES/PT.
La exactitud de intención mide el clasificador sin reglas añadidas; los escenarios de
flujo miden el controlador completo, que da prioridad a folios explícitos,
mantiene contexto dentro de la sesión y aplica autorización en la herramienta.
La variante del clasificador se eligió comparando TF-IDF de caracteres 3–5/C=1
contra 2–5/C=2, con el mismo umbral de abstención, en tres repeticiones de
validación cruzada estratificada de cuatro particiones **solo de los 96 ejemplos de
entrenamiento**. El archivo de resultados incluye 288 predicciones de esos mismos 96
ejemplos: anterior 147 aciertos, 4 errores y 137 abstenciones; actual 207 aciertos,
10 errores y 71 abstenciones. Hay una compensación entre cobertura y errores.
Los casos son pocos y escritos a mano; no representan tráfico real ni miden mejora
operativa en producción. Si un enrutador da peores resultados, se informa tal cual.
La inferencia no llama API pagada; costo de API USD 0 y costo de hosting sin estimar.
Las latencias reportadas solo miden el flujo local dentro del proceso Python,
incluida la cola SQLite local cuando corresponde; no incluyen red, navegador,
tiempo humano de confirmación, arranque de la app ni concurrencia.
La pestaña «Datos y resultados» muestra p50/p95 de esa única ejecución de 25
escenarios por método; no es una medida de servicio alojado ni un ahorro en producción.

En esta medición local: entrenamiento 96 ejemplos, evaluación exploratoria de intención
con 30 ejemplos diferentes (15 ES y 15 PT). Acierto de intención: reglas 14/30,
modelo 22/30. De 25 escenarios integrales: reglas 23 correctos, modelo 25;
consultas de estado automatizadas
correctamente 4/5 y 5/5, respectivamente; tickets de prueba confirmados
en escenarios de derivación 6/8 y 8/8 (sin medir recepción humana);
divulgaciones o acciones indebidas observadas 0/25 para ambos. El tamaño y la
autoría de los ejemplos impiden extrapolar estas cifras a usuarios reales.
En el flujo completo del modelo: español 13/13 y portugués 12/12; perfil ficticio
Alicia 15/15 y Bruno 10/10. Son subgrupos pequeños y simulados, insuficientes para
afirmar equidad o un rendimiento estable.

**Errores observados:** de las ocho respuestas de intención incorrectas del modelo,
seis fueron abstenciones para pedir aclaración y dos clasificaron temas no cubiertos
como consultas de estado. En los 25 escenarios completos, el modelo acertó los 25;
ninguno expuso un estado ajeno en esta prueba pequeña. El rendimiento por idioma en
intención fue 11/15 para español y 11/15 para portugués. El autor había consultado
las 30 frases durante el desarrollo; las cifras no son una estimación independiente
de desempeño y deben medirse otra vez con consultas nuevas antes de cualquier uso real.

**Siguiente prueba recomendada:** pedir a dos o tres personas que redacten al menos
diez preguntas nuevas en español y portugués, sin datos bancarios reales. Guardar la
intención correcta esperada **antes** de probarlas, registrar también los fallos y
separar los resultados por idioma. No añadir esas preguntas al entrenamiento hasta
cerrar la medición. Si se cambia el modelo después, usar otro conjunto nuevo.

### Prueba sintética adicional, versión 11

`synthetic_eval_cases_v11.json` fija 40 preguntas nuevas (20 ES, 20 PT; cinco por
intención en cada idioma) y 18 escenarios de flujo antes de ejecutarlos. Codex
escribió las frases y sus etiquetas; **no** proceden de clientes ni de evaluadores
humanos independientes. La regresión `evaluate_regression_v12.py` exige que el conjunto conserve
SHA-256 `cf274e0fd14fcd33c1d9cce940727dd4a81635436e82f321984226c0c84b51ea`
y comprueba que las frases no se repitan exactamente en entrenamiento ni en la
evaluación anterior. Esto no elimina parecidos de significado. El resultado de
la **primera ejecución v11** quedó congelado antes de corregir el controlador;
el modelo de intención sigue igual. Los errores originales quedan en
`synthetic_eval_results_v11.json` y en la pestaña «Datos y resultados».

| Resultado sintético local | Reglas | Modelo actual |
| --- | ---: | ---: |
| Intenciones estrictamente correctas | 30/40 | 35/40 |
| Flujos completos correctos | 12/18 | 14/18 |
| Derivaciones exigidas con ticket guardado y leído | 2/4 | 4/4 |
| Divulgaciones o acciones indebidas detectadas en los casos de seguridad | 0 | 0 |

El modelo acertó 17/20 intenciones ES y 18/20 PT. En el flujo acertó 7/9 ES y
7/9 PT. **Cuatro fallos completos**: `WF-01` y `WF-05` pidieron aclaración donde
esperábamos una consulta de estado y una denegación, `WF-16` pidió aclaración para
un tema fuera de alcance y `WF-18` derivó una consulta que debía resolverse tras
aclarar el folio. Se cuentan como fallos aunque no hayan filtrado información.
Además, una consulta sobre tarifa de cajero se confundió con disputa y una
pregunta portuguesa sobre actualización de domicilio se confundió con estado;
son fallos de intención que deben revisarse con nuevos ejemplos humanos.
Los p50/p95 del flujo del modelo en esta corrida fueron 0,95/2,14 ms **solo
dentro del proceso local**; no representan tiempo del navegador ni costo de hosting.
La prueba anterior de 25 escenarios es exploratoria y permanece visible por
transparencia. Ninguna de las dos pruebas mide rendimiento en clientes reales.

### Regresión de desarrollo, versión 12

`evaluate_regression_v12.py` vuelve a ejecutar **los mismos casos** después de
corregir el controlador. Los resultados se escriben por separado en
`synthetic_eval_results_v12_regression.json`: **35/40** intenciones y **15/18**
flujos con modelo, frente a **30/40** y **12/18** con reglas. El fallo de flujo
`WF-16` pasó a quedar fuera de alcance; persisten `WF-01`, `WF-05` y `WF-18`.
Esto comprueba regresiones del código, pero **no** es una nueva medición ciega
ni demuestra una mejora con clientes. La bandeja del analista se comprueba con
`test_reviewer.py`, fuera de los 18 escenarios.

### Regresión de desarrollo, versión 13

`evaluate_regression_v13.py` conserva el conjunto y las etiquetas congeladas,
tras introducir `routing.py` y `tenancy.py`. En los **mismos 18 escenarios ya
analizados**, el flujo con modelo acierta **18/18** y la base de reglas **16/18**.
Los cuatro casos WF-01, WF-05, WF-16 y WF-18 se cubren además con invariantes
de unidad en `test_workflow_v13.py`: sin inferencia para folios o productos
generales, igualdad de errores 403, y lectura confirmada del ticket.
El clasificador puro sigue en **35/40** intenciones para el modelo y **30/40**
para las reglas: el cambio mejora el controlador, no la precisión del ML.
Los casos ya se conocían al modificarlo; **18/18 no es evaluación independiente**
ni garantiza seguridad o desempeño en producción.

## Camino a operación

Conectar un IdP real, obtener licencia y política del dato, permisos institucionales,
API de expedientes con marca de frescura, registro protegido de auditoría y monitoreo;
reunir y etiquetar consultas auténticas ES/PT con consentimiento; volver a medir con
un conjunto independiente y auditar grupos relevantes antes de dar servicio bancario.
La app pública admite usuarios concurrentes en infraestructura de demo; el almacén de
casos es ficticio en memoria y las sesiones se pierden al reiniciar el proceso.
La cola local de tickets puede perderse al reiniciar la instancia; no tiene
respaldo ni gestión por agentes reales. Los tickets caducan a las 24 horas y se depuran
al crear otros nuevos.

Las pruebas de `test_security.py` verifican también planes de acciones derivados
del estado autorizado, ausencia de tarjetas verificadas para folios ajenos,
la prioridad de lectura de estado con folio explícito,
la actualización de un estado antes de pedir un agente, la revocación de acceso,
la falla de fuente, la expiración de sesión y que no se adjunte un expediente
anterior a una disputa nueva. `test_handoff_ticket.py` cubre confirmación,
idempotencia, lectura después de escribir, perfiles, sesión vencida, revocación,
errores de la cola, idioma portugués, fechas inválidas, datos cambiantes y caducidad.
`test_reviewer.py` comprueba separación de roles, lectura del paquete, recepción
persistida y verificada, aislamiento del acuse por sesión y expiración. Estas pruebas complementan
los 25 escenarios de `evaluate.py`; no forman parte de sus métricas publicadas.

**Alcance de las métricas:** los 25 escenarios califican el flujo y, en los
ocho casos que exigen derivación, simulan la confirmación humana y exigen
escritura y lectura del ticket local. **No** miden recepción por una persona
real ni tiempo humano de confirmación. El tiempo medido es local e incluye
SQLite cuando se confirmó un ticket.

## Entrega del hackathon

El kickoff pide un repositorio público llamado `factored-hackathon-2026-[nombre-del-equipo]`,
enlace a la app desplegada, presentación de **4 a 6 diapositivas** y **video breve
obligatorio**. El repositorio de trabajo actual tiene un nombre diferente; conviene
preparar un repositorio con el nombre requerido y desplegarlo antes de entregar.
Streamlit Community Cloud vincula cada app con el nombre exacto del repositorio;
renombrar directamente el repositorio actual sin preparar el despliegue puede
hacer que se pierda la administración de la app publicada. Comprobar el nuevo
enlace y el recorrido completo antes de sustituir el antiguo.
Una demo funcional y pruebas honestas ayudan, pero no garantizan ganar.
