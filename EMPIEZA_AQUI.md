# Tu siguiente paso, Isaac

Esta actualización incluye la app v12, la bandeja de revisión simulada y la regresión de
desarrollo. No necesitas
instalar Python en Windows para probar la demo.

1. Descomprime `Factored_codigo_v12.zip`. Para cumplir el nombre pedido,
   crea otro repositorio **público** llamado
   `factored-hackathon-2026-isaac-gregorio`. Mantén el repositorio y la app
   actuales mientras preparas y compruebas la nueva entrega.
2. Sube los archivos **que están dentro del ZIP**, todos a la raíz del nuevo repositorio,
   conservando sus nombres. Es un paquete completo: incluye `requirements.txt`,
   `analysis_evidence.json`, código, pruebas y documentación. No subas ZIP de
   datos, PDF con credenciales ni claves de AWS.
3. En Streamlit Community Cloud, despliega **una app nueva** desde el repositorio
   nuevo, rama `main`, archivo `streamlit_app.py`. La
   [demo anterior](https://factored-reclamaciones-ai-2026-cnvgspggr4zr78r9m2fteb.streamlit.app/)
   queda como respaldo. Una vez lista la nueva, comprueba el recorrido:
   Pulsa «Empezar demo como Alicia». En «Mi expediente» ya estará escrito `R-101`:
   pulsa «Consultar estado». Verás estado y fecha completos, además de la fuente; en «Tu siguiente
   paso» pulsa «Preparar derivación (demo)» y después confirma con
   **«Crear ticket de prueba»**. Aparecerá un ID `T-...` únicamente si la app
   guardó el ticket y lo leyó de vuelta. El estado se consulta de nuevo y se
   verifica el permiso antes de guardarlo; no se envía a una persona real.
4. En **«Mesa de revisión»**, entra como analista de prueba con el PIN público
   `8642`. Busca el ID `T-...` y pulsa **«Confirmar recepción de prueba»**.
   Regresa a «Mi expediente»: el cliente ve que la recepción quedó confirmada.
   La bandeja solo guarda paquetes ficticios, no texto libre ni solicitudes a
   una persona real.
5. Para probar seguridad, como Alicia consulta `R-201`: la pantalla no mostrará
   el estado de Bruno. Para probar Bruno, cierra sesión y abre «Probar otro perfil
   con PIN público»: elige Bruno y escribe `2468`. Prueba también idioma portugués,
   «No tengo el folio», sesión vencida y falla de consulta. En «Simular errores»
   marca «Simular falla al guardar el ticket»: al intentar crearlo no debe
   aparecer ID. Desmarca la opción y vuelve a confirmar. Abre «Verificación y
   pasos ejecutados» para ver la traza y el paquete de derivación. El ticket
   queda temporalmente en la cola local de esta instancia; no llega a un agente.

**Por qué elegimos este enfoque:** hay 22 356 expedientes en los datos de 2025,
incluidos 4 123 bajo «Cargo no reconocido». De 4 903 transcripciones de enero,
todas incluyen «saldo», hay solo 42 textos de cliente distintos y las mismas frases
se asignan a múltiples categorías. Entrenar el modelo con esas etiquetas daría
una evaluación engañosa. Usamos 96 consultas ficticias escritas para entrenar
el enrutador local y otras 30 para probarlo.

**Resultados provisionales, sin exagerar:** intención 22/30 del modelo frente a
14/30 de reglas; flujo simulado completo 25/25 frente a 21/25. En los escenarios
de derivación se simula la confirmación y se exige guardar y leer un ticket
de prueba; ninguna persona real lo recibe. Cero divulgaciones indebidas
observadas en solo 25 escenarios; no implica seguridad demostrada a escala.
Las frases de esa evaluación ya se inspeccionaron durante el desarrollo. La
prueba adicional `synthetic_eval_cases_v11.json`, escrita por IA y etiquetada
antes de ejecutarse, encontró **35/40** intenciones y **14/18** flujos correctos
con el modelo, frente a **30/40** y **12/18** con reglas. Es el resultado
histórico previo a v12. Después corregimos el controlador y lo volvimos a
probar sobre **los mismos casos**: **15/18** flujos con modelo. La segunda cifra
es una regresión de desarrollo, no una evaluación independiente; quedan tres
fallos del flujo. El modelo ML sigue siendo el mismo. Se necesitan preguntas
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
