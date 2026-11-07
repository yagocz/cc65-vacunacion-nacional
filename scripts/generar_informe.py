"""
Genera el informe de la PC3 en formato Word a partir de la plantilla oficial
del curso, con todas las cifras obtenidas de la ejecución real del sistema.

Uso:
    python scripts/generar_informe.py
"""
import json
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
SALIDA = RAIZ / "1ACC0065_PC3_202620_Informe_U202412543.docx"

NEGRO = RGBColor(0x00, 0x00, 0x00)
AZUL = RGBColor(0x00, 0x00, 0x00)  # titulos en negro, como la plantilla
GRIS = RGBColor(0x44, 0x44, 0x44)

hist = json.loads((DOCS / "historial_entrenamiento.json").read_text(encoding="utf-8"))
bench = json.loads((DOCS / "benchmark_speedup.json").read_text(encoding="utf-8"))
M = hist["metricas"]


def sombrear(celda, color="1F4E79"):
    tc = celda._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), color)
    tc.append(sh)


def h(doc, texto, nivel=1):
    p = doc.add_heading(texto, level=nivel)
    for r in p.runs:
        r.font.color.rgb = AZUL
    return p


def parr(doc, texto, cursiva=False, size=11, just=True):
    p = doc.add_paragraph()
    if just:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(texto)
    r.font.size = Pt(size)
    r.italic = cursiva
    return p


def tabla(doc, cabeceras, filas, anchos=None):
    t = doc.add_table(rows=1, cols=len(cabeceras))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(cabeceras):
        cel = t.rows[0].cells[i]
        cel.text = ""
        run = cel.paragraphs[0].add_run(c)
        run.bold = True
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        sombrear(cel)
    for fila in filas:
        celdas = t.add_row().cells
        for i, v in enumerate(fila):
            celdas[i].text = ""
            run = celdas[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(9.5)
    if anchos:
        for fila in t.rows:
            for i, w in enumerate(anchos):
                fila.cells[i].width = Inches(w)
    doc.add_paragraph()
    return t


def figura(doc, archivo, titulo, ancho=6.3):
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
    r.font.color.rgb = GRIS


def main():
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Inches(1.0)
        s.top_margin = s.bottom_margin = Inches(1.0)
    est = doc.styles["Normal"]
    est.font.name = "Times New Roman"
    est.font.size = Pt(12)
    est.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    # Encabezados en Times New Roman y negro, como la plantilla oficial.
    for nivel in (1, 2, 3):
        hs = doc.styles[f"Heading {nivel}"]
        hs.font.name = "Times New Roman"
        hs.font.color.rgb = NEGRO
        hs.font.bold = True
        hs.font.size = Pt(15 - nivel)

    # ---------------- CARÁTULA ----------------
    # Replica el formato de la plantilla oficial: Times New Roman 14,
    # centrado, en negro, con el logo institucional.
    def cen(texto, size=14, bold=False, space=0):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space)
        r = p.add_run(texto)
        r.font.name = "Times New Roman"
        r.font.size = Pt(size)
        r.bold = bold
        r.font.color.rgb = NEGRO
        return p

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
    cen("Entregable 1 — PC3", 14, True, 0)
    cen("Caso 7: Clasificación y Seguimiento de la Vacunación Nacional", 12, False, 0)

    for _ in range(4):
        doc.add_paragraph()
    cen("2026-20", 14, False, 0)
    cen("Lima, Perú", 14, False, 0)
    doc.add_page_break()

    # ---------------- ÍNDICE ----------------
    h(doc, "ÍNDICE", 1)
    indice = [
        "1. Resumen", "2. Descripción del problema y motivación",
        "3. Objetivos", "4. Objetivo del estudiante (Student Outcome 4)",
        "   4.1 Ética profesional", "   4.2 Responsabilidad profesional",
        "   4.3 Juicios sobre el impacto de la solución",
        "5. Desarrollo", "   5.1 Dataset seleccionado",
        "   5.2 Arquitectura de la solución",
        "   5.3 Parte A — Carga y limpieza concurrente",
        "   5.4 Etiquetado de la variable objetivo",
        "   5.5 Parte B — Diseño del modelo ML distribuido",
        "   5.6 Paralelización: técnicas y patrones en Go",
        "   5.7 Evidencias de la implementación",
        "   5.8 Evaluación de escalabilidad",
        "   5.9 Trabajo en GitHub y tablero Kanban",
        "6. Conclusiones", "7. Recomendaciones", "8. Anexos", "9. Bibliografía",
    ]
    for it in indice:
        p = doc.add_paragraph(it)
        p.paragraph_format.space_after = Pt(2)
    doc.add_page_break()

    # ---------------- 1. RESUMEN ----------------
    h(doc, "1. RESUMEN", 1)
    parr(doc,
        "El presente informe documenta el primer entregable (PC3) del Trabajo Final del curso "
        "CC65 Programación Concurrente y Distribuida. El equipo desarrolla un sistema concurrente "
        "y distribuido que procesa el Registro Nacional de Vacunación contra la COVID-19 del "
        "Ministerio de Salud del Perú y entrena, sobre un clúster de nodos de cómputo, un modelo "
        "de Regresión Logística Distribuida capaz de predecir la deserción en la aplicación de "
        "segundas y terceras dosis.")
    parr(doc,
        "El conjunto de datos empleado contiene 93,675,827 registros nominales de dosis aplicadas "
        "(9.91 GB), publicado bajo licencia Open Data Commons Attribution en la Plataforma Nacional "
        "de Datos Abiertos, con fecha de corte al 30 de noviembre de 2025. La solución está escrita "
        "íntegramente en Go, utilizando exclusivamente la biblioteca estándar, y aplica los "
        "mecanismos de concurrencia del curso: goroutines, channels, sync.Mutex y sync.WaitGroup, "
        "además de comunicación TCP entre el coordinador y los nodos del clúster.")
    parr(doc,
        "En esta entrega se completó la carga y limpieza concurrente de los 93.6 millones de "
        "registros en 7.80 segundos (1,301 MB/s), la reconstrucción de las trayectorias de "
        "vacunación de 30,968,883 personas, el etiquetado de la variable objetivo y el "
        "entrenamiento distribuido del modelo sobre cuatro nodos comunicados por TCP, que alcanzó "
        f"una exactitud de {M['exactitud']:.4f} y un valor F1 de {M['f1']:.4f}. El motor de "
        f"entrenamiento presenta un Speedup máximo de {max(r['speedup'] for r in bench['resultados']):.2f}× "
        "con 12 trabajadores concurrentes.")
    doc.add_page_break()

    # ---------------- 2. PROBLEMA ----------------
    h(doc, "2. DESCRIPCIÓN DEL PROBLEMA Y MOTIVACIÓN", 1)
    parr(doc,
        "Entre 2021 y 2025 el Estado peruano aplicó más de 93 millones de dosis contra la COVID-19. "
        "Sin embargo, la cobertura no se distribuye de manera uniforme a lo largo del esquema de "
        "vacunación: una proporción considerable de la población recibió la primera o la segunda "
        "dosis y nunca regresó por el refuerzo correspondiente. Ese abandono, conocido como "
        "deserción vacunal, reduce la protección efectiva de la población y desperdicia el esfuerzo "
        "logístico ya invertido en captar a esas personas.")
    parr(doc,
        "El análisis de los datos confirma la magnitud del fenómeno. De las 30,968,883 personas "
        "registradas en el padrón nacional, 8,339,819 —es decir, el 27.06 %— no alcanzaron la "
        "tercera dosis dentro de la ventana de observación, pese a haber iniciado su esquema. "
        "Identificar de antemano qué perfiles presentan mayor riesgo de abandono permitiría al "
        "sector salud dirigir las campañas de seguimiento hacia donde el problema es más denso, en "
        "lugar de distribuir el esfuerzo de manera homogénea sobre todo el territorio.")

    h(doc, "Pregunta que atiende el impacto social", 2)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Inches(0.4)
    r = p.add_run("¿Qué perfiles de población tienen mayor probabilidad de abandonar el esquema de "
                  "vacunación antes de completar la tercera dosis, y en qué departamentos se "
                  "concentran, de modo que el Ministerio de Salud pueda focalizar las campañas de "
                  "seguimiento y las brigadas móviles donde el abandono es más probable?")
    r.bold = True; r.font.size = Pt(11); r.font.color.rgb = AZUL
    doc.add_paragraph()

    parr(doc,
        "La respuesta no es una abstracción académica: se traduce en decisiones operativas "
        "concretas sobre dónde ubicar brigadas móviles, a qué grupos enviar recordatorios y qué "
        "establecimientos de salud requieren refuerzo. El sistema entrega, para cada perfil "
        "demográfico y geográfico, una probabilidad de deserción calculada sobre datos reales.")
    doc.add_page_break()

    # ---------------- 3. OBJETIVOS ----------------
    h(doc, "3. OBJETIVOS", 1)
    h(doc, "Objetivo general", 2)
    parr(doc,
        "Construir una aplicación concurrente y distribuida de alto rendimiento, desarrollada "
        "íntegramente en Go, que procese más de un millón de registros de datos abiertos del Estado "
        "peruano y entrene de forma distribuida un modelo de Regresión Logística capaz de predecir "
        "la deserción en el esquema nacional de vacunación.")
    h(doc, "Objetivos específicos de la PC3", 2)
    for i, o in enumerate([
        "Seleccionar y validar un conjunto de datos abiertos del Portal Nacional que supere el "
        "millón de registros y permita responder la pregunta de impacto social planteada.",
        "Implementar un cargador concurrente que procese el archivo mediante un Worker Pool sobre "
        "channels, aplicando fan-out y fan-in, y que realice la limpieza y validación de los datos.",
        "Reconstruir la trayectoria de vacunación de cada persona a partir de los registros "
        "nominales de dosis y derivar la variable objetivo binaria de deserción.",
        "Diseñar e implementar el motor de entrenamiento distribuido mediante el patrón Parameter "
        "Server, con comunicación TCP entre un coordinador y N nodos de cómputo.",
        "Evaluar experimentalmente la escalabilidad de la solución mediante el cálculo del Speedup "
        "y la eficiencia para distinto número de trabajadores concurrentes.",
        "Gestionar el desarrollo con Git Flow en un repositorio público y dar seguimiento a las "
        "tareas mediante un tablero Kanban en GitHub.",
    ], 1):
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
        "El trabajo se desarrolla sobre datos de salud de alcance nacional, lo que impone "
        "obligaciones éticas que el equipo asumió de manera explícita en el diseño. El conjunto de "
        "datos publicado por el MINSA es seudonimizado: cada persona aparece identificada por un "
        "UUID numérico y no por su documento de identidad. El sistema conserva esa condición en "
        "todo el procesamiento; el UUID se emplea únicamente para agrupar las dosis de un mismo "
        "individuo mediante una función hash, y en ningún punto del flujo se intenta reidentificar "
        "a una persona ni se almacena un identificador reversible.")
    parr(doc,
        "Una segunda decisión ética relevante fue el tratamiento de la censura a la derecha en el "
        "etiquetado. Resultaba técnicamente sencillo clasificar como desertor a todo aquel que no "
        "hubiera completado su esquema a la fecha de corte, lo que habría elevado artificialmente "
        "el número de casos positivos y mejorado las métricas aparentes del modelo. El equipo "
        "descartó esa opción: 152,534 personas cuya última dosis es posterior a la ventana de 180 "
        "días fueron excluidas del conjunto de entrenamiento, porque aún están dentro del plazo "
        "razonable para completar el esquema y etiquetarlas como desertoras sería falsear el dato.")
    parr(doc,
        "En el mismo sentido, se conservaron 17,105 registros que un analizador sintáctico ingenuo "
        "habría descartado silenciosamente. Esas filas contienen un punto y coma dentro del campo "
        "GRUPO_RIESGO, protegido por comillas, correspondiente a diagnósticos como «AFECCIONES "
        "CARDIACAS; INSUFICIENCIA CARDIACA…». Descartarlas habría eliminado de forma sistemática a "
        "pacientes con comorbilidades cardíacas, precisamente una población de alto riesgo. El "
        "analizador se corrigió para respetar las comillas y recuperar esos registros, y el "
        "resultado quedó documentado como evidencia.")
    parr(doc,
        "Finalmente, todas las cifras presentadas en este informe provienen de la ejecución real "
        "del sistema sobre el conjunto de datos completo. Las salidas en crudo de cada programa se "
        "versionan en el directorio docs/ del repositorio, de modo que cualquier afirmación "
        "cuantitativa puede ser verificada de forma independiente.")

    h(doc, "4.2 Demuestra responsabilidad profesional para el logro de los objetivos", 2)
    parr(doc,
        "El equipo organizó el trabajo en frentes independientes que corresponden a las partes de "
        "la arquitectura propuesta por el enunciado, lo que permitió avanzar en paralelo y mantener "
        "trazabilidad. El seguimiento se gestionó mediante un tablero Kanban en GitHub con doce "
        "tareas registradas, de las cuales seis corresponden a esta entrega y se encuentran "
        "cerradas con evidencia asociada.")
    parr(doc,
        "El desarrollo siguió Git Flow de manera estricta: una rama de funcionalidad por cada "
        "componente —carga concurrente, etiquetado y clúster distribuido—, integradas a la rama "
        "principal mediante confirmaciones de fusión explícitas que preservan la estructura del "
        "historial. Cada confirmación documenta no solo qué se implementó, sino las decisiones de "
        "diseño que la motivaron y las cifras medidas que la respaldan.")
    parr(doc,
        "La responsabilidad profesional se manifestó también en la disposición a corregir el "
        "trabajo propio cuando la evidencia lo exigió. El primer entrenamiento se ejecutó con 50 "
        "rondas y una tasa de aprendizaje de 0.5; al inspeccionar el historial se comprobó que la "
        "norma del gradiente permanecía en 0.0317, lo que indicaba que el modelo no había "
        "convergido y que las métricas obtenidas —una exhaustividad de 0.3258— subestimaban la "
        "capacidad real del clasificador. Se repitió el entrenamiento con 300 rondas y una tasa de "
        f"2.0, con lo que la exhaustividad ascendió a {M['exhaustividad']:.4f}. Reportar la "
        "configuración definitiva sin haber detectado esa deficiencia habría sido un resultado "
        "cómodo pero incorrecto.")

    h(doc, "4.3 Emite juicios considerando el impacto de las soluciones en el contexto global, "
            "social, ambiental y económico", 2)
    parr(doc,
        "Impacto social. La solución está orientada a un problema de salud pública con "
        "consecuencias medibles sobre la población. Los 8,339,819 casos de deserción identificados "
        "no constituyen un dato estadístico abstracto: representan personas que iniciaron su "
        "esquema de vacunación y quedaron con protección incompleta. El modelo permite anticipar "
        "qué perfiles presentan mayor riesgo de abandono, y los coeficientes aprendidos resultan "
        "directamente interpretables por un decisor de política pública. El predictor de mayor "
        "peso positivo es la condición de menor de dieciocho años (+1.176), lo que señala a la "
        "población pediátrica y adolescente como el grupo prioritario para las campañas de "
        "seguimiento.")
    parr(doc,
        "Impacto económico. Cada dosis no aplicada tras una primera captación representa una "
        "inversión parcialmente perdida en logística, cadena de frío y personal. Focalizar las "
        "campañas de recuperación en los perfiles de mayor riesgo, en lugar de distribuir el "
        "esfuerzo de manera uniforme, incrementa el rendimiento del gasto público en salud. El "
        "sistema procesa el padrón nacional completo en menos de ocho segundos sobre hardware de "
        "escritorio convencional, lo que lo vuelve viable para una institución pública sin "
        "necesidad de infraestructura especializada.")
    parr(doc,
        "Impacto ambiental. La eficiencia computacional tiene una dimensión ambiental que suele "
        "pasarse por alto. El procesamiento concurrente reduce el tiempo de cómputo de 2,126 "
        f"milisegundos a {min(r['ms_recortada'] for r in bench['resultados']):.0f} milisegundos por "
        "iteración del gradiente, lo que se traduce en un consumo energético proporcionalmente "
        "menor. Para cargas de trabajo que se ejecutan de forma periódica sobre datos nacionales, "
        "esa diferencia es significativa a lo largo del tiempo.")
    parr(doc,
        "Contexto global. La arquitectura es independiente del dominio específico de la vacunación "
        "contra la COVID-19. El mismo esquema —carga concurrente, reconstrucción de trayectorias "
        "individuales y entrenamiento distribuido— es aplicable al seguimiento de cualquier esquema "
        "de inmunización con dosis múltiples, incluidos los programas regulares de vacunación "
        "infantil, y resulta transferible a otros sistemas de salud de la región que enfrentan el "
        "mismo problema de abandono.")
    doc.add_page_break()

    # ---------------- 5. DESARROLLO ----------------
    h(doc, "5. DESARROLLO", 1)

    h(doc, "5.1 Dataset seleccionado", 2)
    parr(doc,
        "El caso asignado al equipo corresponde al número 7 del enunciado: Clasificación y "
        "Seguimiento de la Vacunación Nacional, con el Registro Nacional de Vacunación (HIS-MINSA / "
        "REUNIS) como fuente base y Regresión Logística Distribuida como algoritmo de aprendizaje.")
    tabla(doc, ["Campo", "Valor"], [
        ["Nombre", "Vacunación contra COVID-19"],
        ["Entidad publicadora", "Ministerio de Salud del Perú (MINSA)"],
        ["Plataforma", "Plataforma Nacional de Datos Abiertos"],
        ["Archivo", "vacunas_covid.csv"],
        ["Registros", "93,675,827"],
        ["Columnas", "14"],
        ["Tamaño", "9.91 GB (1.04 GB comprimido)"],
        ["Formato", "CSV, separador punto y coma, UTF-8"],
        ["Fecha de corte", "30 de noviembre de 2025"],
        ["Licencia", "Open Data Commons Attribution License"],
    ], [2.0, 4.3])
    parr(doc,
        "Conviene dejar constancia de una particularidad en el acceso al recurso. La ficha del "
        "conjunto de datos en el portal redirige al formulario de inicio de sesión, de modo que el "
        "archivo no es alcanzable desde esa dirección. El enlace efectivo de descarga se encuentra "
        "en la página del recurso y apunta al repositorio institucional del Ministerio de Salud "
        "(files.minsa.gob.pe). El script scripts/descargar.sh automatiza la obtención y "
        "descompresión del archivo, de modo que cualquier integrante del equipo o evaluador pueda "
        "reproducir el punto de partida.")
    parr(doc,
        "Cada fila del archivo corresponde a una dosis aplicada, no a una persona. Las columnas "
        "relevantes son UUID (identificador seudonimizado del vacunado), DOSIS (número de dosis), "
        "FECHA_VACUNACION, EDAD, SEXO, GRUPO_RIESGO, FABRICANTE y la jerarquía geográfica "
        "DEPARTAMENTO, PROVINCIA y DISTRITO.")

    h(doc, "5.2 Arquitectura de la solución", 2)
    parr(doc,
        "El sistema se organiza en las cuatro partes que define el enunciado. La presente entrega "
        "cubre íntegramente las partes A y B; las partes C y D corresponden a los entregables PC4 "
        "y TB2 respectivamente.")
    tabla(doc, ["Parte", "Componente", "Estado", "Entregable"], [
        ["A", "Cargador de datos concurrente", "Implementado", "PC3"],
        ["—", "Etiquetado y vectorización", "Implementado", "PC3"],
        ["B", "Motor de entrenamiento distribuido", "Implementado", "PC3"],
        ["C", "API REST / WebSocket coordinadora", "Planificado", "PC4"],
        ["—", "Persistencia MongoDB y Redis", "Planificado", "PC4"],
        ["—", "Contenerización con Docker Compose", "Planificado", "PC4"],
        ["D", "Interfaz web SPA", "Planificado", "TB2"],
    ], [0.8, 2.9, 1.3, 1.3])

    h(doc, "5.3 Parte A — Carga y limpieza concurrente", 2)
    parr(doc,
        "El cargador divide el archivo de 9.91 GB en tantos bloques como trabajadores se "
        "configuren, ajustando cada corte a la frontera de línea más próxima para que ningún "
        "registro quede partido entre dos bloques. Los bloques se distribuyen mediante un canal "
        "(fan-out), cada trabajador analiza el suyo de manera independiente y emite un agregado "
        "parcial por un segundo canal, que un reductor consolida (fan-in). Al no existir memoria "
        "compartida mutable entre trabajadores, la única sincronización necesaria es el cierre "
        "ordenado de los canales mediante sync.WaitGroup.")
    parr(doc,
        "Durante la validación se detectó que 17,105 filas contenían un punto y coma dentro del "
        "campo GRUPO_RIESGO, protegido por comillas dobles. El analizador sintáctico inicial las "
        "descartaba por presentar quince campos en lugar de catorce. Dado que esas filas "
        "corresponden a pacientes con comorbilidades cardíacas, se corrigió el analizador para "
        "respetar las comillas; tras la corrección el sistema procesa la totalidad de los registros "
        "sin descartes.")
    tabla(doc, ["Métrica", "Valor"], [
        ["Registros procesados", "93,675,827"],
        ["Filas malformadas", "0"],
        ["Tiempo de procesamiento", "7.80 s"],
        ["Rendimiento", "12,013,392 registros/s"],
        ["Throughput", "1,301 MB/s"],
        ["Trabajadores", "12"],
    ], [3.1, 3.2])
    figura(doc, "01_cargador_concurrente.png",
           "Figura 1. Ejecución del cargador concurrente sobre los 93.6 millones de registros.")
    doc.add_page_break()

    h(doc, "5.4 Etiquetado de la variable objetivo", 2)
    parr(doc,
        "Dado que cada fila representa una dosis y no una persona, fue necesario reconstruir la "
        "trayectoria de vacunación de cada individuo. El procedimiento emplea partición por hash "
        "del UUID: la función FNV-1a asigna de forma determinista cada identificador a uno de los N "
        "fragmentos, de modo que todas las dosis de una misma persona son procesadas siempre por el "
        "mismo agregador. Esta propiedad elimina la necesidad de un mapa compartido protegido por "
        "cerrojo; cada agregador escribe exclusivamente en su propia estructura.")
    parr(doc,
        "La variable objetivo se definió conforme al planteamiento del caso 7, que se refiere a la "
        "deserción en la aplicación de segundas y terceras dosis:")
    tabla(doc, ["Etiqueta", "Criterio", "Personas", "Proporción"], [
        ["y = 1 (desertó)", "Alcanzó 1 o 2 dosis y no recibió la siguiente", "8,339,819", "27.06 %"],
        ["y = 0 (completó)", "Alcanzó 3 o más dosis", "22,476,530", "72.94 %"],
        ["Excluidas", "Última dosis dentro de los 180 días previos al corte", "152,534", "0.49 %"],
    ], [1.5, 2.7, 1.1, 1.0])
    parr(doc,
        "La exclusión de 152,534 registros responde al fenómeno de censura a la derecha, propio del "
        "análisis de supervivencia: una persona cuya última dosis es reciente todavía se encuentra "
        "dentro del plazo razonable para recibir la siguiente, y clasificarla como desertora "
        "introduciría un sesgo sistemático en el modelo.")
    parr(doc,
        "El conjunto resultante contiene 30,816,349 muestras etiquetadas, cada una representada por "
        "un vector de quince características que combinan atributos demográficos (edad, sexo), "
        "temporales (días transcurridos desde la primera dosis, intervalo entre la primera y la "
        "última), geográficos (pertenencia a Lima, condición de zona no metropolitana) y clínicos "
        "(grupo de riesgo priorizado, fabricante de la vacuna).")
    figura(doc, "02_etiquetado_desercion.png",
           "Figura 2. Reconstrucción de trayectorias y etiquetado de la variable objetivo.")
    doc.add_page_break()

    h(doc, "5.5 Parte B — Diseño del modelo ML distribuido", 2)
    parr(doc,
        "El algoritmo asignado es la Regresión Logística Distribuida. El modelo estima la "
        "probabilidad de deserción mediante la función logística aplicada a una combinación lineal "
        "de las características, y se entrena minimizando la verosimilitud logarítmica negativa "
        "mediante descenso de gradiente.")
    parr(doc,
        "La distribución del cómputo sigue el patrón Parameter Server, exactamente como describe el "
        "enunciado: cada nodo procesa un lote de datos, calcula el gradiente del error local y "
        "transmite ese gradiente por TCP al coordinador, que actualiza los pesos del modelo global. "
        "El ciclo de cada ronda de entrenamiento es el siguiente:")
    for paso in [
        "El coordinador difunde el vector de pesos vigente a los N nodos mediante mensajes TCP "
        "emitidos en paralelo.",
        "Cada nodo calcula el gradiente sobre su fragmento del conjunto de datos, paralelizando "
        "internamente el cálculo entre K goroutines.",
        "El coordinador espera la recepción de los N gradientes locales; esta espera constituye la "
        "barrera de sincronización de la ronda.",
        "Los gradientes se agregan mediante media ponderada por el número de muestras de cada nodo, "
        "lo que garantiza que el resultado sea idéntico al que produciría un cálculo centralizado.",
        "El coordinador actualiza los pesos aplicando la tasa de aprendizaje y la regularización L2, "
        "que no penaliza el término de sesgo.",
    ]:
        p = doc.add_paragraph(paso, style="List Number")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    parr(doc,
        "Los nodos no comparten estado entre sí ni se comunican directamente, de modo que el único "
        "punto de sincronización del sistema distribuido es la agregación en el coordinador. El "
        "protocolo de mensajería se implementó sobre TCP con un marco binario explícito de cinco "
        "bytes de cabecera —tipo de mensaje y longitud del cuerpo—, sin recurrir a bibliotecas "
        "externas de serialización.")

    h(doc, "5.6 Paralelización: técnicas y patrones en Go", 2)
    parr(doc,
        "La solución combina dos niveles de paralelismo que operan de manera simultánea. El nivel "
        "distribuido reparte el conjunto de datos entre N procesos independientes comunicados por "
        "TCP; el nivel concurrente, dentro de cada proceso, divide el trabajo entre K goroutines "
        "que comparten el espacio de memoria.")
    tabla(doc, ["Mecanismo", "Dónde se aplica", "Qué resuelve"], [
        ["Goroutines", "Cargador, nodos, coordinador", "Unidades de ejecución concurrentes ligeras"],
        ["Channels", "Reparto de bloques y recolección de parciales",
         "Comunicación sin memoria compartida (fan-out / fan-in)"],
        ["sync.WaitGroup", "Cierre de workers y barrera de ronda",
         "Esperar la finalización de todas las goroutines"],
        ["sync.Mutex", "Volcado de acumuladores en el nodo",
         "Exclusión mutua en la única sección crítica"],
        ["TCP (net)", "Coordinador ↔ nodos", "Comunicación entre procesos del clúster"],
        ["Partición por hash", "Etiquetado por UUID",
         "Evitar un mapa compartido con cerrojo"],
    ], [1.5, 2.2, 2.6])
    parr(doc,
        "La decisión de diseño con mayor incidencia en el rendimiento fue la granularidad del "
        "bloqueo. Cada goroutine acumula el gradiente sobre un arreglo privado y adquiere el cerrojo "
        "una sola vez, al finalizar su lote, para volcar el resultado sobre la estructura "
        "compartida. La alternativa consistente en bloquear en cada muestra sería correcta pero "
        "inservible: con más de treinta millones de muestras por ronda, la contención serializaría "
        "por completo la ejecución. Con acumuladores privados, el número de adquisiciones de cerrojo "
        "por ronda es igual al número de goroutines y no al número de muestras procesadas.")
    doc.add_page_break()

    h(doc, "5.7 Evidencias de la implementación", 2)
    parr(doc,
        "El entrenamiento se ejecutó sobre un clúster de cuatro nodos, cada uno con tres goroutines "
        "internas, durante 300 rondas de descenso de gradiente distribuido. La totalidad de las "
        "30,816,349 muestras participó en cada ronda.")
    tabla(doc, ["Métrica", "Valor"], [
        ["Nodos del clúster", "4 (procesos independientes, comunicados por TCP)"],
        ["Goroutines por nodo", "3"],
        ["Rondas de entrenamiento", "300"],
        ["Muestras", "30,816,349"],
        ["Pérdida inicial", "0.693147"],
        ["Pérdida final", f"{hist['historial'][-1]['perdida']:.6f}"],
        ["Tiempo de entrenamiento", f"{hist['segundos']:.2f} s"],
        ["Tiempo por ronda", f"{hist['segundos']*1000/300:.1f} ms"],
    ], [2.6, 3.7])
    parr(doc, "Las métricas de clasificación, calculadas sobre la matriz de confusión global "
              "consolidada a partir de los cuatro nodos, son las siguientes:")
    tabla(doc, ["Métrica", "Valor", "Interpretación"], [
        ["Exactitud", f"{M['exactitud']:.4f}",
         "Proporción global de clasificaciones correctas"],
        ["Precisión", f"{M['precision']:.4f}",
         "De los señalados como desertores, cuántos lo son"],
        ["Exhaustividad", f"{M['exhaustividad']:.4f}",
         "De los desertores reales, cuántos detecta el modelo"],
        ["F1", f"{M['f1']:.4f}", "Media armónica de precisión y exhaustividad"],
    ], [1.5, 1.2, 3.6])
    figura(doc, "03_entrenamiento_distribuido.png",
           "Figura 3. Entrenamiento distribuido: convergencia de la pérdida y evaluación global.")
    doc.add_paragraph()
    parr(doc,
        "Los coeficientes aprendidos admiten lectura directa en términos del problema. Un "
        "coeficiente positivo incrementa la probabilidad estimada de deserción:")
    nombres = ["sesgo", "edad normalizada", "sexo masculino", "sexo femenino",
               "días desde la primera dosis", "intervalo entre primera y última dosis",
               "fuera de Lima", "grupo de riesgo priorizado", "fabricante Pfizer",
               "fabricante Sinopharm", "fabricante AstraZeneca", "fabricante no registrado",
               "departamento de Lima", "menor de 18 años", "60 años o más"]
    pesos = hist["pesos"]
    orden = sorted(range(len(pesos)), key=lambda i: -pesos[i])[:6]
    tabla(doc, ["Característica", "Coeficiente", "Lectura"],
          [[nombres[i], f"{pesos[i]:+.4f}",
            "Aumenta el riesgo de deserción" if pesos[i] > 0 else "Reduce el riesgo"]
           for i in orden], [2.6, 1.3, 2.4])
    parr(doc,
        "El resultado de mayor relevancia para la política pública es que la condición de menor de "
        f"dieciocho años presenta el coeficiente positivo más alto ({pesos[13]:+.4f}), lo que "
        "identifica a la población pediátrica y adolescente como el grupo con mayor propensión al "
        "abandono del esquema. En sentido opuesto, el intervalo entre la primera y la última dosis "
        f"presenta el coeficiente negativo de mayor magnitud ({pesos[5]:+.4f}): quienes mantuvieron "
        "un seguimiento sostenido a lo largo del tiempo tienden a completar el esquema.")
    figura(doc, "05_pesos_modelo.png",
           "Figura 4. Coeficientes aprendidos por el modelo de Regresión Logística Distribuida.")
    doc.add_page_break()

    h(doc, "5.8 Evaluación de escalabilidad", 2)
    parr(doc,
        "Para aislar el rendimiento del motor de entrenamiento respecto del costo de la "
        "comunicación de red, se midió el cálculo del gradiente sobre el conjunto completo en modo "
        "secuencial y concurrente, con distinto número de goroutines. Se realizaron diez corridas "
        "por configuración y se reporta la media recortada, que descarta el valor máximo y el "
        "mínimo de cada serie para neutralizar el ruido del sistema operativo.")
    filas = [["Secuencial", f"{bench['secuencial']:.2f}", "—", "—"]]
    for r in bench["resultados"]:
        filas.append([f"{r['workers']} workers", f"{r['ms_recortada']:.2f}",
                      f"{r['speedup']:.4f}×", f"{r['eficiencia']*100:.2f} %"])
    tabla(doc, ["Configuración", "Tiempo (ms)", "Speedup", "Eficiencia"], filas,
          [1.8, 1.5, 1.5, 1.5])
    mejor = max(bench["resultados"], key=lambda r: r["speedup"])
    parr(doc,
        f"El Speedup máximo alcanzado es de {mejor['speedup']:.2f}× con {mejor['workers']} "
        "trabajadores, cifra que coincide con el número de núcleos lógicos del procesador empleado. "
        "La eficiencia se mantiene por encima del 92 % hasta los seis trabajadores —el número de "
        "núcleos físicos— y desciende progresivamente a partir de ese punto, cuando los "
        "trabajadores adicionales pasan a ejecutarse sobre hilos SMT que comparten unidades de "
        "ejecución. Con dieciséis trabajadores el Speedup retrocede a "
        f"{[r for r in bench['resultados'] if r['workers']==16][0]['speedup']:.2f}×, efecto "
        "atribuible a la sobre-suscripción: el planificador multiplexa más goroutines que hilos de "
        "hardware disponibles.")
    figura(doc, "04_benchmark_speedup.png",
           "Figura 5. Medición de Speedup y eficiencia del cálculo del gradiente.")
    parr(doc, "Entorno de medición: AMD Ryzen 5 5600X (6 núcleos físicos, 12 hilos lógicos), "
              "15.9 GB de memoria RAM, Windows 11, Go 1.27.0. Todas las corridas se ejecutaron en "
              "la misma máquina.", cursiva=True)
    doc.add_page_break()

    h(doc, "5.9 Trabajo en GitHub y tablero Kanban", 2)
    parr(doc,
        "El proyecto se aloja en un repositorio público y el desarrollo sigue Git Flow. Se "
        "emplearon tres ramas de funcionalidad, una por componente de la arquitectura, integradas a "
        "la rama principal mediante confirmaciones de fusión sin avance rápido, de modo que el "
        "grafo del historial conserva visible la estructura de ramas.")
    tabla(doc, ["Rama", "Contenido"], [
        ["feature/carga-concurrente", "Cargador concurrente, núcleo del modelo, script de descarga"],
        ["feature/etiquetado-desercion", "Reconstrucción de trayectorias y vectorización"],
        ["feature/cluster-distribuido", "Protocolo TCP, coordinador, nodos y benchmark"],
        ["develop", "Rama de integración"],
        ["main", "Versión estable del entregable"],
    ], [2.4, 3.9])
    parr(doc,
        "El seguimiento de actividades se realiza mediante un tablero Kanban público en GitHub "
        "Projects, con doce tareas que cubren los tres entregables del trabajo final. Las siete "
        "correspondientes a la PC3 se encuentran en la columna Done, cada una con la evidencia de "
        "su ejecución asociada; las cinco restantes permanecen en Todo y corresponden a la PC4 y "
        "al TB2. El tablero está vinculado al repositorio, de modo que el cierre de una incidencia "
        "actualiza automáticamente su posición en el flujo.")
    figura(doc, "06_tablero_kanban.png",
           "Figura 6. Tablero Kanban del proyecto: 7 tareas completadas (PC3) y 5 pendientes "
           "(PC4 y TB2).")
    doc.add_paragraph()
    parr(doc, "Tablero: https://github.com/users/yagocz/projects/1", cursiva=True)
    doc.add_page_break()

    # ---------------- 6. CONCLUSIONES ----------------
    h(doc, "6. CONCLUSIONES", 1)
    for c in [
        "El conjunto de datos seleccionado supera ampliamente el requisito de volumen del "
        "enunciado. Con 93,675,827 registros, el Registro Nacional de Vacunación excede en más de "
        "noventa veces el mínimo de un millón exigido, y en dieciocho veces el volumen estimado "
        "para el caso 7. Procesarlo de forma secuencial resultaría impracticable, lo que justifica "
        "el enfoque concurrente no como un ejercicio académico sino como una necesidad real.",
        "La partición por hash del identificador resultó ser la decisión de diseño más acertada "
        "del trabajo. Al garantizar que todas las dosis de una persona sean procesadas por el "
        "mismo agregador, se elimina por completo la necesidad de un mapa compartido con cerrojo. "
        "Treinta millones de trayectorias se reconstruyen sin una sola operación de sincronización "
        "sobre la estructura de datos principal.",
        "La granularidad del bloqueo determina si el paralelismo produce ganancia o la destruye. "
        "Con acumuladores privados por goroutine, el número de adquisiciones de cerrojo por ronda "
        "es igual al número de trabajadores y no al número de muestras, lo que permitió alcanzar "
        f"un Speedup de {mejor['speedup']:.2f}× con una eficiencia superior al 92 % en el rango de "
        "núcleos físicos.",
        "El modelo distribuido converge de manera estable y produce resultados interpretables. La "
        f"pérdida desciende de 0.693147 a {hist['historial'][-1]['perdida']:.6f} a lo largo de 300 "
        f"rondas, con una exactitud de {M['exactitud']:.4f} y un valor F1 de {M['f1']:.4f}. Más "
        "relevante que las métricas agregadas es que los coeficientes admiten lectura directa por "
        "parte de un decisor de política pública.",
        "La verificación sistemática de los resultados intermedios evitó dos errores que habrían "
        "comprometido la validez del trabajo. El primero fue el descarte silencioso de 17,105 "
        "registros de pacientes con comorbilidades cardíacas por una deficiencia del analizador "
        "sintáctico. El segundo, la presentación de un modelo no convergido cuyas métricas "
        "subestimaban su capacidad real. En ambos casos la revisión de la evidencia, y no la "
        "inspección del código, fue lo que reveló el problema.",
    ]:
        p = doc.add_paragraph(c, style="List Number")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # ---------------- 7. RECOMENDACIONES ----------------
    h(doc, "7. RECOMENDACIONES", 1)
    for r in [
        "Incorporar la validación cruzada mediante la separación del conjunto en particiones de "
        "entrenamiento y prueba. La evaluación actual se realiza sobre la totalidad de los datos, "
        "lo que impide descartar el sobreajuste, aunque el riesgo sea bajo dada la relación entre "
        "treinta millones de muestras y quince parámetros.",
        "Ajustar el umbral de decisión según el objetivo de la política pública. Con el umbral "
        f"estándar de 0.5 el modelo alcanza una exhaustividad de {M['exhaustividad']:.4f}; para una "
        "campaña de seguimiento suele ser preferible reducir el umbral y aceptar un mayor número "
        "de falsos positivos antes que dejar sin contactar a personas que efectivamente "
        "desertarán.",
        "Enriquecer el conjunto de características con variables de accesibilidad geográfica, como "
        "la distancia al establecimiento de salud más próximo o la densidad de centros de "
        "vacunación por distrito, que previsiblemente explican una parte sustancial de la deserción "
        "en zonas rurales.",
        "Desplegar los nodos del clúster en máquinas físicamente distintas para la PC4. La presente "
        "implementación ejecuta los cuatro nodos como procesos independientes comunicados por TCP "
        "sobre la misma máquina, lo que valida el protocolo pero no la latencia de red real.",
        "Documentar explícitamente las limitaciones del modelo en la interfaz de usuario que se "
        "desarrolle para el TB2. El sistema estima probabilidades agregadas por perfil y no debe "
        "emplearse para tomar decisiones sobre personas individuales, consideración ética que debe "
        "quedar visible para el usuario final.",
    ]:
        p = doc.add_paragraph(r, style="List Number")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # ---------------- 8. ANEXOS ----------------
    h(doc, "8. ANEXOS", 1)
    tabla(doc, ["Recurso", "Enlace o ubicación"], [
        ["Repositorio GitHub", "https://github.com/yagocz/cc65-vacunacion-nacional"],
        ["Tablero Kanban", "Pestaña Issues y Projects del repositorio"],
        ["Conjunto de datos", "https://www.datosabiertos.gob.pe/dataset/vacunación-contra-covid-19-ministerio-de-salud-minsa"],
        ["Descarga directa", "https://files.minsa.gob.pe/s/J8C75Y55nkFazWF/download"],
        ["Video de presentación", "Pendiente (entregable TB2)"],
    ], [1.9, 4.4])
    parr(doc, "Evidencias de ejecución versionadas en el directorio docs/ del repositorio:")
    tabla(doc, ["Archivo", "Contenido"], [
        ["salida_cargador.txt", "Carga concurrente de los 93.6 millones de registros"],
        ["salida_etiquetado.txt", "Reconstrucción de trayectorias y etiquetado"],
        ["salida_entrenamiento.txt", "Entrenamiento distribuido y evaluación"],
        ["salida_benchmark.txt", "Medición de Speedup y eficiencia"],
        ["historial_entrenamiento.json", "Pérdida por ronda, pesos y métricas finales"],
        ["benchmark_speedup.json", "Tiempos crudos de las corridas de escalabilidad"],
        ["capturas/", "Capturas de terminal de cada etapa"],
    ], [2.4, 3.9])

    # ---------------- 9. BIBLIOGRAFÍA ----------------
    h(doc, "9. BIBLIOGRAFÍA", 1)
    for b in [
        "Ministerio de Salud del Perú. (2025). Vacunación contra COVID-19 [Conjunto de datos]. "
        "Plataforma Nacional de Datos Abiertos. "
        "https://www.datosabiertos.gob.pe/dataset/vacunación-contra-covid-19-ministerio-de-salud-minsa",
        "Dean, J., Corrado, G., Monga, R., Chen, K., Devin, M., Le, Q. V., Mao, M. Z., Ranzato, M., "
        "Senior, A., Tucker, P., Yang, K., & Ng, A. Y. (2012). Large scale distributed deep "
        "networks. Advances in Neural Information Processing Systems, 25, 1223–1231.",
        "Donovan, A. A. A., & Kernighan, B. W. (2015). The Go programming language. "
        "Addison-Wesley Professional.",
        "Li, M., Andersen, D. G., Park, J. W., Smola, A. J., Ahmed, A., Josifovski, V., Long, J., "
        "Shekita, E. J., & Su, B. Y. (2014). Scaling distributed machine learning with the "
        "parameter server. 11th USENIX Symposium on Operating Systems Design and Implementation, "
        "583–598.",
        "Organización Mundial de la Salud. (2022). Global COVID-19 vaccination strategy in a "
        "changing world. World Health Organization.",
        "Zheng, A., & Casari, A. (2018). Feature engineering for machine learning: Principles and "
        "techniques for data scientists. O'Reilly Media.",
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
