#!/usr/bin/env bash
# Descarga el Registro Nacional de Vacunación COVID-19 del MINSA.
#
# El dataset pesa 9.91 GB descomprimido y está excluido del repositorio.
# Cada integrante debe ejecutar este script una vez para reconstruir
# data/raw/ en su máquina.
#
# Fuente oficial:
#   https://www.datosabiertos.gob.pe/dataset/vacunación-contra-covid-19-ministerio-de-salud-minsa
#
# El enlace de la ficha redirige al login del portal; el archivo real se
# sirve desde el Nextcloud institucional del MINSA.
set -e

cd "$(dirname "$0")/.."
mkdir -p data/raw
cd data/raw

URL="https://files.minsa.gob.pe/s/J8C75Y55nkFazWF/download"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

if [ -f vacunas_covid.csv ]; then
    echo "[skip] vacunas_covid.csv ya existe ($(du -h vacunas_covid.csv | cut -f1))"
    exit 0
fi

echo "[1/3] descargando VACUNAS_COVID.zip (~1.04 GB)..."
curl -L -C - --retry 5 --retry-delay 3 -A "$UA" -o VACUNAS_COVID.zip "$URL"

echo "[2/3] extrayendo el .7z interno..."
python -c "
import zipfile
zipfile.ZipFile('VACUNAS_COVID.zip').extract('VACUNAS_COVID/vacunas_covid.7z', '.')
print('  ok')
"

echo "[3/3] descomprimiendo (9.91 GB)..."
SEVENZ=""
for p in "/c/Program Files/7-Zip/7z.exe" "/usr/bin/7z" "/usr/local/bin/7z"; do
    [ -f "$p" ] && SEVENZ="$p" && break
done
if [ -z "$SEVENZ" ]; then
    echo "ERROR: se requiere 7-Zip para descomprimir el archivo." >&2
    echo "  Windows: https://www.7-zip.org/" >&2
    echo "  Linux  : sudo apt install p7zip-full" >&2
    exit 1
fi
"$SEVENZ" x "VACUNAS_COVID/vacunas_covid.7z" -o. -y

rm -rf VACUNAS_COVID VACUNAS_COVID.zip

echo
echo "[ok] data/raw/vacunas_covid.csv listo"
ls -la vacunas_covid.csv
echo
echo "Verificación rápida del número de filas:"
echo "  python -c \"print(sum(1 for _ in open('vacunas_covid.csv',encoding='utf-8',errors='replace')))\""
echo "  (debe dar 93,675,828 líneas, incluida la cabecera)"
