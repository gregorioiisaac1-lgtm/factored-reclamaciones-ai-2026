# Consulta de reclamaciones · Factored AI & Data Hackathon 2026

Prototipo bilingüe y **simulado** para consultar el estado de una reclamación y guardar
un ticket de derivación en una cola local temporal. Modelo local
TF-IDF de n-gramas de caracteres + regresión logística para enrutar la intención;
orquestador con aclaraciones, seguimiento, planes de siguientes acciones y traza de pasos ejecutados;
sesiones de prueba firmadas; permiso por propietario aplicado en el servicio de expedientes;
respuesta construida solo después de volver a consultar la fuente. El ticket requiere
confirmación y una escritura seguida de lectura. No hay clientes reales, claves
AWS, respuestas del banco en vivo ni servicios externos de IA.

## Demo pública y prueba guiada

[Abrir la demo](https://factored-reclamaciones-ai-2026-cnvgspggr4zr78r9m2fteb.streamlit.app/).
La primera pestaña es un espacio de trabajo: un formulario de folio, una tarjeta del
expediente verificado y un panel de siguientes acciones. Las preguntas libres y el
historial siguen disponibles en secciones plegables. No hace falta usar el chat
para recorrer el flujo principal.
Las otras pestañas muestran los agregados del reto, un gráfico de estados, la comparación con el método
base y las decisiones de seguridad. La interfaz se puede usar en español y portugués.

1. Pulsa **«Empezar demo como Alicia»**. El campo de folio ya propone `R-101`:
   pulsa «Consultar estado». Verás estado y fecha completos, fuente y copia de 2025.
   El panel «Tu siguiente paso» ofrece «Verificar fecha», «Preguntar por el motivo»
   y «Preparar derivación (demo)» según la respuesta autorizada. Las consultas de
   hechos vuelven al servicio para revisar registro y permisos. Como el motivo no existe
   en la fuente, esa pregunta prepara una derivación sin inventar un motivo.
   Pulsa **«Crear ticket de prueba»** para confirmar la escritura; aparecerá `T-...`
   solo tras guardarlo y leerlo de vuelta. «Verificación y pasos ejecutados» muestra
   la traza y el paquete autorizado. El ticket **no se envía** a un agente real.
   Prueba `R-102`; para entrar como **Bruno (prueba)**,
   cierra la sesión y abre «Probar otro perfil con PIN público»; el PIN es `2468`
   y su folio sugerido es `R-201`. Vuelve a Alicia para consultar `R-201` sin permiso.
2. Abre «Simular errores» para provocar una caída de la fuente o vencer la sesión.
   Pulsa «No tengo el folio» y escribe `R-102` en el formulario; también puedes
   escribir `R-101 y R-201`: la app te exigirá elegir un solo folio.
   Marca «Simular falla al guardar el ticket», prepara una derivación y comprueba
   que no aparece un ID hasta desmarcarla y confirmar de nuevo.
   Cambia a «Português» para repetir las preguntas en portugués.
   Despliega «Ver historial de la consulta» si quieres ver los turnos anteriores.
3. Para reproducir el despliegue, usa los archivos de este repositorio y elige
   `streamlit_app.py` como archivo principal en Streamlit Community Cloud.
   No subas los ZIP de datos ni documentos con credenciales.

Los PIN son públicos para reproducir el demo. Este formulario representa un emisor
de sesiones de prueba, **no** autenticación bancaria. El token firmado vence a los
10 minutos; la consulta valida propiedad antes de retornar estado. El acceso rápido
también emite una sesión firmada para Alicia con las credenciales ficticias públicas;
no demuestra verificación de identidad de clientes reales.

El ZIP de entrega incluye los archivos de ejecución (`requirements.txt`, app,
clasificador, servicio, ejemplos), los agregados (`analysis_evidence.json`),
la evaluación, las pruebas y los scripts de auditoría. No incluye los ZIP con
registros originales del organizador. Para comprobar que se puede ejecutar desde
una extracción nueva, instala dependencias, ejecuta los comandos siguientes y
selecciona `streamlit_app.py` como archivo principal al desplegar.

## Ejecutar localmente (opcional)

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
python evaluate.py
python -m unittest test_security.py test_handoff_ticket.py
python update_fixture.py
```

El archivo `evaluation_results.json` registra las métricas de esta versión. Para rehacer
la auditoría con los ZIP locales del organizador:

```bash
python audit_data.py --interactions interacciones_2025.zip --complaints quejas_2025.zip --transcripts transcripciones_2025_01.zip > analysis_evidence.json
```

Esos tres ZIP **no se incluyen** en el repositorio público. `audit_data.py` solo exporta
agregados. En los datos originales de enero, todas las frases `customer_text` incluyen
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

## Contratos, decisiones y límites

| Parte | Contrato y decisión |
| --- | --- |
| Preparación | `audit_data.py` lee ZIP sin extraer, comprueba IDs únicos y empareja transcripciones con llamadas. Rechaza IDs duplicados. Solo se publica conteo agregado. |
| Intención | Clasificación local en `status`, `new_dispute`, `human`, `other`; baja confianza da `unclear`. Se compara con reglas de palabras clave sobre los mismos 30 textos de prueba ES/PT. |
| Orquestación | El modelo propone la ruta; solicitudes explícitas de humano o cargo nuevo tienen prioridad. El controlador conserva el último folio verificado solo para la misma sesión firmada y pide datos faltantes. Una pregunta por fecha o motivo reutiliza el folio, pero **vuelve a consultar la fuente** y a comprobar permiso; el estado anterior no se reutiliza. Una derivación tras un folio confirmado vuelve a verificar propiedad, estado y fecha. El servicio decide qué acciones ofrecer según el resultado: fecha, motivo o atención humana; los botones vuelven a ejecutar esas rutas y permisos. Nunca inventa un motivo ausente. Es un agente de flujo acotado, sin generación libre. El ticket necesita confirmación humana explícita en la pantalla. |
| Identidad | Una sesión firmada expira. La identidad no se deriva de un número de cliente escrito en el chat. PIN público significa **solo simulación**. |
| Privacidad de la demo | Se rechazan entradas con secuencias de 12 a 19 dígitos, con espacios o guiones opcionales, antes de guardarlas en el historial. El ticket almacena una descripción fija de la intención, **no** el texto libre del visitante. La interfaz oculta números largos rechazados. El filtro no detecta todas las formas de información personal: usar solo datos ficticios. |
| Herramienta | `CaseRepository.lookup` verifica `owner == sub` en servidor. Caso ajeno o inexistente retorna lo mismo. Acepta `R-101`, `R101`, `R 101` y `R–101`. Si la petición de estado menciona dos folios distintos, solicita elegir uno antes de llamar la herramienta; si se solicita un agente con dos folios distintos, prepara la derivación sin asociar ningún estado. Dos fallos reales de la fuente causan derivación, aunque no se haya activado el simulador de errores. |
| Respuesta | Estado y fecha proceden únicamente del registro de prueba. Siempre indica que es una copia de 2025 y no estado actual. Caso escalado se deriva a una persona. |
| Acciones | Sin creación de reclamaciones, transferencias, reversos ni acceso a cuentas reales. La única escritura es un ticket ficticio, solicitada con un botón de confirmación. La cola SQLite queda en el disco temporal de la instancia; un reinicio puede borrarla y los tickets dejan de poder leerse tras 24 horas. No hay bandeja de agentes reales. |
| Trazabilidad | La respuesta guarda fuente, tipo de resultado, cantidad de intentos, un plan de acciones y los pasos **realmente ejecutados**. La pantalla muestra una tarjeta del expediente solo cuando el servicio devuelve una lectura autorizada. Las derivaciones preparan un paquete con solicitud categorizada, hechos verificados y fecha si están autorizados, acciones intentadas y próximo paso. Al confirmar, se verifica de nuevo el permiso, se guarda una sola vez por solicitud y se vuelve a leer el ticket; los fallos no muestran un éxito falso. La app no envía el paquete a una persona. Un folio ajeno, inexistente, con datos inválidos o inaccesible por falla no aporta estado ni fecha. Un cargo nuevo no hereda el estado de un folio anterior. No muestra ni almacena razonamiento interno del modelo. |
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
flujo miden el controlador completo, que da prioridad a peticiones humanas explícitas,
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
modelo 22/30. De 25 escenarios integrales: reglas 21 correctos, modelo 25;
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

## Camino a operación

Conectar un IdP real, obtener licencia y política del dato, permisos institucionales,
API de expedientes con marca de frescura, registro protegido de auditoría y monitoreo;
reunir y etiquetar consultas auténticas ES/PT con consentimiento; volver a medir con
un conjunto independiente y auditar grupos relevantes antes de dar servicio bancario.
La app pública admite usuarios concurrentes en infraestructura de demo; el almacén de
casos es ficticio en memoria y las sesiones se pierden al reiniciar el proceso.
La cola local de tickets puede perderse al reiniciar la instancia; no tiene
respaldo ni gestión por agentes. Los tickets caducan a las 24 horas y se depuran
al crear otros nuevos.

Las pruebas de `test_security.py` verifican también planes de acciones derivados
del estado autorizado, ausencia de tarjetas verificadas para folios ajenos,
la derivación con folio explícito,
la actualización de un estado antes de pedir un agente, la revocación de acceso,
la falla de fuente, la expiración de sesión y que no se adjunte un expediente
anterior a una disputa nueva. `test_handoff_ticket.py` cubre confirmación,
idempotencia, lectura después de escribir, perfiles, sesión vencida, revocación,
errores de la cola, idioma portugués y caducidad. Estas pruebas complementan
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
adaptarlo antes de entregar y volver a comprobar el despliegue después del cambio.
Una demo funcional y pruebas honestas ayudan, pero no garantizan ganar.
