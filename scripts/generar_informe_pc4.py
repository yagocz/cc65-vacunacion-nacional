"""
Genera el informe de la PC4 en formato Word.

El enunciado indica que el informe de la PC4 debe contener el entregable
anterior con sus correcciones, de modo que este documento incluye las
secciones de la PC3 y añade las que corresponden a esta entrega:
distribución, API, bases de datos y evidencias.

Uso:
    python scripts/generar_informe_pc4.py
"""
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
CAPS = DOCS / "capturas"
import os as _os
SALIDA = Path(_os.environ.get("INFORME_SALIDA",
    str(RAIZ / "1ACC0065_PC4_202620_Informe_U202412543.docx")))

NEGRO = RGBColor(0, 0, 0)

hist = json.loads((DOCS / "historial_entrenamiento.json").read_text(encoding="utf-8"))
bench = json.loads((DOCS / "benchmark_speedup.json").read_text(encoding="utf-8"))
M = hist["metricas"]

# Latencias medidas sobre el stack contenerizado.
LAT = {"solicitudes": 200, "media": 3.48, "min": 2.81,
       "p50": 3.29, "p95": 4.44, "p99": 5.39, "max": 12.91}


def sombrear(celda, color="D9D9D9"):
    tc = celda._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), color)
    tc.append(sh)


def h(doc, texto, nivel=1):
    p = doc.add_heading(texto, level=nivel)
    for r in p.runs:
        r.font.color.rgb = NEGRO
        r.font.name = "Times New Roman"
    return p


def parr(doc, texto, cursiva=False, size=12):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(texto)
    r.font.size = Pt(size)
    r.italic = cursiva
    return p


def tabla(doc, cabeceras, filas, anchos=None, size=9.5):
    t = doc.add_table(rows=1, cols=len(cabeceras))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(cabeceras):
        cel = t.rows[0].cells[i]
        cel.text = ""
        r = cel.paragraphs[0].add_run(c)
        r.bold = True
        r.font.size = Pt(size)
        sombrear(cel)
    for fila in filas:
        cs = t.add_row().cells
        for i, v in enumerate(fila):
            cs[i].text = ""
            r = cs[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(size)
    if anchos:
        for fila in t.rows:
            for i, w in enumerate(anchos):
                fila.cells[i].width = Inches(w)
    doc.add_paragraph()
    return t


def figura(doc, archivo, titulo, ancho=6.2):
    ruta = CAPS / archivo
    if not ruta.exists():
        return
    doc.add_picture(str(ruta), width=Inches(ancho))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(titulo)
    r.italic = True
    r.font.size = Pt(9)


def main():
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Inches(1.0)
        s.top_margin = s.bottom_margin = Inches(1.0)

    est = doc.styles["Normal"]
    est.font.name = "Times New Roman"
    est.font.size = Pt(12)
    est.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    for n in (1, 2, 3):
        hs = doc.styles[f"Heading {n}"]
        hs.font.name = "Times New Roman"
        hs.font.color.rgb = NEGRO
        hs.font.bold = True
        hs.font.size = Pt(15 - n)

    # ---------------- CARÁTULA ----------------
    def cen(texto, size=14, bold=False, space=0):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space)
        r = p.add_run(texto)
        r.font.name = "Times New Roman"
        r.font.size = Pt(size)
        r.bold = bold
        r.font.color.rgb = NEGRO

    doc.add_paragraph()
    logo = DOCS / "logo_upc.png"
    if logo.exists():
        doc.add_picture(str(logo), width=Inches(1.17))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()
    cen("INFORME DE EVALUACIÓN DE DESEMPEÑO", 14, True, 12)
    doc.add_paragraph()
    cen("CC65 Programación Concurrente y Distribuida", 14, False, 0)
    cen("Carrera de Ciencias de la Computación", 14, False, 12)
    doc.add_paragraph()
    cen("Sección: ……", 14, False, 12)
    doc.add_paragraph()
    cen("Docente: Ms. Carlos Jara García", 14, False, 12)
    doc.add_paragraph()
    doc.add_paragraph()
    cen("Alumnos:", 14, False, 6)
    cen("U202215375 — Ricardo Rafael Rivas Carrillo", 12, False, 0)
    cen("U202412543 — Ernesto Yago Caldas Zapata", 12, False, 0)
    cen("U202220230 — Andre Angel Chipana Rios", 12, False, 12)
    doc.add_paragraph()
    cen("Entregable 2 — PC4", 14, True, 0)
    cen("Caso 7: Clasificación y Seguimiento de la Vacunación Nacional", 12, False, 0)
    for _ in range(3):
        doc.add_paragraph()
    cen("2026-20", 14, False, 0)
    cen("Lima, Perú", 14, False, 0)
    doc.add_page_break()

    # ---------------- ÍNDICE ----------------
    h(doc, "ÍNDICE", 1)
    for it in [
        "1. Resumen", "2. Descripción del problema y motivación", "3. Objetivos",
        "4. Objetivo del estudiante (Student Outcome 4)",
        "   4.1 Ética profesional", "   4.2 Responsabilidad profesional",
        "   4.3 Juicios sobre el impacto de la solución",
        "5. Desarrollo — Entregable 1 (PC3) con correcciones",
        "   5.1 Dataset seleccionado", "   5.2 Carga y limpieza concurrente",
        "   5.3 Etiquetado de la variable objetivo",
        "   5.4 Modelo ML distribuido y paralelización",
        "6. Distribución: clúster de nodos ML",
        "   6.1 Topología de red y justificación",
        "   6.2 Funcionamiento en lenguaje Go",
        "   6.3 Protocolo de comunicación TCP",
        "7. Desarrollo de la API",
        "   7.1 Endpoints y documentación Swagger",
        "   7.2 Autenticación con JWT",
        "   7.3 Funcionamiento en lenguaje Go",
        "   7.4 Evaluación de latencia",
        "   7.5 Canal WebSocket en tiempo real",
        "8. Implementación de bases de datos",
        "   8.1 Diseño de entidades", "   8.2 MongoDB: persistencia",
        "   8.3 Redis: caché de respuestas precalculadas",
        "9. Despliegue con Docker Compose",
        "10. Evidencias de la implementación y pruebas",
        "11. Trabajo en GitHub y tablero Kanban",
        "12. Conclusiones", "13. Recomendaciones", "14. Anexos", "15. Bibliografía",
    ]:
        p = doc.add_paragraph(it)
        p.paragraph_format.space_after = Pt(2)
    doc.add_page_break()

    # ---------------- 1. RESUMEN ----------------
    h(doc, "1. RESUMEN", 1)
    parr(doc,
        "Este informe documenta el segundo entregable (PC4) del Trabajo Final del curso CC65. "
        "Conforme indica el enunciado, incorpora los puntos del entregable anterior con sus "
        "correcciones y añade los componentes desarrollados en esta etapa: la distribución del "
        "cómputo en un clúster de nodos, la API coordinadora REST y WebSocket, la implementación "
        "de los dos niveles de almacenamiento y el despliegue contenerizado del sistema completo.")
    parr(doc,
        "El sistema procesa el Registro Nacional de Vacunación contra la COVID-19 del Ministerio "
        "de Salud, compuesto por 93,675,827 registros nominales (9.91 GB), y entrena de forma "
        "distribuida un modelo de Regresión Logística que predice la deserción en la aplicación "
        "de segundas y terceras dosis. La solución está escrita íntegramente en Go sobre la "
        "biblioteca estándar y se despliega mediante Docker Compose.")
    parr(doc,
        "El requisito de latencia que establece el enunciado —responder en menos de 100 "
        f"milisegundos— se cumple con holgura: sobre {LAT['solicitudes']} solicitudes consecutivas "
        f"al servicio contenerizado, la latencia media fue de {LAT['media']} ms y el percentil 99 "
        f"de {LAT['p99']} ms, aproximadamente dieciocho veces por debajo del umbral exigido.")
    doc.add_page_break()

    # ---------------- 2. PROBLEMA ----------------
    h(doc, "2. DESCRIPCIÓN DEL PROBLEMA Y MOTIVACIÓN", 1)
    parr(doc,
        "Entre 2021 y 2025 el Estado peruano aplicó más de 93 millones de dosis contra la "
        "COVID-19. La cobertura, sin embargo, no se distribuye de manera uniforme a lo largo del "
        "esquema: una proporción considerable de la población recibió la primera o la segunda "
        "dosis y nunca regresó por el refuerzo. Ese abandono, conocido como deserción vacunal, "
        "reduce la protección efectiva de la población y desaprovecha el esfuerzo logístico ya "
        "invertido en captar a esas personas.")
    parr(doc,
        "El análisis de los datos confirma la magnitud del fenómeno. De las 30,968,883 personas "
        "registradas en el padrón nacional, 8,339,819 —el 27.06 %— no alcanzaron la tercera dosis "
        "dentro de la ventana de observación pese a haber iniciado su esquema.")
    h(doc, "Pregunta que atiende el impacto social", 2)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Inches(0.4)
    r = p.add_run("¿Qué perfiles de población tienen mayor probabilidad de abandonar el esquema "
                  "de vacunación antes de completar la tercera dosis, y en qué departamentos se "
                  "concentran, de modo que el Ministerio de Salud pueda focalizar las campañas de "
                  "seguimiento donde el abandono es más probable?")
    r.bold = True
    r.font.size = Pt(12)
    doc.add_paragraph()
    parr(doc,
        "En esta entrega la respuesta deja de ser un resultado estático en un informe y se "
        "convierte en un servicio consultable: cualquier sistema del sector salud puede enviar un "
        "perfil demográfico a la API y recibir, en pocos milisegundos, la probabilidad de "
        "deserción junto con una recomendación operativa.")
    doc.add_page_break()

    # ---------------- 3. OBJETIVOS ----------------
    h(doc, "3. OBJETIVOS", 1)
    h(doc, "Objetivo general", 2)
    parr(doc,
        "Construir una aplicación concurrente y distribuida de alto rendimiento, desarrollada en "
        "Go y contenerizada con Docker, que procese más de un millón de registros de datos "
        "abiertos del Estado peruano, entrene de forma distribuida un modelo de aprendizaje "
        "automático y exponga sus predicciones mediante una API consumible por una interfaz web.")
    h(doc, "Objetivos específicos de la PC4", 2)
    for o in [
        "Distribuir el cómputo del entrenamiento en un clúster de nodos comunicados por TCP, "
        "justificando la topología de red adoptada.",
        "Desarrollar una API REST documentada con Swagger que responda en menos de 100 "
        "milisegundos y actúe como coordinadora del clúster.",
        "Implementar los dos niveles de almacenamiento que exige la arquitectura: MongoDB para "
        "la persistencia y Redis como caché de respuestas precalculadas.",
        "Gestionar la autenticación mediante tokens JWT y exponer un canal WebSocket que sirva "
        "datos en tiempo real al frontend.",
        "Contenerizar la solución completa y orquestarla con Docker Compose.",
        "Documentar las evidencias de funcionamiento con datos de prueba y capturas de pantalla.",
    ]:
        p = doc.add_paragraph(o, style="List Number")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    doc.add_page_break()

    # ---------------- 4. STUDENT OUTCOME ----------------
    h(doc, "4. OBJETIVO DEL ESTUDIANTE (STUDENT OUTCOME)", 1)
    parr(doc,
        "ABET – EAC – Student Outcome 4: La capacidad de reconocer responsabilidades éticas y "
        "profesionales en situaciones de ingeniería y hacer juicios informados, que deben "
        "considerar el impacto de las soluciones de ingeniería en contextos globales, económicos, "
        "ambientales y sociales.", cursiva=True)

    h(doc, "4.1 Demuestra ética profesional en el ejercicio de la ingeniería de software", 2)
    parr(doc,
        "El sistema trabaja con datos de salud de alcance nacional, lo que impone obligaciones "
        "que el equipo asumió de forma explícita en el diseño. El conjunto publicado por el MINSA "
        "es seudonimizado: cada persona aparece identificada por un UUID numérico. El sistema "
        "conserva esa condición en todo el flujo, y el identificador se emplea únicamente para "
        "agrupar las dosis de un mismo individuo mediante una función hash.")
    parr(doc,
        "En esta entrega la consideración ética se extendió a la capa de servicio. La API no "
        "expone ningún endpoint que permita consultar a una persona concreta: recibe un perfil "
        "demográfico —edad, sexo, departamento, fabricante, intervalos entre dosis— y devuelve "
        "una probabilidad asociada a ese perfil, no a un individuo identificable. Esta decisión "
        "limita deliberadamente la funcionalidad del servicio para impedir que se utilice como "
        "mecanismo de consulta individual sobre el historial de vacunación de una persona.")
    parr(doc,
        "Los endpoints que devuelven predicciones o métricas exigen un token JWT válido, y cada "
        "consulta queda registrada en MongoDB junto con el usuario que la realizó, de modo que "
        "existe trazabilidad sobre quién consulta el modelo y con qué frecuencia. Las "
        "credenciales de prueba se documentan explícitamente como tales en la especificación "
        "Swagger, para que no se confundan con credenciales de un entorno real.")

    h(doc, "4.2 Demuestra responsabilidad profesional para el logro de los objetivos", 2)
    parr(doc,
        "El trabajo se organizó en ramas de funcionalidad independientes, integradas a la rama "
        "principal mediante confirmaciones de fusión que preservan la estructura del historial. "
        "El seguimiento se gestiona en un tablero Kanban público de GitHub Projects con doce "
        "tareas, de las cuales diez se encuentran completadas al cierre de esta entrega.")
    parr(doc,
        "Durante el desarrollo surgieron tres obstáculos que ilustran la diferencia entre dar un "
        "componente por terminado y verificar que funciona. El primero: la compilación de las "
        "imágenes Docker falló porque la imagen base declaraba una versión de Go anterior a la "
        "que exige el módulo del proyecto; el error no era visible en la salida resumida y hubo "
        "que reconstruir con trazas completas para localizarlo. El segundo: los puertos 6379 y "
        "8080 ya estaban ocupados por otros servicios del equipo de desarrollo, lo que obligó a "
        "reasignar los puertos publicados en lugar de detener procesos ajenos al proyecto. El "
        "tercero, y el más relevante desde el punto de vista metodológico, se describe a "
        "continuación.")
    parr(doc,
        "La prueba destinada a demostrar el funcionamiento de la caché arrojaba que ambas "
        "llamadas provenían de Redis, lo que parecía confirmar que el sistema operaba "
        "correctamente. Una inspección más atenta reveló que el perfil consultado coincidía con "
        "el de una prueba anterior del mismo script, de modo que la primera llamada ya encontraba "
        "la entrada en caché. La prueba no demostraba nada: pasaba por una razón equivocada. Se "
        "corrigió para emplear un perfil generado aleatoriamente en cada ejecución, y solo "
        "entonces la evidencia mostró la secuencia correcta de fallo seguido de acierto.")

    h(doc, "4.3 Emite juicios considerando el impacto de las soluciones en el contexto global, "
            "social, ambiental y económico", 2)
    parr(doc,
        "Impacto social. El sistema convierte un modelo estadístico en una herramienta operativa. "
        "Una brigada de salud puede consultar la API y obtener, en milisegundos, la probabilidad "
        "de deserción de un perfil junto con una recomendación concreta: contacto telefónico "
        "prioritario y visita domiciliaria para riesgo alto, recordatorio por mensaje para riesgo "
        "medio, seguimiento regular para riesgo bajo. Las predicciones confirman que el grupo de "
        "mayor riesgo es la población pediátrica: un perfil de diez años en Cusco arroja una "
        "probabilidad de deserción de 0.8794, frente a 0.3755 para uno de setenta años.")
    parr(doc,
        "Impacto económico. La arquitectura se diseñó para operar sobre infraestructura modesta. "
        "El servicio completo —API, base de datos y caché— se ejecuta en tres contenedores sobre "
        "un equipo de escritorio, y atiende solicitudes con una latencia media de "
        f"{LAT['media']} milisegundos. Una institución pública puede desplegarlo sin adquirir "
        "infraestructura especializada, lo que reduce la barrera de adopción.")
    parr(doc,
        "Impacto ambiental. La caché en Redis evita recalcular predicciones para perfiles "
        "repetidos, y el modelo en memoria resuelve cada consulta con un producto escalar de "
        "quince términos en lugar de recorrer el conjunto de datos. Para un servicio con consultas "
        "recurrentes, esa diferencia se traduce en un consumo energético proporcionalmente menor.")
    parr(doc,
        "Contexto global. Ni la arquitectura ni el protocolo dependen del dominio específico de "
        "la vacunación contra la COVID-19. El mismo esquema es aplicable al seguimiento de "
        "cualquier programa de inmunización con dosis múltiples, incluidos los calendarios "
        "regulares de vacunación infantil, y resulta transferible a otros sistemas de salud de la "
        "región que enfrentan el mismo problema de abandono.")
    doc.add_page_break()

    # ---------------- 5. PC3 RESUMIDA ----------------
    h(doc, "5. DESARROLLO — ENTREGABLE 1 (PC3) CON CORRECCIONES", 1)
    parr(doc,
        "El enunciado establece que el informe de la PC4 debe contener el entregable anterior con "
        "sus correcciones. Esta sección resume los componentes desarrollados en la PC3, cuyas "
        "cifras se mantienen vigentes porque provienen de la misma ejecución sobre el conjunto de "
        "datos completo.")

    h(doc, "5.1 Dataset seleccionado", 2)
    tabla(doc, ["Campo", "Valor"], [
        ["Nombre", "Vacunación contra COVID-19"],
        ["Entidad", "Ministerio de Salud del Perú (MINSA)"],
        ["Registros", "93,675,827"],
        ["Tamaño", "9.91 GB"],
        ["Fecha de corte", "30 de noviembre de 2025"],
        ["Licencia", "Open Data Commons Attribution License"],
    ], [2.0, 4.2])
    parr(doc,
        "La ficha del conjunto en la Plataforma Nacional de Datos Abiertos redirige al formulario "
        "de inicio de sesión; el archivo se sirve desde el repositorio institucional del MINSA. El "
        "script scripts/descargar.sh automatiza su obtención.")

    h(doc, "5.2 Carga y limpieza concurrente", 2)
    tabla(doc, ["Métrica", "Valor"], [
        ["Registros procesados", "93,675,827"],
        ["Filas malformadas", "0"],
        ["Tiempo", "7.80 s"],
        ["Throughput", "1,301 MB/s"],
    ], [3.0, 3.2])
    parr(doc,
        "El analizador sintáctico respeta las comillas dobles, lo que permite conservar 17,105 "
        "registros de pacientes con comorbilidades cardíacas que un analizador ingenuo descartaría "
        "por contener un punto y coma dentro del campo GRUPO_RIESGO.")

    h(doc, "5.3 Etiquetado de la variable objetivo", 2)
    tabla(doc, ["Etiqueta", "Personas", "Proporción"], [
        ["y = 1 (desertó: menos de 3 dosis)", "8,339,819", "27.06 %"],
        ["y = 0 (completó: 3 o más dosis)", "22,476,530", "72.94 %"],
        ["Excluidas por censura a la derecha", "152,534", "0.49 %"],
    ], [3.1, 1.6, 1.5])

    h(doc, "5.4 Modelo ML distribuido y paralelización", 2)
    tabla(doc, ["Métrica", "Valor"], [
        ["Algoritmo", "Regresión Logística Distribuida"],
        ["Muestras de entrenamiento", "30,816,349"],
        ["Pérdida", f"0.693147 → {hist['historial'][-1]['perdida']:.6f}"],
        ["Exactitud", f"{M['exactitud']:.4f}"],
        ["Precisión", f"{M['precision']:.4f}"],
        ["Exhaustividad", f"{M['exhaustividad']:.4f}"],
        ["F1", f"{M['f1']:.4f}"],
        ["Speedup máximo", f"{max(r['speedup'] for r in bench['resultados']):.2f}× (12 workers)"],
    ], [2.8, 3.4])
    doc.add_page_break()

    # ---------------- 6. DISTRIBUCIÓN ----------------
    h(doc, "6. DISTRIBUCIÓN: CLÚSTER DE NODOS ML", 1)

    h(doc, "6.1 Topología de red y justificación", 2)
    parr(doc,
        "El clúster adopta una topología en estrella: un coordinador central y N nodos de cómputo "
        "que se comunican exclusivamente con él, sin enlaces entre sí. Esta elección corresponde "
        "al patrón Parameter Server y responde a la naturaleza del algoritmo.")
    parr(doc,
        "La justificación es la siguiente. En el descenso de gradiente distribuido, cada nodo "
        "calcula el gradiente sobre su fragmento del conjunto de datos y el resultado global es la "
        "media ponderada de esos gradientes parciales. Los nodos no necesitan conocer el trabajo "
        "de sus pares: solo el coordinador requiere la totalidad de los gradientes para actualizar "
        "los pesos. Una topología de malla, en la que todos los nodos se comunicaran entre sí, "
        "elevaría el número de enlaces de N a N(N−1)/2 sin aportar información adicional.")
    tabla(doc, ["Topología", "Enlaces con N=4", "Idoneidad para este algoritmo"], [
        ["Estrella (adoptada)", "4", "Cada nodo solo necesita hablar con el coordinador"],
        ["Malla completa", "6", "Enlaces redundantes: los nodos no usan datos de sus pares"],
        ["Anillo (AllReduce)", "4", "Viable, pero añade latencia de propagación por salto"],
    ], [1.6, 1.3, 3.3])
    parr(doc,
        "El contrapeso de la topología en estrella es que el coordinador constituye un punto único "
        "de fallo y un posible cuello de botella. En este sistema el riesgo es acotado: el "
        "coordinador solo agrega quince valores por nodo y por ronda, de modo que su carga es "
        "independiente del tamaño del conjunto de datos. La medición lo confirma: con cuatro nodos "
        "procesando 30.8 millones de muestras, cada ronda toma 250.5 milisegundos, de los cuales "
        "la agregación representa una fracción despreciable.")

    h(doc, "6.2 Funcionamiento en lenguaje Go", 2)
    parr(doc,
        "El sistema combina dos niveles de paralelismo que operan de forma simultánea. El nivel "
        "distribuido reparte el conjunto entre procesos independientes comunicados por TCP; el "
        "nivel concurrente, dentro de cada proceso, divide el trabajo entre goroutines que "
        "comparten el espacio de memoria.")
    tabla(doc, ["Componente", "Rol", "Mecanismo de Go"], [
        ["coordinador", "Reparte shards, difunde pesos, agrega gradientes",
         "net.Listen, goroutines por nodo, sync.WaitGroup"],
        ["nodo", "Calcula el gradiente sobre su shard",
         "net.Dial, goroutines internas, sync.Mutex"],
        ["protocolo", "Marco binario de mensajes",
         "encoding/binary sobre net.Conn"],
    ], [1.4, 2.5, 2.3])
    parr(doc,
        "Dentro de cada nodo, el cálculo del gradiente se reparte entre K goroutines que acumulan "
        "en memoria privada y vuelcan su resultado sobre la estructura compartida bajo una única "
        "adquisición de sync.Mutex. El número de bloqueos por ronda es igual al número de "
        "goroutines y no al número de muestras, que es la condición que permite que el paralelismo "
        "produzca ganancia en lugar de destruirla por contención.")

    h(doc, "6.3 Protocolo de comunicación TCP", 2)
    parr(doc,
        "La comunicación entre el coordinador y los nodos emplea un marco binario propio, definido "
        "en el paquete protocolo: una cabecera de cinco bytes —un byte de tipo de mensaje y cuatro "
        "de longitud del cuerpo— seguida del contenido serializado.")
    tabla(doc, ["Mensaje", "Dirección", "Contenido"], [
        ["HOLA", "nodo → coordinador", "Identificador del nodo"],
        ["CARGAR", "coordinador → nodo", "Ruta del dataset y rango del shard"],
        ["LISTO", "nodo → coordinador", "Número de muestras cargadas"],
        ["PESOS", "coordinador → nodo", "Vector de pesos de la iteración"],
        ["GRADIENTE", "nodo → coordinador", "Gradiente local, pérdida y nº de muestras"],
        ["EVALUAR", "coordinador → nodo", "Pesos finales para calcular métricas"],
        ["METRICAS", "nodo → coordinador", "Matriz de confusión local"],
        ["FIN", "coordinador → nodo", "Orden de terminación"],
    ], [1.3, 1.9, 3.0])
    parr(doc,
        "El ciclo de cada ronda es: difusión de pesos en paralelo, barrera de espera de los N "
        "gradientes, agregación ponderada y actualización. La barrera constituye el único punto de "
        "sincronización del sistema distribuido.")
    figura(doc, "03_entrenamiento_distribuido.png",
           "Figura 1. Entrenamiento distribuido sobre el clúster: convergencia y evaluación global.")
    doc.add_page_break()

    # ---------------- 7. API ----------------
    h(doc, "7. DESARROLLO DE LA API", 1)
    parr(doc,
        "La API cumple la doble función que describe el enunciado: expone el modelo entrenado como "
        "servicio web y actúa como coordinadora del clúster. Está escrita en Go sobre la "
        "biblioteca estándar, sin frameworks externos.")

    h(doc, "7.1 Endpoints y documentación Swagger", 2)
    tabla(doc, ["Método", "Ruta", "Descripción", "JWT"], [
        ["GET", "/api/salud", "Estado del servicio y sus dependencias", "No"],
        ["POST", "/api/login", "Autenticación y emisión de token", "No"],
        ["POST", "/api/predecir", "Predicción individual", "Sí"],
        ["POST", "/api/predecir/lote", "Predicción de hasta 10,000 perfiles", "Sí"],
        ["GET", "/api/metricas", "Métricas de latencia, caché y modelo", "Sí"],
        ["GET", "/ws", "Canal WebSocket en tiempo real", "No"],
        ["GET", "/swagger", "Documentación interactiva", "No"],
    ], [0.8, 1.7, 3.0, 0.6])
    parr(doc,
        "La especificación OpenAPI 3.0 se sirve en /swagger.json y se renderiza con Swagger UI en "
        "/swagger. Documenta siete esquemas de datos, los ejemplos de solicitud para cada endpoint "
        "y el esquema de seguridad BearerAuth.")
    figura(doc, "11_swagger.png",
           "Figura 2. Documentación OpenAPI 3.0 servida por la propia API.")
    doc.add_paragraph()

    h(doc, "7.2 Autenticación con JWT", 2)
    parr(doc,
        "La autenticación emplea tokens JWT firmados con HMAC-SHA256, implementados sobre los "
        "paquetes crypto/hmac y crypto/sha256 de la biblioteca estándar. El token incluye el "
        "usuario, su rol y la marca de expiración, y tiene una validez de ocho horas. Los "
        "endpoints protegidos verifican la firma y la vigencia antes de atender la solicitud; una "
        "petición sin token o con token inválido recibe un código 401.")

    h(doc, "7.3 Funcionamiento en lenguaje Go", 2)
    parr(doc,
        "El servicio mantiene los pesos del modelo en memoria y resuelve cada predicción mediante "
        "un producto escalar de quince términos, seguido de la función logística. La estructura "
        "del flujo es la siguiente: se consulta primero la caché de Redis; si la entrada no "
        "existe, se calcula la predicción y se responde de inmediato; la escritura en la caché, la "
        "persistencia en MongoDB y la difusión por WebSocket se realizan en una goroutine "
        "posterior a la respuesta.")
    parr(doc,
        "Esta separación es deliberada: el enunciado exige una latencia inferior a 100 "
        "milisegundos, y bloquear la respuesta hasta confirmar la escritura en la base de datos "
        "sometería ese presupuesto a la latencia de MongoDB. El endpoint de lote aplica el mismo "
        "principio de concurrencia lanzando una goroutine por elemento.")

    h(doc, "7.4 Evaluación de latencia", 2)
    parr(doc,
        f"Se ejecutaron {LAT['solicitudes']} solicitudes consecutivas contra el servicio "
        "desplegado en contenedores, con perfiles distintos en cada una para evitar que la caché "
        "distorsionara la medición.")
    tabla(doc, ["Estadístico", "Valor (ms)"], [
        ["Media", f"{LAT['media']}"],
        ["Mínimo", f"{LAT['min']}"],
        ["Percentil 50", f"{LAT['p50']}"],
        ["Percentil 95", f"{LAT['p95']}"],
        ["Percentil 99", f"{LAT['p99']}"],
        ["Máximo", f"{LAT['max']}"],
    ], [2.4, 2.0])
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(f"El percentil 99 es de {LAT['p99']} ms, aproximadamente dieciocho veces inferior "
                  "al umbral de 100 ms que establece el enunciado. El requisito se cumple con "
                  "holgura incluso en el peor caso observado.")
    r.bold = True
    r.font.size = Pt(12)
    doc.add_paragraph()
    figura(doc, "08_latencia_api.png",
           "Figura 3. Medición de latencia sobre 200 solicitudes al servicio contenerizado.")
    doc.add_paragraph()
    figura(doc, "07_pruebas_api.png",
           "Figura 4. Pruebas funcionales: autenticación, validación de entrada y caché.")
    doc.add_page_break()

    h(doc, "7.5 Canal WebSocket en tiempo real", 2)
    parr(doc,
        "El endpoint /ws implementa el protocolo WebSocket conforme al RFC 6455 sobre la "
        "biblioteca estándar: promueve la conexión HTTP mediante http.Hijacker, calcula la "
        "respuesta del handshake con SHA-1 sobre la clave del cliente concatenada con el GUID "
        "definido en la especificación, y emite tramas de texto sin máscara.")
    parr(doc,
        "El servidor mantiene un registro de clientes conectados y difunde cada predicción en "
        "cuanto se produce, además de un latido cada quince segundos con las métricas acumuladas. "
        "Cuando un cliente no consume sus mensajes con suficiente rapidez, el mensaje se descarta "
        "en lugar de bloquear al emisor, de modo que un consumidor lento no degrada el servicio "
        "para los demás.")
    parr(doc,
        "La especificación admite dos esquemas de URI: ws:// para conexiones sin cifrar, que es el "
        "empleado en el entorno de desarrollo, y wss:// para conexiones cifradas, que corresponde "
        "a un despliegue en producción tras un terminador TLS.")
    figura(doc, "12_websocket.png",
           "Figura 5. Canal WebSocket: handshake, difusión de predicciones y latido de métricas.")
    doc.add_page_break()

    # ---------------- 8. BASES DE DATOS ----------------
    h(doc, "8. IMPLEMENTACIÓN DE BASES DE DATOS", 1)
    parr(doc,
        "La arquitectura exige dos niveles de almacenamiento: uno persistente en MongoDB y uno de "
        "caché en Redis. Ambos clientes están escritos sobre la biblioteca estándar de Go, "
        "implementando los protocolos de alambre que el proyecto necesita —OP_MSG para MongoDB y "
        "RESP para Redis— en lugar de incorporar los SDK oficiales. La restricción del curso es "
        "trabajar en Go puro y ambos protocolos son lo bastante acotados para que la decisión no "
        "comprometa la claridad del código.")

    h(doc, "8.1 Diseño de entidades", 2)
    parr(doc, "La base de datos vacunacion contiene tres colecciones:")
    tabla(doc, ["Colección", "Propósito", "Campos principales"], [
        ["predicciones", "Registro histórico de cada consulta al modelo",
         "usuario, rol, edad, sexo, departamento, fabricante, probabilidad, "
         "clasificacion, nivel_riesgo, latencia_ms, marca_tiempo"],
        ["metricas_cluster", "Instantáneas de rendimiento del clúster",
         "nodos, rondas, perdida, duracion, marca_tiempo"],
        ["modelos", "Versiones del modelo entrenado",
         "version, pesos, metricas, fecha_entrenamiento"],
    ], [1.4, 2.2, 2.6])
    parr(doc,
        "La colección predicciones incorpora validación de esquema en el propio motor: MongoDB "
        "rechaza documentos sin los campos obligatorios o con una edad fuera del rango de 0 a 120 "
        "años. La validación en la base de datos complementa la que realiza la API, de modo que un "
        "defecto en la capa de servicio no puede corromper los datos almacenados.")
    parr(doc, "Índices definidos sobre la colección predicciones:")
    tabla(doc, ["Índice", "Clave", "Consulta que optimiza"], [
        ["idx_tiempo", "marca_tiempo descendente", "Predicciones más recientes"],
        ["idx_geo_riesgo", "departamento, nivel_riesgo", "Agregación geográfica por riesgo"],
        ["idx_usuario", "usuario, marca_tiempo", "Auditoría por usuario"],
    ], [1.5, 2.2, 2.5])

    h(doc, "8.2 MongoDB: persistencia", 2)
    parr(doc,
        "Durante las pruebas se persistieron 203 predicciones. La agregación por nivel de riesgo "
        "sobre esos registros ilustra el tipo de consulta que el panel administrativo del frontend "
        "consumirá en el siguiente entregable:")
    tabla(doc, ["Nivel de riesgo", "Registros", "Probabilidad media"], [
        ["MEDIO", "129", "0.5451"],
        ["BAJO", "73", "0.3863"],
        ["ALTO", "1", "0.8767"],
    ], [1.8, 1.4, 2.0])

    h(doc, "8.3 Redis: caché de respuestas precalculadas", 2)
    parr(doc,
        "Redis cumple la función que el enunciado describe como «recomendaciones precalculadas o "
        "respuestas parciales». Una predicción depende exclusivamente del perfil consultado, de "
        "modo que dos solicitudes con los mismos atributos producen idéntico resultado y la "
        "segunda puede resolverse sin recalcular. La clave se compone de los siete atributos del "
        "perfil y las entradas expiran a la hora.")
    parr(doc,
        "El contenedor se configura con una política allkeys-lru y un límite de 256 MB: cuando la "
        "memoria se agota, Redis descarta las entradas menos usadas recientemente en lugar de "
        "rechazar escrituras. Para una caché, perder una entrada antigua es preferible a dejar de "
        "aceptar nuevas.")
    figura(doc, "10_bases_datos.png",
           "Figura 6. MongoDB con sus colecciones e índices, y Redis con las claves en caché.")
    doc.add_page_break()

    # ---------------- 9. DOCKER ----------------
    h(doc, "9. DESPLIEGUE CON DOCKER COMPOSE", 1)
    parr(doc,
        "El sistema completo se despliega mediante Docker Compose sobre una red interna llamada "
        "clusterml. Las imágenes de Go se construyen en dos etapas: una de compilación sobre "
        "golang:1.27-alpine y otra de ejecución sobre alpine:3.20, lo que reduce la imagen final a "
        "unos pocos megabytes al no incluir el compilador.")
    tabla(doc, ["Servicio", "Imagen", "Puerto", "Función"], [
        ["api", "construida localmente", "8090 → 8080", "Coordinadora REST/WebSocket"],
        ["mongodb", "mongo:7", "27017", "Almacenamiento persistente"],
        ["redis", "redis:7-alpine", "6380 → 6379", "Caché de predicciones"],
        ["coordinador", "construida localmente", "interno 9000", "Master del clúster (perfil)"],
        ["nodo1..3", "construida localmente", "interno", "Nodos de cómputo (perfil)"],
    ], [1.2, 1.8, 1.3, 2.0])
    parr(doc,
        "Los nodos del clúster se declaran bajo el perfil entrenamiento y no se levantan en el "
        "arranque ordinario, porque el entrenamiento es un proceso por lotes y no un servicio "
        "permanente. Su comunicación con el coordinador ocurre dentro de la red interna, sin "
        "exponer ese tráfico al anfitrión: solo la API publica puertos hacia el exterior.")
    parr(doc,
        "Cada servicio declara una comprobación de salud y las dependencias se expresan con la "
        "condición service_healthy, de modo que la API no arranca hasta que MongoDB y Redis "
        "respondan correctamente. Esto evita el fallo habitual de un servicio que intenta "
        "conectarse a una base de datos que todavía está inicializándose.")
    figura(doc, "09_docker_compose.png",
           "Figura 7. Servicios desplegados con Docker Compose y direcciones de la red interna.")
    doc.add_page_break()

    # ---------------- 10. EVIDENCIAS ----------------
    h(doc, "10. EVIDENCIAS DE LA IMPLEMENTACIÓN Y PRUEBAS", 1)
    parr(doc,
        "El enunciado pide verificar el servicio con Postman. Para ello se preparó la colección "
        "docs/postman/CC65_Vacunacion_API.postman_collection.json, con doce solicitudes que "
        "recorren todos los endpoints expuestos. Cada una lleva asociada una aserción automática "
        "que comprueba el código de respuesta, la forma del cuerpo devuelto y, en los doce casos, "
        "que el tiempo de respuesta sea inferior a 100 milisegundos. De este modo la ejecución "
        "completa de la colección produce en una sola pantalla la evidencia del cumplimiento del "
        "requisito de latencia.")
    parr(doc,
        "En paralelo, el script scripts/pruebas_api.sh reproduce las mismas comprobaciones desde "
        "la terminal y añade una medición de latencia sobre 200 solicitudes consecutivas. Su "
        "salida queda registrada en docs/salida_pruebas_api.txt, de forma que la verificación no "
        "depende de una herramienta gráfica y puede repetirse en una canalización automatizada.")
    tabla(doc, ["#", "Prueba", "Resultado"], [
        ["1", "GET /api/salud sin autenticación", "200, los tres componentes activos"],
        ["2", "POST /api/login con credenciales válidas", "200, token de 176 caracteres"],
        ["3", "POST /api/login con contraseña incorrecta", "401"],
        ["4", "POST /api/predecir sin token", "401"],
        ["5", "Predicción: 15 años, Cusco, intervalo corto", "p = 0.8767, riesgo ALTO"],
        ["6", "Predicción: 68 años, Lima, seguimiento sostenido", "p = 0.1151, riesgo BAJO"],
        ["7", "Caché: perfil nuevo consultado dos veces", "fallo y luego acierto"],
        ["8", "Validación: edad fuera de rango", "400 con mensaje descriptivo"],
        ["9", "Lote de 5 perfiles en paralelo", "5 resultados coherentes"],
        ["10", "200 solicitudes consecutivas", f"p99 = {LAT['p99']} ms"],
        ["11", "GET /api/metricas", "Métricas completas del servicio"],
    ], [0.4, 3.2, 2.6])
    parr(doc,
        "Las predicciones de las pruebas 5 y 6 ilustran el comportamiento del modelo en los "
        "extremos del espectro. El perfil adolescente fuera de Lima con intervalo corto entre "
        "dosis obtiene una probabilidad de deserción de 0.8767, mientras que el adulto mayor en "
        "Lima con seguimiento sostenido obtiene 0.1151. La diferencia es coherente con los "
        "coeficientes aprendidos durante el entrenamiento, donde la condición de menor de "
        "dieciocho años presentaba el peso positivo más alto.")
    doc.add_paragraph()
    figura(doc, "13_postman.png",
           "Figura 8. Ejecución de la colección de Postman: las doce solicitudes superan sus "
           "aserciones y responden por debajo del umbral de 100 ms.")
    parr(doc,
        "Las solicitudes séptima y octava merecen una precisión metodológica. Están destinadas a "
        "demostrar el funcionamiento de la caché: la primera debe resolverse en el modelo y la "
        "segunda recuperarse de Redis. Una versión anterior de la prueba consultaba un perfil "
        "fijo que ya había sido almacenado por una comprobación previa del mismo script, con lo "
        "que ambas llamadas devolvían el indicador de acierto en caché. La prueba informaba "
        "éxito, pero no demostraba el comportamiento que afirmaba verificar. Se corrigió "
        "mediante un script de pre-solicitud que genera un perfil con edad e intervalo "
        "aleatorios, y solo entonces la evidencia mostró la secuencia real de fallo seguido de "
        "acierto, con probabilidad idéntica en ambas respuestas.")
    doc.add_page_break()

    # ---------------- 11. GITHUB ----------------
    h(doc, "11. TRABAJO EN GITHUB Y TABLERO KANBAN", 1)
    parr(doc, "Repositorio público: https://github.com/yagocz/cc65-vacunacion-nacional")
    parr(doc,
        "El desarrollo sigue Git Flow. Las ramas de esta entrega se integraron a la rama principal "
        "mediante confirmaciones de fusión sin avance rápido, de modo que el grafo del historial "
        "conserva visible la estructura de ramas.")
    tabla(doc, ["Rama", "Contenido", "Entregable"], [
        ["feature/carga-concurrente", "Cargador concurrente y núcleo del modelo", "PC3"],
        ["feature/etiquetado-desercion", "Reconstrucción de trayectorias", "PC3"],
        ["feature/cluster-distribuido", "Protocolo TCP, coordinador, nodos", "PC3"],
        ["feature/informe-gaps", "Informe y evidencias", "PC3"],
        ["feature/api-coordinadora", "API REST/WebSocket, JWT, Swagger, caché", "PC4"],
        ["feature/docker-persistencia", "Docker Compose, MongoDB, Redis", "PC4"],
        ["feature/postman", "Colección de pruebas de la API", "PC4"],
    ], [2.2, 3.0, 1.0])
    parr(doc,
        "El tablero Kanban de GitHub Projects registra doce tareas que cubren los tres "
        "entregables. Al cierre de la PC4 figuran diez en la columna Done y dos en Todo, "
        "correspondientes al frontend y la evaluación experimental del TB2.")
    parr(doc, "Tablero: https://github.com/users/yagocz/projects/1", cursiva=True)
    figura(doc, "06_tablero_kanban.png",
           "Figura 9. Tablero Kanban con el seguimiento de las tareas del proyecto.")
    doc.add_page_break()

    # ---------------- 12. CONCLUSIONES ----------------
    h(doc, "12. CONCLUSIONES", 1)
    for c in [
        f"El requisito de latencia se cumple con un margen amplio. Sobre {LAT['solicitudes']} "
        f"solicitudes al servicio contenerizado, el percentil 99 fue de {LAT['p99']} milisegundos "
        "frente al umbral de 100 que fija el enunciado. El margen no proviene de una optimización "
        "sofisticada sino de dos decisiones de diseño simples: mantener el modelo en memoria y "
        "diferir la persistencia a una goroutine posterior a la respuesta.",

        "La topología en estrella es la adecuada para el algoritmo elegido. En el descenso de "
        "gradiente distribuido los nodos no necesitan intercambiar información entre sí, de modo "
        "que una malla completa añadiría enlaces sin aportar valor. El coordinador constituye un "
        "punto único de fallo, pero su carga es independiente del tamaño del conjunto de datos: "
        "agrega quince valores por nodo y por ronda.",

        "Implementar los protocolos de MongoDB y Redis sobre la biblioteca estándar resultó "
        "viable y fue coherente con la restricción del curso. OP_MSG requiere un constructor BSON "
        "y un marco de mensajes de dieciséis bytes; RESP es un protocolo de texto de pocas líneas. "
        "El ejercicio obligó a entender qué ocurre por debajo de un SDK, en lugar de delegarlo.",

        "La separación entre la respuesta y los efectos secundarios es lo que permite cumplir el "
        "presupuesto de latencia. Escribir en MongoDB, actualizar la caché y difundir por "
        "WebSocket ocurre después de que el cliente ya recibió su respuesta. Si esas operaciones "
        "fueran síncronas, la latencia quedaría sujeta a la de la base de datos.",

        "Una prueba que pasa no siempre demuestra lo que afirma. La prueba de la caché reportaba "
        "éxito porque consultaba un perfil ya almacenado por una prueba anterior del mismo "
        "script: ambas llamadas provenían de la caché y la evidencia no mostraba el fallo inicial. "
        "Corregirla para usar un perfil aleatorio fue lo que convirtió el resultado en evidencia "
        "real.",
    ]:
        p = doc.add_paragraph(c, style="List Number")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # ---------------- 13. RECOMENDACIONES ----------------
    h(doc, "13. RECOMENDACIONES", 1)
    for r in [
        "Medir la latencia bajo carga concurrente antes del TB2. Las cifras actuales provienen de "
        "solicitudes secuenciales; un escenario con decenas de clientes simultáneos podría revelar "
        "contención que la prueba actual no expone.",

        "Trasladar las credenciales de los usuarios a MongoDB con las contraseñas cifradas. El "
        "esquema actual las mantiene en memoria y se documenta como datos de prueba, lo que es "
        "aceptable para un entregable académico pero no para un despliegue real.",

        "Añadir un terminador TLS para habilitar wss:// en el canal WebSocket. El protocolo admite "
        "ambos esquemas y la implementación actual solo expone el no cifrado, suficiente para "
        "desarrollo pero inadecuado para datos de salud en producción.",

        "Evaluar la elevación del tiempo de vida de la caché para perfiles frecuentes. La tasa de "
        "acierto observada fue baja porque las pruebas emplearon perfiles distintos de forma "
        "deliberada; en uso real, con consultas repetidas sobre los mismos grupos poblacionales, "
        "conviene medir la distribución efectiva antes de fijar el parámetro.",

        "Incorporar pruebas automatizadas sobre los clientes de MongoDB y Redis. Ambos "
        "implementan protocolos binarios escritos a mano y un cambio en su lógica de "
        "serialización podría pasar inadvertido hasta fallar en ejecución.",
    ]:
        p = doc.add_paragraph(r, style="List Number")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # ---------------- 14. ANEXOS ----------------
    h(doc, "14. ANEXOS", 1)
    tabla(doc, ["Recurso", "Enlace o ubicación"], [
        ["Repositorio GitHub", "https://github.com/yagocz/cc65-vacunacion-nacional"],
        ["Tablero Kanban", "https://github.com/users/yagocz/projects/1"],
        ["Documentación Swagger", "http://localhost:8090/swagger (con el stack desplegado)"],
        ["Conjunto de datos", "Plataforma Nacional de Datos Abiertos — MINSA"],
        ["Video de presentación", "Pendiente (entregable TB2)"],
    ], [1.9, 4.3])
    parr(doc, "Evidencias versionadas en el directorio docs/ del repositorio:")
    tabla(doc, ["Archivo", "Contenido"], [
        ["salida_pruebas_api.txt", "Once pruebas funcionales y de latencia"],
        ["salida_websocket.txt", "Traza del canal en tiempo real"],
        ["salida_docker.txt", "Estado de los servicios y red interna"],
        ["salida_basedatos.txt", "Colecciones, índices y agregaciones"],
        ["salida_swagger.txt", "Endpoints y esquemas documentados"],
        ["capturas/", "Doce capturas de terminal de todas las etapas"],
    ], [2.3, 4.0])
    parr(doc, "Comandos para reproducir el entorno:")
    p = doc.add_paragraph()
    r = p.add_run("docker compose up -d --build\n"
                  "bash scripts/pruebas_api.sh http://localhost:8090\n"
                  "python scripts/prueba_websocket.py localhost 8090")
    r.font.name = "Consolas"
    r.font.size = Pt(10)

    # ---------------- 15. BIBLIOGRAFÍA ----------------
    h(doc, "15. BIBLIOGRAFÍA", 1)
    for b in [
        "Fette, I., & Melnikov, A. (2011). The WebSocket Protocol (RFC 6455). Internet "
        "Engineering Task Force. https://www.rfc-editor.org/rfc/rfc6455",

        "Jones, M., Bradley, J., & Sakimura, N. (2015). JSON Web Token (JWT) (RFC 7519). Internet "
        "Engineering Task Force. https://www.rfc-editor.org/rfc/rfc7519",

        "Li, M., Andersen, D. G., Park, J. W., Smola, A. J., Ahmed, A., Josifovski, V., Long, J., "
        "Shekita, E. J., & Su, B. Y. (2014). Scaling distributed machine learning with the "
        "parameter server. 11th USENIX Symposium on Operating Systems Design and Implementation, "
        "583–598.",

        "Ministerio de Salud del Perú. (2025). Vacunación contra COVID-19 [Conjunto de datos]. "
        "Plataforma Nacional de Datos Abiertos.",

        "MongoDB, Inc. (2024). MongoDB wire protocol specification. "
        "https://www.mongodb.com/docs/manual/reference/mongodb-wire-protocol/",

        "Redis Ltd. (2024). Redis serialization protocol specification. "
        "https://redis.io/docs/latest/develop/reference/protocol-spec/",

        "Donovan, A. A. A., & Kernighan, B. W. (2015). The Go programming language. "
        "Addison-Wesley Professional.",
    ]:
        p = doc.add_paragraph(b)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Inches(-0.3)
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.space_after = Pt(8)

    doc.save(SALIDA)
    print(f"[ok] {SALIDA}")
    print(f"     {SALIDA.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
