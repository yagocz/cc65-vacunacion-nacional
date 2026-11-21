# -*- coding: utf-8 -*-
"""
Ejecuta la coleccion de Postman sin depender de la aplicacion grafica.

Lee docs/postman/CC65_Vacunacion_API.postman_collection.json, resuelve las
variables, reproduce los scripts de pre-solicitud necesarios y comprueba la
asercion de latencia que lleva cada solicitud. La salida queda en
docs/salida_postman.txt y sirve de evidencia para el informe.

Uso:
    python scripts/ejecutar_postman.py [base_url]
"""
import io
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
COLECCION = RAIZ / "docs" / "postman" / "CC65_Vacunacion_API.postman_collection.json"
SALIDA = RAIZ / "docs" / "salida_postman.txt"
UMBRAL_MS = 100.0


def resolver(texto, vars_):
    """Sustituye {{variable}} por su valor."""
    if not isinstance(texto, str):
        return texto
    for k, v in vars_.items():
        texto = texto.replace("{{" + k + "}}", str(v))
    return texto


def ejecutar(base_url):
    col = json.loads(COLECCION.read_text(encoding="utf-8"))
    vars_ = {v["key"]: v["value"] for v in col.get("variable", [])}
    vars_["base_url"] = base_url

    # Perfil aleatorio para las pruebas de cache (replica el pre-request script)
    vars_["edad_unica"] = random.randint(20, 75)
    vars_["dias_unico"] = random.randint(40, 200)

    filas = []
    for i, item in enumerate(col["item"], 1):
        req = item["request"]
        metodo = req["method"]
        url = req["url"]
        url = url["raw"] if isinstance(url, dict) else url
        url = resolver(url, vars_)

        cabeceras = {}
        for h in req.get("header", []):
            if h.get("disabled"):
                continue
            cabeceras[h["key"]] = resolver(h["value"], vars_)

        cuerpo = None
        if req.get("body", {}).get("raw"):
            cuerpo = resolver(req["body"]["raw"], vars_).encode("utf-8")

        peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras,
                                          method=metodo)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(peticion, timeout=10) as r:
                codigo = r.status
                datos = r.read()
        except urllib.error.HTTPError as e:
            codigo = e.code
            datos = e.read()
        ms = (time.perf_counter() - t0) * 1000

        # Capturar el token del login para las solicitudes protegidas
        if codigo == 200 and "login" in url:
            try:
                j = json.loads(datos)
                if "token" in j:
                    vars_["token"] = j["token"]
            except (ValueError, KeyError):
                pass

        nombre = item["name"]
        nombre = nombre.split(". ", 1)[1] if ". " in nombre[:4] else nombre
        filas.append((i, nombre, codigo, ms, ms < UMBRAL_MS))

    return filas


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090"
    filas = ejecutar(base_url)

    L = []
    sep = "=" * 70
    L.append(sep)
    L.append("COLECCION POSTMAN — VERIFICACION DE LAS 12 SOLICITUDES")
    L.append(sep)
    L.append("  coleccion : CC65 — API Vacunación Nacional (Caso 7)")
    L.append("  base_url  : " + base_url)
    L.append("  requisito : cada solicitud debe responder en menos de 100 ms")
    L.append(sep)
    L.append("")
    L.append("  #   solicitud                                     HTTP         ms")
    L.append("  " + "-" * 66)
    for i, nombre, codigo, ms, ok in filas:
        L.append("  %-3d %-45s %-9d %6.2f  %s"
                 % (i, nombre[:45], codigo, ms, "PASA" if ok else "FALLA"))
    L.append("  " + "-" * 66)

    pasan = sum(1 for f in filas if f[4])
    tiempos = [f[3] for f in filas]
    L.append("  solicitudes que pasan : %d/%d" % (pasan, len(filas)))
    L.append("  latencia maxima       : %.2f ms" % max(tiempos))
    L.append("  latencia media        : %.2f ms" % (sum(tiempos) / len(tiempos)))
    L.append("  TODAS CUMPLEN EL REQUISITO DE 100 ms: %s"
             % ("SI" if pasan == len(filas) else "NO"))
    L.append(sep)

    texto = "\n".join(L) + "\n"
    io.open(SALIDA, "w", encoding="utf-8", newline="\n").write(texto)
    sys.stdout.reconfigure(encoding="utf-8")
    print(texto)
    print("[ok] %s" % SALIDA)


if __name__ == "__main__":
    main()
