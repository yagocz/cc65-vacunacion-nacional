"""
Genera el Reporte de Participación de la PC3 reutilizando el documento
oficial del curso como plantilla.

Se edita el .docx existente en lugar de construir uno nuevo, de modo que
la fuente, los colores, los bordes y la estructura de tablas se conservan
exactamente como en el formato entregado por el docente.

Uso:
    python scripts/generar_participacion.py
"""
import shutil
from pathlib import Path

from docx import Document

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLA = Path(r"C:\Users\Yago Caldas\Downloads\CC65-Participación-202620 .docx")
SALIDA = RAIZ / "CC65-Participación-202620.docx"

# --------------------------------------------------------------------------
# Reparto de responsabilidades: cuatro por integrante, equivalentes en carga.
# Cada bloque corresponde a una parte identificable del entregable, de modo
# que los tres puedan sustentar su aporte en la exposición.
# --------------------------------------------------------------------------
RESPONSABILIDADES = {
    "Andre Angel Chipana Rios": [
        "Validación del modelo de clasificación: revisión de la matriz de confusión global y "
        "análisis de las métricas de exactitud, precisión, exhaustividad y F1 obtenidas sobre "
        "los 30,816,349 registros etiquetados.",
        "Análisis del umbral de decisión: evaluación del compromiso entre precisión y "
        "exhaustividad y su implicancia para una campaña de salud pública.",
        "Interpretación de los coeficientes del modelo y su lectura en términos de política "
        "pública, identificando a la población pediátrica como grupo de mayor deserción.",
        "Elaboración de las conclusiones y recomendaciones del informe, incluidas las "
        "limitaciones declaradas y las líneas de mejora para la PC4.",
    ],
    "Ernesto Yago Caldas Zapata": [
        "Parte A: cargador concurrente del CSV del MINSA mediante Worker Pool con fan-out y "
        "fan-in sobre channels, procesando 93,675,827 registros en 7.80 segundos.",
        "Etiquetado de la deserción por partición de hash del UUID, reconstruyendo las "
        "trayectorias de 30,968,883 personas sin recurrir a un mapa compartido con cerrojo.",
        "Parte B: protocolo TCP, coordinador y nodos del clúster bajo el patrón Parameter "
        "Server, con entrenamiento distribuido sobre cuatro nodos.",
        "Gestión del repositorio con Git Flow, tablero Kanban en GitHub Projects y redacción "
        "del informe.",
    ],
    "Ricardo Rafael Rivas Carrillo": [
        "Identificación y validación de la fuente de datos: localización del Registro Nacional "
        "de Vacunación del MINSA y de su enlace efectivo de descarga.",
        "Interpretación del caso 7 asignado y verificación de la correspondencia entre el "
        "planteamiento del problema y el algoritmo de Regresión Logística Distribuida.",
        "Benchmark de escalabilidad: medición del Speedup y la eficiencia para 2, 4, 6, 8, 12 "
        "y 16 trabajadores, con diez corridas por configuración y media recortada.",
        "Redacción de la sección de paralelización del informe: técnicas, patrones de "
        "concurrencia en Go y justificación del planteamiento.",
    ],
}

COMENTARIO = """Los tres integrantes cumplieron con las responsabilidades asignadas para la PC3 y cada uno tiene commits propios en el repositorio, visibles en el historial bajo su cuenta de GitHub.

El trabajo se organizó en tres frentes que corresponden a las partes de la arquitectura definida en el enunciado. Ricardo Rivas identificó la fuente de datos y resolvió un obstáculo que bloqueaba el avance: la ficha del conjunto de datos en la Plataforma Nacional de Datos Abiertos redirige al formulario de inicio de sesión, y el archivo real se sirve desde el repositorio institucional del MINSA. También interpretó correctamente que el caso 7 se refiere a la vacunación contra la COVID-19, y se encargó del benchmark de escalabilidad.

Ernesto Yago Caldas Zapata implementó la Parte A (cargador concurrente) y la Parte B (motor de entrenamiento distribuido) de la arquitectura, además de coordinar la integración de ramas y el tablero Kanban. El sistema procesa los 93,675,827 registros del Registro Nacional de Vacunación en 7.80 segundos a 1,301 MB/s, reconstruye las trayectorias de 30,968,883 personas y entrena un modelo de Regresión Logística sobre un clúster de cuatro nodos comunicados por TCP.

Andre Chipana se encargó de la validación del modelo y de la interpretación de sus resultados en términos de política pública, así como de las conclusiones y recomendaciones del informe. Su revisión identificó que el coeficiente de mayor peso positivo corresponde a la condición de menor de dieciocho años, lo que señala a la población pediátrica como el grupo prioritario para las campañas de seguimiento.

Dos hallazgos surgidos de la verificación de resultados intermedios merecen mención. El primero: 17,105 registros de pacientes con comorbilidades cardíacas eran descartados silenciosamente por el analizador sintáctico inicial, al contener un punto y coma dentro de un campo entrecomillado; el analizador se corrigió para recuperarlos. El segundo: el primer entrenamiento no había convergido —la norma del gradiente permanecía en 0.0317— y sus métricas subestimaban la capacidad real del modelo, por lo que se repitió con una configuración adecuada, elevando la exhaustividad de 0.3258 a 0.5714.

El seguimiento se gestionó mediante un tablero Kanban público en GitHub Projects con doce tareas: las siete de esta entrega figuran en la columna Done y las cinco restantes, correspondientes a la PC4 y al TB2, permanecen en Todo.

Repositorio: https://github.com/yagocz/cc65-vacunacion-nacional
Tablero Kanban: https://github.com/users/yagocz/projects/1"""


def set_celda(celda, texto):
    """Reemplaza el texto conservando el formato del primer run."""
    parrafos = celda.paragraphs
    p = parrafos[0]
    if p.runs:
        p.runs[0].text = texto
        for r in p.runs[1:]:
            r.text = ""
    else:
        p.add_run(texto)
    for extra in parrafos[1:]:
        extra._element.getparent().remove(extra._element)


def set_celda_multilinea(celda, texto):
    """Escribe un texto de varios párrafos conservando el formato base."""
    parrafos = celda.paragraphs
    base = parrafos[0]
    for extra in parrafos[1:]:
        extra._element.getparent().remove(extra._element)

    lineas = [l for l in texto.split("\n") if l.strip()]
    if base.runs:
        base.runs[0].text = lineas[0]
        for r in base.runs[1:]:
            r.text = ""
    else:
        base.add_run(lineas[0])

    import copy
    for linea in lineas[1:]:
        nuevo = copy.deepcopy(base._element)
        base._element.addnext(nuevo)
        from docx.text.paragraph import Paragraph
        pn = Paragraph(nuevo, celda)
        if pn.runs:
            pn.runs[0].text = linea
            for r in pn.runs[1:]:
                r.text = ""
        base = pn


def main():
    if not PLANTILLA.exists():
        raise SystemExit(f"No se encuentra la plantilla: {PLANTILLA}")

    shutil.copy(PLANTILLA, SALIDA)
    doc = Document(str(SALIDA))

    # ---- Tabla 0: datos de la entrega ----
    t0 = doc.tables[0]
    set_celda(t0.rows[0].cells[1], "PC3")
    set_celda(t0.rows[1].cells[1], "Grupo 1 — CC65")
    set_celda(t0.rows[2].cells[1],
              "Clasificación y Seguimiento de la Vacunación Nacional: predicción de deserción "
              "en segundas y terceras dosis mediante Regresión Logística Distribuida en Go "
              "(Caso 7)")
    set_celda(t0.rows[3].cells[1], "Ernesto Yago Caldas Zapata")

    # ---- Tabla 1: comentario del team leader ----
    set_celda_multilinea(doc.tables[1].rows[1].cells[0], COMENTARIO)

    # ---- Tabla 2: responsabilidades ----
    t2 = doc.tables[2]
    orden = [
        ("1", "Andre Angel Chipana Rios"),
        ("2", "Ernesto Yago Caldas Zapata"),
        ("3", "Ricardo Rafael Rivas Carrillo"),
    ]
    fila = 2
    for nro, nombre in orden:
        for tarea in RESPONSABILIDADES[nombre]:
            if fila >= len(t2.rows):
                break
            r = t2.rows[fila]
            set_celda(r.cells[0], nro)
            set_celda(r.cells[1], nombre)
            set_celda(r.cells[2], tarea)
            set_celda(r.cells[3], "X")
            set_celda(r.cells[4], "")
            set_celda(r.cells[5], "")
            fila += 1

    doc.save(str(SALIDA))
    print(f"[ok] {SALIDA}")
    print(f"     {SALIDA.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
