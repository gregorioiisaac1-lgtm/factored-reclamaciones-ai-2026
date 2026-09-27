# Tu siguiente paso, Isaac

Esta actualización incluye la app, la evaluación y una guía al día. No necesitas
instalar Python en Windows para probar la demo.

1. Descomprime `Factored_actualizacion_v10.zip` y abre tu repositorio existente
   [factored-reclamaciones-ai-2026](https://github.com/gregorioiisaac1-lgtm/factored-reclamaciones-ai-2026).
2. Sube los archivos **que están dentro del ZIP**, todos a la raíz del repositorio,
   conservando sus nombres. Es un paquete completo: incluye `requirements.txt`,
   `analysis_evidence.json`, código, pruebas y documentación. Si GitHub avisa que
   alguno ya existe, súbelo con el mismo nombre para actualizarlo.
   **No borres el README.md anterior**: el nuevo lleva el mismo nombre y GitHub
   conserva las versiones en el historial. Si el sitio no permite cargar archivos
   que ya existen, no los renombres: abre cada archivo en GitHub, usa el lápiz de
   edición y pega el contenido de la versión nueva. No subas ZIP de datos, PDF
   con credenciales ni claves de AWS.
3. Espera a que se actualice la [demo pública](https://factored-reclamaciones-ai-2026-cnvgspggr4zr78r9m2fteb.streamlit.app/).
   Pulsa «Empezar demo como Alicia». En «Mi expediente» ya estará escrito `R-101`:
   pulsa «Consultar estado». Verás estado y fecha completos, además de la fuente; en «Tu siguiente
   paso» pulsa «Preparar derivación (demo)» y después confirma con
   **«Crear ticket de prueba»**. Aparecerá un ID `T-...` únicamente si la app
   guardó el ticket y lo leyó de vuelta. El estado se consulta de nuevo y se
   verifica el permiso antes de guardarlo; no se envía a una persona real.
4. Para probar seguridad, como Alicia consulta `R-201`: la pantalla no mostrará
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
Las frases de evaluación ya se inspeccionaron durante el desarrollo: hace falta
un conjunto nuevo e independiente para medir la calidad real.

**Lo que aún falta antes de operar en un banco:** identidad real, permisos de una
fuente autorizada y actual, prueba nueva con preguntas de otras personas en ES/PT,
medición del tiempo y costo con red y hosting, y auditoría y retención protegidas.
Esta versión es una demo con datos ficticios, no un servicio bancario conectado.

**Entrega pendiente según el kickoff:** tu repositorio actual no sigue el nombre
pedido `factored-hackathon-2026-[nombre-del-equipo]`. Antes de enviar, adapta
ese nombre y revisa que la app desplegada siga funcionando. También necesitarás
presentación de **4 a 6 diapositivas** y **video corto obligatorio**, junto con
el enlace público al repositorio y el enlace de la app.

Para las diapositivas, sugiero cinco partes: (1) problema y cifras, (2) fallo de
calidad en las transcripciones, (3) flujo con sesión y autorización por expediente,
(4) demo ES/PT con derivación, (5) evaluación, límites y camino a producción.
El archivo `README.md` contiene la arquitectura, los comandos y los resultados.
