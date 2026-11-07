"""
Genera el Reporte de Participación de la PC3 en formato Word.

Uso:
    python scripts/generar_participacion.py
"""
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "1ACC0065_Participacion_202620.docx"
NEGRO = RGBColor(0, 0, 0)


def sombrear(celda, color="D9D9D9"):
    tc = celda._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), color)
    tc.append(sh)


def main():
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Inches(0.9)
        s.top_margin = s.bottom_margin = Inches(0.9)
    est = doc.styles["Normal"]
    est.font.name = "Times New Roman"
    est.font.size = Pt(11)
    est.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    def cen(texto, size=12, bold=False, space=4):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space)
        r = p.add_run(texto)
        r.font.name = "Times New Roman"
        r.font.size = Pt(size)
        r.bold = bold
        r.font.color.rgb = NEGRO

    def just(texto, size=11):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r = p.add_run(texto)
        r.font.size = Pt(size)
        return p

    def tabla(cabeceras, filas, anchos=None, size=9.5):
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
                p = cs[i].paragraphs[0]
                if v in ("X", "—"):
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(str(v))
                r.font.size = Pt(size)
                if v == "X":
                    r.bold = True
        if anchos:
            for fila in t.rows:
                for i, w in enumerate(anchos):
                    fila.cells[i].width = Inches(w)
        doc.add_paragraph()
        return t

    # ---------------- Encabezado ----------------
    cen("1ACC0065 PROGRAMACIÓN CONCURRENTE Y DISTRIBUIDA", 13, True, 2)
    cen("REPORTE DE PARTICIPACIÓN", 13, True, 2)
    cen("CIENCIAS DE LA COMPUTACIÓN", 12, False, 12)

    tabla(["Campo", "Detalle"], [
        ["Entrega", "PC3 — Entregable 1 del Trabajo Final"],
        ["Nombre del grupo", "Grupo 1 — CC65"],
        ["Nombre de la solución",
         "Clasificación y Seguimiento de la Vacunación Nacional: predicción de "
         "deserción en segundas y terceras dosis mediante Regresión Logística "
         "Distribuida en Go (Caso 7)"],
        ["Team Leader", "Ernesto Yago Caldas Zapata (U202412543)"],
        ["Repositorio", "https://github.com/yagocz/cc65-vacunacion-nacional"],
        ["Tablero Kanban", "https://github.com/users/yagocz/projects/1"],
    ], [1.6, 5.1])

    # ---------------- Comentario ----------------
    p = doc.add_paragraph()
    r = p.add_run("Comentario del team leader")
    r.bold = True
    r.font.size = Pt(12)

    just(
        "La PC3 se organizó en tres frentes que corresponden a las partes de la arquitectura "
        "definida en el enunciado. El equipo mantuvo la misma conformación que en los entregables "
        "anteriores del curso, lo que permitió aprovechar la experiencia acumulada en el manejo de "
        "Git Flow y en el trabajo con conjuntos de datos masivos.")
    just(
        "Durante esta entrega se completaron la Parte A (cargador concurrente) y la Parte B (motor "
        "de entrenamiento distribuido) de la arquitectura. El sistema procesa los 93,675,827 "
        "registros del Registro Nacional de Vacunación del MINSA en 7.80 segundos, reconstruye las "
        "trayectorias de 30,968,883 personas y entrena un modelo de Regresión Logística sobre un "
        "clúster de cuatro nodos comunicados por TCP, alcanzando una exactitud de 0.8483 y un "
        "Speedup máximo de 9.01× con doce trabajadores concurrentes.")
    just(
        "Dos hallazgos surgidos de la verificación de resultados intermedios merecen mención. El "
        "primero: 17,105 registros correspondientes a pacientes con comorbilidades cardíacas eran "
        "descartados silenciosamente por el analizador sintáctico inicial, al contener un punto y "
        "coma dentro de un campo entrecomillado; el analizador se corrigió para recuperarlos. El "
        "segundo: el primer entrenamiento no había convergido —la norma del gradiente permanecía "
        "en 0.0317— y sus métricas subestimaban la capacidad real del modelo, por lo que se repitió "
        "con una configuración adecuada.")
    just(
        "El seguimiento se gestionó mediante un tablero Kanban público en GitHub Projects con doce "
        "tareas. Las siete correspondientes a esta entrega figuran en la columna Done con su "
        "evidencia asociada; las cinco restantes, correspondientes a la PC4 y al TB2, permanecen "
        "en Todo.")

    doc.add_paragraph()

    # ---------------- Tabla de participación ----------------
    p = doc.add_paragraph()
    r = p.add_run("Tabla de Participación")
    r.bold = True
    r.font.size = Pt(12)
    p = doc.add_paragraph()
    r = p.add_run("Marcar con una X de acuerdo al nivel de cumplimiento")
    r.italic = True
    r.font.size = Pt(10)

    filas = [
        ["1", "Andre Angel Chipana Rios",
         "Revisión del planteamiento del caso y de la pregunta de impacto social", "X", "", ""],
        ["", "", "Validación de las métricas de evaluación del modelo", "X", "", ""],
        ["", "", "Participación en la revisión del informe", "X", "", ""],
        ["2", "Ernesto Yago Caldas Zapata",
         "Parte A: cargador concurrente del CSV (Worker Pool, fan-out/fan-in)", "X", "", ""],
        ["", "", "Etiquetado de deserción por partición de hash del UUID", "X", "", ""],
        ["", "", "Parte B: protocolo TCP, coordinador y nodos del clúster", "X", "", ""],
        ["", "", "Benchmark de escalabilidad y redacción del informe", "X", "", ""],
        ["", "", "Gestión del repositorio, Git Flow y tablero Kanban", "X", "", ""],
        ["3", "Ricardo Rafael Rivas Carrillo",
         "Identificación de la fuente del conjunto de datos del MINSA", "X", "", ""],
        ["", "", "Interpretación del caso 7 y validación del algoritmo asignado", "X", "", ""],
        ["", "", "Participación en la revisión del informe", "X", "", ""],
    ]
    tabla(["N°", "Estudiante", "Responsabilidades", "Cumplió",
           "Cumplimiento parcial", "No cumplió"],
          filas, [0.4, 1.7, 2.9, 0.65, 0.9, 0.65], 9)

    doc.add_page_break()

    # ---------------- Criterios ----------------
    p = doc.add_paragraph()
    r = p.add_run("CRITERIOS DE DESCUENTO POR PARTICIPACIÓN INDIVIDUAL")
    r.bold = True
    r.font.size = Pt(12)
    just(
        "La calificación del trabajo grupal se ajustará individualmente según el nivel de "
        "compromiso y cumplimiento de las tareas asignadas. Es responsabilidad del equipo reportar "
        "objetivamente el desempeño de sus integrantes en el formato de responsabilidad.", 10)
    doc.add_paragraph()

    tabla(["Nivel de cumplimiento", "Descripción", "Descuento", "Justificación"], [
        ["Cumplió",
         "El estudiante entregó todas sus tareas asignadas (código, documentación, video) en el "
         "plazo acordado y con la calidad esperada. Participó activamente en las reuniones y la "
         "integración final.",
         "0 puntos (Nota completa)",
         "Participación responsable, proactiva y organizada que contribuyó al éxito del proyecto."],
        ["Cumplimiento Parcial",
         "El estudiante entregó sus tareas tarde o incompletas, obligando al resto del equipo a "
         "corregir o completar su parte. Su asistencia a reuniones fue irregular.",
         "-5 puntos",
         "La falta de prolijidad o puntualidad generó una carga de trabajo adicional para el resto "
         "del equipo."],
        ["No Cumplió",
         "El estudiante no entregó ninguna tarea asignada, o su aporte fue irrelevante o "
         "insuficiente. No participó en la grabación del video ni en la redacción del informe.",
         "Nota Individual: 00 (Se anula la nota del trabajo)",
         "La inacción total perjudicó gravemente el avance del proyecto. No existe evidencia de "
         "aprendizaje ni trabajo realizado."],
    ], [1.3, 2.6, 1.1, 2.2], 8.5)

    doc.save(SALIDA)
    print(f"[ok] {SALIDA}")
    print(f"     {SALIDA.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
