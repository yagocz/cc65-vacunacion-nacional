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
import os as _os
SALIDA = Path(_os.environ.get("PARTICIPACION_SALIDA",
    str(RAIZ / "CC65-Participación-202620-PC4.docx")))

# --------------------------------------------------------------------------
# Reparto de responsabilidades: cuatro por integrante, equivalentes en carga.
# Cada bloque corresponde a una parte identificable del entregable, de modo
# que los tres puedan sustentar su aporte en la exposición.
# --------------------------------------------------------------------------
RESPONSABILIDADES = {
    "Andre Angel Chipana Rios": [
        "Diseño de las entidades de MongoDB: definición de las tres colecciones, el esquema de "
        "validación de documentos y los cinco índices que optimizan las consultas del panel.",
        "Configuración de Redis como caché de respuestas precalculadas: estrategia de claves por "
        "perfil, tiempo de vida de una hora y política de desalojo allkeys-lru.",
        "Pruebas de funcionamiento de las bases de datos: verificación de la persistencia de 203 "
        "predicciones y de las agregaciones por nivel de riesgo.",
        "Elaboración de las conclusiones y recomendaciones del informe de la PC4.",
    ],
    "Ernesto Yago Caldas Zapata": [
        "Desarrollo de la API coordinadora en Go: endpoints REST, autenticación con tokens JWT "
        "firmados con HMAC-SHA256 y canal WebSocket conforme al RFC 6455.",
        "Implementación de los clientes de MongoDB y Redis sobre la biblioteca estándar, con los "
        "protocolos OP_MSG y RESP escritos para el proyecto.",
        "Contenerización del sistema y orquestación con Docker Compose, incluidas las "
        "comprobaciones de salud y la red interna del clúster.",
        "Gestión del repositorio con Git Flow, actualización del tablero Kanban y redacción del "
        "informe de la PC4.",
    ],
    "Ricardo Rafael Rivas Carrillo": [
        "Justificación de la topología de red del clúster: análisis comparativo entre estrella, "
        "malla y anillo frente a las necesidades del descenso de gradiente distribuido.",
        "Documentación de la API con OpenAPI 3.0: definición de los siete esquemas de datos y de "
        "los ejemplos de solicitud de cada endpoint.",
        "Elaboración de la colección de Postman con las doce solicitudes de prueba y su aserción "
        "de latencia, y verificación del cumplimiento del requisito de responder en menos de "
        "100 milisegundos sobre el servicio contenerizado.",
        "Redacción de las secciones de distribución y protocolo de comunicación TCP del informe.",
    ],
}

COMENTARIO = """Los tres integrantes cumplieron con las responsabilidades asignadas para la PC4 y cada uno tiene commits propios en el repositorio.

En esta entrega se completaron la Parte C de la arquitectura —la API coordinadora REST y WebSocket— junto con los dos niveles de almacenamiento y el despliegue contenerizado del sistema. El servicio expone el modelo entrenado sobre 30,816,349 registros y responde con una latencia media de 3.48 milisegundos; el percentil 99 es de 5.39 milisegundos, aproximadamente dieciocho veces por debajo del umbral de 100 milisegundos que fija el enunciado.

Ricardo Rivas se encargó de justificar la topología de red del clúster, comparando las alternativas de estrella, malla y anillo frente a las necesidades del descenso de gradiente distribuido, y documentó la API en OpenAPI 3.0. También preparó la colección de Postman que el enunciado solicita, con doce solicitudes que recorren todos los endpoints y comprueban automáticamente que ninguna supere los 100 milisegundos.

Ernesto Yago Caldas Zapata desarrolló la API en Go con autenticación JWT y canal WebSocket conforme al RFC 6455, implementó los clientes de MongoDB y Redis sobre la biblioteca estándar —con los protocolos OP_MSG y RESP escritos para el proyecto, en lugar de incorporar los SDK oficiales— y orquestó el despliegue con Docker Compose.

Andre Chipana diseñó las entidades de MongoDB con su validación de esquema e índices, configuró Redis como caché de respuestas precalculadas y verificó el funcionamiento de ambos almacenamientos.

Durante el desarrollo se corrigió un defecto en la propia batería de pruebas que merece mención. La prueba destinada a demostrar el funcionamiento de la caché reportaba éxito, pero ambas llamadas provenían de Redis porque el perfil consultado coincidía con el de una prueba anterior del mismo script: la prueba pasaba por una razón equivocada y no demostraba el comportamiento que afirmaba verificar. Se corrigió para emplear un perfil generado aleatoriamente, y solo entonces la evidencia mostró la secuencia de fallo seguido de acierto.

El tablero Kanban registra diez de las doce tareas completadas; las dos restantes corresponden al frontend y a la evaluación experimental del TB2.

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
    set_celda(t0.rows[0].cells[1], "PC4")
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
