# Clasificación y Seguimiento de la Vacunación Nacional

**CC65 — Programación Concurrente y Distribuida** · Trabajo Final 2026-20
Carrera de Ciencias de la Computación — UPC

| Código | Nombres y apellidos |
|---|---|
| U202215375 | Ricardo Rafael Rivas Carrillo |
| U202412543 | Ernesto Yago Caldas Zapata |
| U202220230 | Andre Angel Chipana Rios |

**Caso 7** · Algoritmo MML: **Regresión Logística Distribuida**

---

## El problema

Perú aplicó más de 93 millones de dosis contra la COVID-19, pero una parte
importante de la población **inició el esquema y lo abandonó**: recibió la
primera o la segunda dosis y nunca volvió por el refuerzo.

> **Pregunta de impacto social que responde el sistema:**
> ¿Qué perfiles de población tienen mayor probabilidad de abandonar el
> esquema de vacunación antes de completar la tercera dosis, y en qué
> departamentos se concentran, para focalizar las campañas de seguimiento?

El sistema entrena un clasificador binario sobre los datos reales del
Registro Nacional de Vacunación y produce, para cada perfil demográfico y
geográfico, la probabilidad de deserción. Esa información permite al MINSA
dirigir brigadas y recordatorios donde el abandono es más probable, en lugar
de repartir el esfuerzo de forma uniforme.

## Dataset

| Campo | Valor |
|---|---|
| Nombre | Vacunación contra COVID-19 |
| Entidad | Ministerio de Salud del Perú (MINSA) |
| Plataforma | Plataforma Nacional de Datos Abiertos |
| Archivo | `vacunas_covid.csv` |
| **Registros** | **93,675,827** |
| Columnas | 14 |
| Tamaño | **9.91 GB** |
| Fecha de corte | 30 de noviembre de 2025 |
| Licencia | Open Data Commons Attribution License |

El enlace de descarga directa está en el Nextcloud institucional del MINSA:
`https://files.minsa.gob.pe/s/J8C75Y55nkFazWF/download`

El CSV original **no se versiona**: se reconstruye con `scripts/descargar.sh`.

## Arquitectura

```
                    ┌──────────────────────────┐
  vacunas_covid.csv │  PARTE A — Cargador      │
     9.91 GB        │  concurrente             │
   93.6M filas  ──> │  Worker Pool + channels  │
                    │  fan-out / fan-in        │
                    └───────────┬──────────────┘
                                │ 30.8M personas etiquetadas
                    ┌───────────▼──────────────┐
                    │  PARTE B — Entrenamiento │
                    │  distribuido             │
                    │                          │
                    │   coordinador (TCP)      │
                    │    │  │  │  │            │
                    │   n1 n2 n3 n4            │  Parameter Server
                    │   (cada nodo: K goroutines)
                    └───────────┬──────────────┘
                                │ modelo entrenado
                    ┌───────────▼──────────────┐
                    │  PARTE C — API REST/WS   │  (PC4)
                    │  PARTE D — SPA           │  (TB2)
                    └──────────────────────────┘
```

## Resultados medidos

Máquina de referencia: **AMD Ryzen 5 5600X** (6 núcleos / 12 hilos),
15.9 GB RAM, Windows 11, Go 1.27.0.

### Carga concurrente (Parte A)

| Métrica | Valor |
|---|---|
| Registros procesados | 93,675,827 |
| Filas malformadas | 0 |
| Tiempo | 7.80 s |
| Rendimiento | 12,013,392 registros/s |
| Throughput | 1,301 MB/s |

### Etiquetado de deserción

| | Personas | % |
|---|---:|---:|
| **Desertó** (y=1, menos de 3 dosis) | 8,339,819 | 27.06% |
| **Completó** (y=0, 3 o más dosis) | 22,476,530 | 72.94% |
| Excluidas por censura a la derecha | 152,534 | 0.49% |
| **Total etiquetado** | **30,816,349** | |

### Entrenamiento distribuido (Parte B)

4 nodos TCP, 300 rondas de descenso de gradiente distribuido:

| Métrica | Valor |
|---|---|
| Pérdida | 0.693147 → **0.329359** |
| Exactitud | **0.8483** |
| Precisión | **0.8124** |
| Exhaustividad | **0.5714** |
| F1 | **0.6709** |
| Tiempo | 75.15 s (250.5 ms/ronda) |

### Escalabilidad

| Workers | Tiempo (ms) | Speedup | Eficiencia |
|---:|---:|---:|---:|
| Secuencial | 2126.36 | — | — |
| 2 | 1070.36 | 1.99× | 99.33% |
| 4 | 548.23 | 3.88× | 96.97% |
| 6 | 383.88 | 5.54× | 92.32% |
| 8 | 307.13 | 6.92× | 86.54% |
| **12** | **236.12** | **9.01×** | 75.04% |
| 16 | 275.50 | 7.72× | 48.24% |

El máximo se alcanza en 12 workers, que coincide con los núcleos lógicos de
la máquina. En 16 el speedup retrocede por sobre-suscripción.

## Cómo ejecutar

```bash
# 1. Descargar el dataset (9.91 GB)
bash scripts/descargar.sh

# 2. Cargar y explorar de forma concurrente
cd go && go run ./cargador -w 12

# 3. Etiquetar deserción y vectorizar
go run ./etiquetado -w 12

# 4. Entrenar en el clúster distribuido (coordinador + 4 nodos)
cd .. && bash scripts/entrenar.sh 4 300 2.0 3

# 5. Benchmark de escalabilidad
cd go && go run ./benchmark -n 10
```

## Estructura

```
go/
  modelo/       núcleo compartido: sigmoide, gradiente, métricas
  protocolo/    mensajería TCP entre coordinador y nodos
  cargador/     Parte A — carga concurrente del CSV
  etiquetado/   reconstrucción de trayectorias y vectorización
  coordinador/  Parte B — Parameter Server (master del clúster)
  nodo/         Parte B — nodo de cómputo del clúster
  benchmark/    medición de speedup y eficiencia
scripts/
  descargar.sh  descarga del dataset del MINSA
  entrenar.sh   lanza el clúster completo
docs/           evidencias de ejecución y resultados
```

## Entregables

- **PC3** (semana 11): caso, limpieza, modelo distribuido, paralelización,
  evidencias, GitHub y Kanban. ✅
- **PC4** (semana 13): clúster de nodos, API REST/WebSocket, MongoDB/Redis.
- **TB2** (semana 14): frontend SPA, integración y evaluación experimental.
