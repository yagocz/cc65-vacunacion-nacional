# Pruebas de la API con Postman

Colección de pruebas para el entregable PC4 del Trabajo Final de CC65.

El enunciado exige que la API responda en menos de 100 milisegundos y pide
capturas de las pruebas realizadas con Postman. Cada solicitud de esta
colección incluye una aserción automática que verifica ese requisito, de modo
que al ejecutar la colección completa se obtiene la evidencia de cumplimiento
en una sola pantalla.

## Antes de empezar

Levantar el sistema:

```bash
cd <raíz del proyecto>
docker compose up -d
```

Comprobar que responde:

```bash
curl http://localhost:8090/api/salud
```

## Importar la colección

1. Abrir Postman.
2. Botón **Import** (arriba a la izquierda).
3. Arrastrar el archivo `CC65_Vacunacion_API.postman_collection.json`.
4. La colección aparece en la barra lateral como
   **CC65 — API Vacunación Nacional (Caso 7)**.

La variable `base_url` ya apunta a `http://localhost:8090`. Si se levantó el
servicio en otro puerto, editarla en la pestaña **Variables** de la colección.

## Ejecutar

### Opción A — Collection Runner (recomendada para la captura)

1. Clic derecho sobre la colección → **Run collection**.
2. Dejar las doce solicitudes marcadas, en orden.
3. Pulsar **Run CC65 — API Vacunación Nacional**.

El Runner muestra el resultado de cada aserción y el tiempo de respuesta de
cada solicitud. Esa pantalla es la captura más completa para el informe:
evidencia en una sola imagen que las doce solicitudes pasan y que todas
responden por debajo del umbral.

### Opción B — solicitud por solicitud

Ejecutar en orden, empezando por la número 2 (login), que guarda el token
en la variable de colección. Las solicitudes protegidas lo toman de ahí
automáticamente mediante `{{token}}`.

## Qué contiene la colección

| # | Solicitud | Verifica |
|---|---|---|
| 1 | Salud del servicio | 200, modelo, MongoDB y Redis activos |
| 2 | Login | 200, token JWT de tres partes, rol administrador |
| 3 | Login con contraseña incorrecta | 401 |
| 4 | Predecir sin token | 401 |
| 5 | Adolescente fuera de Lima | DESERTARÁ, riesgo ALTO |
| 6 | Adulto mayor en Lima | COMPLETARÁ, riesgo BAJO |
| 7 | Caché, primera llamada | `desde_cache = false` |
| 8 | Caché, segunda llamada | `desde_cache = true` |
| 9 | Edad fuera de rango | 400 con mensaje descriptivo |
| 10 | Lote de 5 perfiles | 5 resultados, procesados en paralelo |
| 11 | Métricas | `cumple_sla_100ms = true`, p99 por debajo de 100 |
| 12 | Especificación OpenAPI | OpenAPI 3.0 con 6 o más rutas |

**Las doce incluyen la aserción de latencia inferior a 100 ms.**

## Sobre las pruebas 7 y 8

Demuestran el funcionamiento de la caché de Redis. La solicitud 7 genera un
perfil con edad y días aleatorios mediante un script de pre-request, de modo
que la caché esté necesariamente vacía; la solicitud 8 repite exactamente el
mismo perfil y debe resolverse desde Redis.

El detalle importa: una versión anterior de estas pruebas consultaba un perfil
fijo que ya había sido cacheado por una prueba previa, con lo que ambas
llamadas devolvían `desde_cache = true`. La prueba pasaba, pero no demostraba
lo que afirmaba verificar. Al aleatorizar el perfil, la secuencia de fallo y
acierto queda realmente comprobada.

## Credenciales de prueba

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `minsa2026` | administrador |
| `analista` | `vacunas2026` | analista |

Son credenciales de demostración, definidas en el código y documentadas como
tales en la especificación Swagger. Un despliegue real las tomaría de MongoDB
con las contraseñas cifradas.

## Alternativa sin interfaz gráfica

El script `scripts/pruebas_api.sh` ejecuta las mismas comprobaciones desde la
terminal y añade una medición de latencia sobre 200 solicitudes consecutivas:

```bash
bash scripts/pruebas_api.sh http://localhost:8090
```

Su salida queda en `docs/salida_pruebas_api.txt`.
