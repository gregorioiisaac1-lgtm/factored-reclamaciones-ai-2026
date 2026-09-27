# Tu siguiente paso, Isaac

Este ZIP ya trae una app y los resultados de la primera evaluación. No necesitas
instalar Python en Windows para presentarla.

1. Descomprime el ZIP y crea un repositorio nuevo en GitHub.
2. Sube **los archivos que están dentro de `factored_demo`**, nunca los ZIP originales,
   PDF con credenciales ni claves de AWS.
3. En [Streamlit Community Cloud](https://share.streamlit.io/) selecciona ese
   repositorio y pon `streamlit_app.py` como archivo principal.
4. En la app entra como Alicia con `1379` y pregunta `¿Cómo va R-101?`;
   luego intenta `¿Cómo va R-201?`. Prueba también Bruno `2468`, idioma portugués,
   sesión vencida y falla de consulta.

**Por qué elegimos este enfoque:** hay 22 356 expedientes en los datos de 2025,
incluidos 4 123 bajo «Cargo no reconocido». De 4 903 transcripciones de enero,
todas incluyen «saldo», hay solo 42 textos de cliente distintos y las mismas frases
se asignan a múltiples categorías. Entrenar el modelo con esas etiquetas daría
una evaluación engañosa. Usamos 96 consultas ficticias escritas para entrenar
el enrutador local y otras 30 para probarlo.

**Resultados provisionales, sin exagerar:** intención 15/30 del modelo frente a
14/30 de reglas; flujo completo 23/25 frente a 21/25. Cero divulgaciones indebidas
observadas en solo 25 escenarios; no implica seguridad demostrada a escala.

Para las diapositivas, sugiero cinco partes: (1) problema y cifras, (2) fallo de
calidad en las transcripciones, (3) flujo con sesión y autorización por expediente,
(4) demo ES/PT con derivación, (5) evaluación, límites y camino a producción.
El archivo `README.md` contiene la arquitectura, los comandos y los resultados.
