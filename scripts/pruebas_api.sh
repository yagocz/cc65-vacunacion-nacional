#!/usr/bin/env bash
# Pruebas funcionales y de latencia de la API coordinadora.
#
# Equivale a la colección de Postman que pide el enunciado, pero ejecutable
# desde la terminal, de modo que las cifras del informe sean reproducibles.
#
# Uso:
#   bash scripts/pruebas_api.sh [URL_BASE]
set -u

BASE="${1:-http://localhost:8090}"
OUT="docs/salida_pruebas_api.txt"
mkdir -p docs

exec > >(tee "$OUT") 2>&1

echo "=============================================================="
echo "PRUEBAS DE LA API COORDINADORA"
echo "=============================================================="
echo "  base   : $BASE"
echo "  fecha  : $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================================="
echo

# --------------------------------------------------------------------------
echo "### 1. GET /api/salud — estado del servicio (sin autenticación)"
curl -s -m 10 -w "\n  → HTTP %{http_code} | %{time_total}s\n" "$BASE/api/salud"
echo

# --------------------------------------------------------------------------
echo "### 2. POST /api/login — autenticación y emisión de JWT"
RESP=$(curl -s -m 10 -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d '{"usuario":"admin","contrasena":"minsa2026"}')
echo "$RESP" | head -c 400
echo
TOKEN=$(echo "$RESP" | python -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
if [ -z "$TOKEN" ]; then
    echo "  ERROR: no se obtuvo token; se detienen las pruebas."
    exit 1
fi
echo "  → token obtenido (${#TOKEN} caracteres)"
echo

# --------------------------------------------------------------------------
echo "### 3. POST /api/login — credenciales incorrectas (debe dar 401)"
curl -s -m 10 -o /dev/null -w "  → HTTP %{http_code}\n" -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d '{"usuario":"admin","contrasena":"incorrecta"}'
echo

# --------------------------------------------------------------------------
echo "### 4. POST /api/predecir sin token (debe dar 401)"
curl -s -m 10 -o /dev/null -w "  → HTTP %{http_code}\n" -X POST "$BASE/api/predecir" \
  -H "Content-Type: application/json" -d '{"edad":15}'
echo

# --------------------------------------------------------------------------
echo "### 5. POST /api/predecir — adolescente fuera de Lima"
echo "    Perfil: 15 años, masculino, CUSCO, Pfizer, intervalo corto"
curl -s -m 10 -X POST "$BASE/api/predecir" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"edad":15,"sexo":"MASCULINO","departamento":"CUSCO","fabricante":"PFIZER","dias_desde_primera_dosis":400,"intervalo_entre_dosis":25,"grupo_riesgo_priorizado":false}' \
  -w "\n  → HTTP %{http_code} | tiempo total %{time_total}s\n"
echo

# --------------------------------------------------------------------------
echo "### 6. POST /api/predecir — adulto mayor en Lima con seguimiento sostenido"
echo "    Perfil: 68 años, femenino, LIMA, Pfizer, intervalo largo"
curl -s -m 10 -X POST "$BASE/api/predecir" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"edad":68,"sexo":"FEMENINO","departamento":"LIMA","fabricante":"PFIZER","dias_desde_primera_dosis":900,"intervalo_entre_dosis":420,"grupo_riesgo_priorizado":true}' \
  -w "\n  → HTTP %{http_code} | tiempo total %{time_total}s\n"
echo

# --------------------------------------------------------------------------
echo "### 7. Caché de Redis: fallo y acierto sobre un perfil nuevo"
echo "    (la primera llamada calcula; la segunda debe venir de la caché)"
EDAD_UNICA=$(( 20 + RANDOM % 50 ))
DIAS_UNICO=$(( 500 + RANDOM % 300 ))
PERFIL="{\"edad\":$EDAD_UNICA,\"sexo\":\"FEMENINO\",\"departamento\":\"TACNA\",\"fabricante\":\"MODERNA\",\"dias_desde_primera_dosis\":$DIAS_UNICO,\"intervalo_entre_dosis\":45}"
for i in 1 2; do
  printf "    llamada %d: " "$i"
  curl -s -m 10 -X POST "$BASE/api/predecir"     -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN"     -d "$PERFIL"     | python -c "import sys,json; d=json.load(sys.stdin); print(f\"desde_cache={d['desde_cache']}  latencia={d['latencia_ms']} ms\")" 2>/dev/null
  sleep 2
done
echo

# --------------------------------------------------------------------------
echo "### 8. Validación de entrada: edad fuera de rango (debe dar 400)"
curl -s -m 10 -X POST "$BASE/api/predecir" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"edad":200,"sexo":"MASCULINO","departamento":"LIMA"}' \
  -w "\n  → HTTP %{http_code}\n"
echo

# --------------------------------------------------------------------------
echo "### 9. POST /api/predecir/lote — 5 perfiles en paralelo"
curl -s -m 20 -X POST "$BASE/api/predecir/lote" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '[
    {"edad":15,"sexo":"MASCULINO","departamento":"CUSCO","fabricante":"PFIZER","dias_desde_primera_dosis":400,"intervalo_entre_dosis":25},
    {"edad":45,"sexo":"FEMENINO","departamento":"LIMA","fabricante":"SINOPHARM","dias_desde_primera_dosis":800,"intervalo_entre_dosis":380,"grupo_riesgo_priorizado":true},
    {"edad":70,"sexo":"MASCULINO","departamento":"PUNO","fabricante":"","dias_desde_primera_dosis":600,"intervalo_entre_dosis":30},
    {"edad":8,"sexo":"FEMENINO","departamento":"LORETO","fabricante":"PFIZER","dias_desde_primera_dosis":300,"intervalo_entre_dosis":21},
    {"edad":32,"sexo":"MASCULINO","departamento":"AREQUIPA","fabricante":"ASTRAZENECA","dias_desde_primera_dosis":1000,"intervalo_entre_dosis":500}
  ]' | python -c "
import sys, json
d = json.load(sys.stdin)
print(f\"  total: {d['total']} | latencia {d['latencia_ms']} ms | por item {d['latencia_por_item']} ms\")
for i, r in enumerate(d['resultados'], 1):
    print(f\"    {i}. p={r['probabilidad_desercion']:.4f}  {r['clasificacion']:<11} riesgo {r['nivel_riesgo']}\")
" 2>/dev/null
echo

# --------------------------------------------------------------------------
echo "### 10. Prueba de latencia: 200 solicitudes consecutivas"
echo "    Requisito del enunciado: la API debe responder en menos de 100 ms"
TMP=$(mktemp)
for i in $(seq 1 200); do
  curl -s -m 10 -o /dev/null -w "%{time_total}\n" -X POST "$BASE/api/predecir" \
    -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
    -d "{\"edad\":$((20 + i % 60)),\"sexo\":\"MASCULINO\",\"departamento\":\"LIMA\",\"fabricante\":\"PFIZER\",\"dias_desde_primera_dosis\":$((300 + i)),\"intervalo_entre_dosis\":$((20 + i % 400))}" \
    >> "$TMP"
done
python - "$TMP" <<'PYEOF'
import sys
ts = sorted(float(l) * 1000 for l in open(sys.argv[1]) if l.strip())
n = len(ts)
print(f"    solicitudes : {n}")
print(f"    media       : {sum(ts)/n:.2f} ms")
print(f"    mínimo      : {ts[0]:.2f} ms")
print(f"    p50         : {ts[n//2]:.2f} ms")
print(f"    p95         : {ts[int(n*0.95)]:.2f} ms")
print(f"    p99         : {ts[min(int(n*0.99), n-1)]:.2f} ms")
print(f"    máximo      : {ts[-1]:.2f} ms")
print()
p99 = ts[min(int(n*0.99), n-1)]
print(f"    CUMPLE EL REQUISITO (p99 < 100 ms): {'SÍ' if p99 < 100 else 'NO'}")
PYEOF
rm -f "$TMP"
echo

# --------------------------------------------------------------------------
echo "### 11. GET /api/metricas — métricas del servicio"
curl -s -m 10 "$BASE/api/metricas" -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool 2>/dev/null | head -45
echo

echo "=============================================================="
echo "FIN DE LAS PRUEBAS"
echo "=============================================================="
