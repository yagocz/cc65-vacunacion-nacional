# -*- coding: utf-8 -*-
"""
Arma el ZIP del entregable de la PC4 con el codigo, las evidencias y la
documentacion. El informe y el reporte de participacion se entregan por
separado, de modo que el ZIP contiene solo el proyecto.

Uso:
    python scripts/armar_zip_pc4.py
"""
import os
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "1ACC0065_PC4_U202412543.zip"

INCLUIR = [
    "README.md",
    ".gitignore",
    "docker-compose.yml",
]
CARPETAS = [
    ("go", {".go", ".mod", ".sum"}),
    ("docker", None),
    ("scripts", None),
    ("docs/capturas", {".png"}),
    ("docs/postman", None),
]
SUELTOS_DOCS = {".txt", ".json"}

# Lo que nunca entra: datos pesados, temporales, binarios compilados
EXCLUIR_DIR = {"__pycache__", ".git", "datos", "data", "node_modules", "bin"}
EXCLUIR_EXT = {".csv", ".zip", ".7z", ".exe", ".pyc", ".tmp"}


def permitido(p: Path) -> bool:
    if any(parte in EXCLUIR_DIR for parte in p.parts):
        return False
    if p.suffix.lower() in EXCLUIR_EXT:
        return False
    if p.name.startswith("~"):
        return False
    return True


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    archivos = []

    for nombre in INCLUIR:
        p = RAIZ / nombre
        if p.is_file():
            archivos.append(p)

    for carpeta, exts in CARPETAS:
        base = RAIZ / carpeta
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or not permitido(p):
                continue
            if exts and p.suffix.lower() not in exts:
                continue
            archivos.append(p)

    # Salidas de texto de docs/ (evidencias de ejecucion)
    for p in sorted((RAIZ / "docs").glob("*")):
        if p.is_file() and p.suffix.lower() in SUELTOS_DOCS and permitido(p):
            archivos.append(p)

    if SALIDA.exists():
        SALIDA.unlink()

    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        for p in archivos:
            z.write(p, p.relative_to(RAIZ).as_posix())

    print("[ok] %s" % SALIDA)
    print("     %d archivos, %.2f MB" % (len(archivos), SALIDA.stat().st_size / 1048576))
    print()
    for p in archivos:
        print("  ", p.relative_to(RAIZ).as_posix())


if __name__ == "__main__":
    main()
