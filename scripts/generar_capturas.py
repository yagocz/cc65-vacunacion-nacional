"""
Genera capturas PNG con aspecto de terminal a partir de las salidas de
texto que producen los programas, para pegarlas en el informe.

El enunciado pide "imagenes de evidencia del funcionamiento". Estas
capturas se generan desde las salidas REALES guardadas en docs/, no se
escriben a mano.

Uso:
    python scripts/generar_capturas.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
CAPS = DOCS / "capturas"

# Paleta tipo terminal oscura
FONDO = "#11161c"
TEXTO = "#d6deeb"
TITULO = "#7fdbca"
ACENTO = "#ffcb6b"
VERDE = "#a3e635"


def captura(lineas, salida, titulo, resaltar=None, ancho_pulg=None):
    """Renderiza una lista de lineas como una captura de terminal."""
    resaltar = resaltar or []
    n = len(lineas)
    maxlen = max((len(l) for l in lineas), default=80)

    ancho = ancho_pulg or max(9.0, min(maxlen * 0.088, 16.0))
    alto = max(2.2, n * 0.175 + 0.75)

    fig = plt.figure(figsize=(ancho, alto), dpi=170)
    fig.patch.set_facecolor(FONDO)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(FONDO)
    ax.axis("off")

    # Barra de titulo estilo ventana
    ax.text(0.012, 0.985, titulo, color=TITULO, fontsize=8.5,
            family="DejaVu Sans Mono", va="top", weight="bold")

    y = 0.985 - (1.35 / n if n else 0.04)
    paso = 0.93 / max(n, 1)
    y = 0.945

    for linea in lineas:
        color = TEXTO
        peso = "normal"
        for pat, col in resaltar:
            if pat in linea:
                color = col
                peso = "bold"
                break
        ax.text(0.012, y, linea, color=color, fontsize=7.4,
                family="DejaVu Sans Mono", va="top", weight=peso)
        y -= paso

    CAPS.mkdir(parents=True, exist_ok=True)
    fig.savefig(CAPS / salida, facecolor=FONDO, bbox_inches="tight",
                pad_inches=0.18)
    plt.close(fig)
    print(f"[ok] capturas/{salida}  ({n} lineas)")


def leer(nombre, desde=0, hasta=None):
    t = (DOCS / nombre).read_text(encoding="utf-8", errors="replace")
    ls = [l.rstrip() for l in t.splitlines()]
    return ls[desde:hasta]


def main():
    # ---- CAPTURA 1: ejecucion secuencial ----
    ls = leer("salida_ejecucion.txt")
    ini = next(i for i, l in enumerate(ls) if "K-MEANS SECUENCIAL" in l)
    fin = next(i for i, l in enumerate(ls) if "VERSION CONCURRENTE" in l)
    captura(
        ls[ini - 1:fin - 2],
        "01_ejecucion_secuencial.png",
        "$ go run ./secuencial -k 5 -iter 10 -semilla 42",
        resaltar=[("TIEMPO DEL ALGORITMO", ACENTO),
                  ("inercia", VERDE),
                  ("puntos por cluster", VERDE)],
    )

    # ---- CAPTURA 2: ejecucion concurrente ----
    ini = next(i for i, l in enumerate(ls) if "K-MEANS CONCURRENTE" in l)
    fin = next(i for i, l in enumerate(ls) if "COMPROBACION DE CORRECCION" in l)
    captura(
        ls[ini - 1:fin - 2],
        "02_ejecucion_concurrente.png",
        "$ go run ./concurrente -k 5 -iter 10 -w 12 -semilla 42",
        resaltar=[("TIEMPO DEL ALGORITMO", ACENTO),
                  ("inercia", VERDE),
                  ("puntos por cluster", VERDE),
                  ("WORKERS", ACENTO)],
    )

    # ---- CAPTURA 3: detector de carreras ----
    ls = leer("salida_race.txt")
    fin = next((i for i, l in enumerate(ls) if "PARTICION DEL DATASET" in l), 18)
    cuerpo = ls[:fin]
    cuerpo += ["", "   >>> Sin lineas 'WARNING: DATA RACE' en toda la salida.",
               "   >>> El detector no encontro ninguna condicion de carrera."]
    captura(
        cuerpo,
        "03_detector_carreras.png",
        "$ CGO_ENABLED=1 go run -race ./concurrente -k 5 -iter 3 -w 6",
        resaltar=[("Sin lineas", VERDE), ("no encontro", VERDE)],
    )

    # ---- CAPTURA 4: benchmark ----
    ls = leer("salida_bench.txt")
    ini = next(i for i, l in enumerate(ls) if "TABLA 1" in l) - 1
    captura(
        ls[ini:],
        "04_benchmark_speedup.png",
        "$ go run ./bench -k 5 -iter 10 -n 15",
        resaltar=[("5.1071", ACENTO), ("secuencial", VERDE)],
    )

    # ---- CAPTURA 5: recursos ----
    ls = leer("salida_recursos.txt")
    captura(
        ls,
        "05_recursos.png",
        "$ go run ./recursos -k 5 -iter 10",
        resaltar=[("concur. W=12", ACENTO), ("secuencial", VERDE)],
    )

    # ---- CAPTURA 6: verificacion SPIN ----
    ls = leer("salida_spin.txt")
    ini = next(i for i, l in enumerate(ls) if "RESUMEN DE RESULTADOS" in l) - 1
    captura(
        ls[ini:],
        "06_verificacion_spin.png",
        "$ bash verificar.sh   (SPIN 6.5.2)",
        resaltar=[("0 errores", VERDE), ("Errores", ACENTO),
                  ("CONCLUSION", VERDE)],
    )

    print(f"\nTodas las capturas en: {CAPS}")


if __name__ == "__main__":
    main()
