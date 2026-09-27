# Consulta de reclamaciones · Factored AI & Data Hackathon 2026

Prototipo bilingüe y **simulado** para consultar el estado de una reclamación. Modelo local
TF-IDF de n-gramas de caracteres + regresión logística para enrutar la intención;
sesiones de prueba firmadas; permiso por propietario aplicado en el servicio de expedientes;
respuesta construida solo después de consultar la fuente. No hay clientes reales, claves
AWS, respuestas del banco en vivo ni servicios externos de IA.

## Probar la aplicación sin instalar Python

1. Descomprime este paquete. Crea un repositorio en GitHub y sube **solo** los archivos
   de esta carpeta (no los ZIP de datos ni el diccionario con credenciales).
2. Abre [Streamlit Community Cloud](https://share.streamlit.io/), conéctalo a GitHub,
   selecciona el repositorio y el archivo principal `streamlit_app.py`, y despliega.
3. En la interfaz elige **Alicia (prueba)**, PIN `1379`, y escribe `¿Cómo va R-101?`.
   Prueba `R-102`, cambia al perfil **Bruno (prueba)** con PIN `2468` para `R-201`,
   y vuelve a Alicia para intentar consultar `R-201` sin permiso.
4. Marca «Simular falla de consulta», o vence la sesión, para mostrar la ruta segura.
   Cambia a «Português» para repetir las preguntas en portugués.

Los PIN son públicos para reproducir el demo. Este formulario representa un emisor
de sesiones de prueba, **no** autenticación bancaria. El token firmado vence a los
10 minutos; la consulta valida propiedad antes de retornar estado.

## Ejecutar localmente (opcional)

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
python evaluate.py
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
`intent_data.py` y los expedientes de `service.py` son **creados por el equipo**;
hay ejemplos separados de entrenamiento y prueba, aunque un único autor creó ambos.

## Contratos, decisiones y límites

| Parte | Contrato y decisión |
| --- | --- |
| Preparación | `audit_data.py` lee ZIP sin extraer, comprueba IDs únicos y empareja transcripciones con llamadas. Rechaza IDs duplicados. Solo se publica conteo agregado. |
| Intención | Clasificación local en `status`, `new_dispute`, `human`, `other`; baja confianza da `unclear`. Se compara con reglas de palabras clave sobre los mismos 30 textos de prueba ES/PT. |
| Identidad | Una sesión firmada expira. La identidad no se deriva de un número de cliente escrito en el chat. PIN público significa **solo simulación**. |
| Herramienta | `CaseRepository.lookup` verifica `owner == sub` en servidor. Caso ajeno o inexistente retorna lo mismo. Fallo: dos intentos, luego derivación sin inventar estado. |
| Respuesta | Estado y fecha proceden únicamente del registro de prueba. Siempre indica que es una copia de 2025 y no estado actual. Caso escalado se deriva a una persona. |
| Acciones | Sin creación de reclamaciones, transferencias, reversos ni acceso a cuentas reales. No hay autonomía de escritura. |
| Trazabilidad | La respuesta guarda fuente, tipo de resultado, cantidad de intentos y paquete para agente, sin razonamiento interno del modelo. |
| Actualización | Los archivos del reto son copia estática de 2025. Una integración real requiere origen autorizado, marcas de actualización, validaciones y prueba de cambios incrementales antes de mostrar actualidad. |

`update_fixture.py` prueba, solo con datos inventados, aplicar un evento nuevo, repetirlo
sin cambios, ignorar uno viejo y rechazar un cambio de propietario del expediente.

## Evaluación

`evaluate.py` compara los mismos **25 escenarios** para ambos enrutadores. Reporta
exactitud/F1 de intención, rutas correctas, automatizaciones correctas, divulgaciones
indebidas detectadas y latencia local p50/p95. Incluye sesiones vencidas, token alterado,
expediente ajeno, folio inexistente, caída de herramienta, prompt injection y ES/PT.
Los casos son pocos y escritos a mano; no representan tráfico real ni miden mejora
operativa en producción. Si un enrutador da peores resultados, se informa tal cual.
La inferencia no llama API pagada; costo de API USD 0 y costo de hosting sin estimar.

En esta medición local: entrenamiento 96 ejemplos, prueba de intención 30 ejemplos
(15 ES y 15 PT). Acierto de intención: reglas 14/30, modelo 15/30. De 25 escenarios
integrales: reglas 21 correctos, modelo 23; consultas de estado automatizadas
correctamente 4/5 y 5/5, respectivamente; derivaciones correctas 6/8 y 8/8;
divulgaciones o acciones indebidas observadas 0/25 para ambos. El tamaño y la
autoría de los ejemplos impiden extrapolar estas cifras a usuarios reales.

## Camino a operación

Conectar un IdP real, obtener licencia y política del dato, permisos institucionales,
API de expedientes con marca de frescura, registro protegido de auditoría y monitoreo;
reunir y etiquetar consultas auténticas ES/PT con consentimiento; volver a medir con
un conjunto independiente y auditar grupos relevantes antes de dar servicio bancario.
La app pública admite usuarios concurrentes en infraestructura de demo; el almacén de
casos es ficticio en memoria y las sesiones se pierden al reiniciar el proceso.
