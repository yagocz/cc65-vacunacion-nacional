#!/usr/bin/env bash
# Lanza el clúster de entrenamiento distribuido: 1 coordinador + N nodos.
#
# Uso:
#   bash scripts/entrenar.sh [N_NODOS] [RONDAS] [LR] [HILOS_POR_NODO]
#
# Cada nodo es un proceso independiente que se conecta al coordinador por
# TCP, recibe un shard disjunto del dataset y participa en el descenso de
# gradiente distribuido.
set -e

NODOS=${1:-4}
RONDAS=${2:-50}
LR=${3:-0.5}
HILOS=${4:-3}
PUERTO=${PUERTO:-9000}

cd "$(dirname "$0")/../go"
export PATH="/c/Program Files/Go/bin:$PATH"

echo "=== compilando ==="
go build -o ../bin/coordinador.exe ./coordinador
go build -o ../bin/nodo.exe ./nodo

echo "=== lanzando coordinador (puerto $PUERTO) ==="
../bin/coordinador.exe -nodos "$NODOS" -rondas "$RONDAS" -lr "$LR" -puerto "$PUERTO" &
COORD=$!

sleep 2

echo "=== lanzando $NODOS nodos ($HILOS goroutines cada uno) ==="
PIDS=()
for i in $(seq 1 "$NODOS"); do
    ../bin/nodo.exe -id "$i" -coord "localhost:$PUERTO" -hilos "$HILOS" &
    PIDS+=($!)
done

wait $COORD
for p in "${PIDS[@]}"; do wait "$p" 2>/dev/null || true; done
echo "=== clúster finalizado ==="
