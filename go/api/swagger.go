package main

// especificacionOpenAPI documenta la API en formato OpenAPI 3.0. El enunciado
// pide Swagger de forma explícita; se sirve en /swagger.json y se renderiza
// en /swagger mediante Swagger UI.
const especificacionOpenAPI = `{
  "openapi": "3.0.3",
  "info": {
    "title": "API de Predicción de Deserción Vacunal",
    "description": "Servicio coordinador del clúster de Machine Learning distribuido para el seguimiento de la vacunación nacional. Expone un modelo de Regresión Logística entrenado sobre 30,816,349 registros del Registro Nacional de Vacunación del MINSA (93,675,827 dosis aplicadas).\n\n**Caso 7** — Clasificación y Seguimiento de la Vacunación Nacional.\n\nPregunta de impacto social: ¿qué perfiles de población tienen mayor probabilidad de abandonar el esquema de vacunación antes de completar la tercera dosis?",
    "version": "1.0.0",
    "contact": {
      "name": "Grupo 1 - CC65 Programación Concurrente y Distribuida",
      "url": "https://github.com/yagocz/cc65-vacunacion-nacional"
    },
    "license": {"name": "Open Data Commons Attribution License"}
  },
  "servers": [
    {"url": "http://localhost:8080", "description": "Entorno local"},
    {"url": "http://api:8080", "description": "Red interna de Docker Compose"}
  ],
  "tags": [
    {"name": "Autenticación", "description": "Obtención de tokens JWT"},
    {"name": "Predicción", "description": "Inferencia sobre el modelo entrenado"},
    {"name": "Operación", "description": "Salud y métricas del servicio"}
  ],
  "paths": {
    "/api/salud": {
      "get": {
        "tags": ["Operación"],
        "summary": "Estado del servicio",
        "description": "Verifica que la API esté operativa y reporta el estado de sus dependencias. No requiere autenticación.",
        "responses": {
          "200": {
            "description": "Servicio operativo",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Salud"},
              "example": {"estado": "operativo", "version": "1.0.0-pc4",
                "componentes": {"modelo": true, "mongodb": true, "redis": true}}}}
          }
        }
      }
    },
    "/api/login": {
      "post": {
        "tags": ["Autenticación"],
        "summary": "Obtener token JWT",
        "description": "Autentica al usuario y devuelve un token JWT firmado con HS256, válido durante ocho horas.\n\nUsuarios de prueba:\n- admin / minsa2026 (rol administrador)\n- analista / vacunas2026 (rol analista)",
        "requestBody": {
          "required": true,
          "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/Credenciales"},
            "example": {"usuario": "admin", "contrasena": "minsa2026"}}}
        },
        "responses": {
          "200": {"description": "Autenticación correcta",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TokenJWT"}}}},
          "401": {"description": "Credenciales incorrectas"}
        }
      }
    },
    "/api/predecir": {
      "post": {
        "tags": ["Predicción"],
        "summary": "Predecir la deserción de un perfil",
        "description": "Calcula la probabilidad de que una persona con el perfil indicado abandone el esquema de vacunación antes de completar la tercera dosis.\n\nLa respuesta incluye un nivel de riesgo y una recomendación operativa para la campaña de seguimiento. Las respuestas se almacenan en caché (Redis) durante una hora, de modo que perfiles repetidos se resuelven sin recalcular.\n\n**Latencia objetivo: menos de 100 ms.**",
        "security": [{"BearerAuth": []}],
        "requestBody": {
          "required": true,
          "content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/SolicitudPrediccion"},
            "examples": {
              "adolescente_rural": {
                "summary": "Adolescente fuera de Lima (riesgo alto)",
                "value": {"edad": 15, "sexo": "MASCULINO", "departamento": "CUSCO",
                  "fabricante": "PFIZER", "dias_desde_primera_dosis": 400,
                  "intervalo_entre_dosis": 25, "grupo_riesgo_priorizado": false}
              },
              "adulto_mayor_lima": {
                "summary": "Adulto mayor en Lima con seguimiento sostenido",
                "value": {"edad": 68, "sexo": "FEMENINO", "departamento": "LIMA",
                  "fabricante": "PFIZER", "dias_desde_primera_dosis": 900,
                  "intervalo_entre_dosis": 420, "grupo_riesgo_priorizado": true}
              }
            }}}
        },
        "responses": {
          "200": {"description": "Predicción calculada",
            "content": {"application/json": {
              "schema": {"$ref": "#/components/schemas/RespuestaPrediccion"},
              "example": {"probabilidad_desercion": 0.874213, "clasificacion": "DESERTARÁ",
                "nivel_riesgo": "ALTO",
                "recomendacion": "Contacto telefónico prioritario y visita domiciliaria de brigada móvil.",
                "latencia_ms": 0.21, "desde_cache": false}}}},
          "400": {"description": "Solicitud inválida"},
          "401": {"description": "Token ausente, inválido o expirado"}
        }
      }
    },
    "/api/predecir/lote": {
      "post": {
        "tags": ["Predicción"],
        "summary": "Predecir un lote de perfiles",
        "description": "Procesa hasta 10,000 perfiles de forma concurrente, lanzando una goroutine por elemento. Devuelve la latencia total y la latencia media por elemento.",
        "security": [{"BearerAuth": []}],
        "requestBody": {
          "required": true,
          "content": {"application/json": {
            "schema": {"type": "array", "items": {"$ref": "#/components/schemas/SolicitudPrediccion"}},
            "example": [
              {"edad": 15, "sexo": "MASCULINO", "departamento": "CUSCO", "fabricante": "PFIZER",
               "dias_desde_primera_dosis": 400, "intervalo_entre_dosis": 25, "grupo_riesgo_priorizado": false},
              {"edad": 45, "sexo": "FEMENINO", "departamento": "LIMA", "fabricante": "SINOPHARM",
               "dias_desde_primera_dosis": 800, "intervalo_entre_dosis": 380, "grupo_riesgo_priorizado": true}
            ]}}
        },
        "responses": {
          "200": {"description": "Lote procesado",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RespuestaLote"}}}},
          "400": {"description": "Lote vacío o superior a 10,000 elementos"},
          "401": {"description": "No autorizado"}
        }
      }
    },
    "/api/metricas": {
      "get": {
        "tags": ["Operación"],
        "summary": "Métricas del servicio y del clúster",
        "description": "Devuelve percentiles de latencia, tasa de acierto de la caché, estado de las bases de datos y métricas del modelo. Es la fuente del panel de administración del frontend.",
        "security": [{"BearerAuth": []}],
        "responses": {
          "200": {"description": "Métricas actuales",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Metricas"}}}},
          "401": {"description": "No autorizado"}
        }
      }
    },
    "/ws": {
      "get": {
        "tags": ["Operación"],
        "summary": "Canal WebSocket en tiempo real",
        "description": "Establece una conexión WebSocket (RFC 6455) que emite en JSON cada predicción realizada y un latido cada quince segundos con las métricas del servicio.\n\nEsquemas admitidos: ws:// para conexiones sin cifrar y wss:// para conexiones cifradas.",
        "responses": {
          "101": {"description": "Conexión promovida a WebSocket"},
          "400": {"description": "La solicitud no es una promoción de WebSocket"}
        }
      }
    }
  },
  "components": {
    "securitySchemes": {
      "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT",
        "description": "Token obtenido en /api/login. Enviar como: Authorization: Bearer <token>"}
    },
    "schemas": {
      "Credenciales": {
        "type": "object", "required": ["usuario", "contrasena"],
        "properties": {
          "usuario": {"type": "string", "example": "admin"},
          "contrasena": {"type": "string", "format": "password", "example": "minsa2026"}
        }
      },
      "TokenJWT": {
        "type": "object",
        "properties": {
          "token": {"type": "string", "description": "JWT firmado con HS256"},
          "usuario": {"type": "string"},
          "rol": {"type": "string", "enum": ["administrador", "analista"]},
          "expira_seg": {"type": "integer", "example": 28800}
        }
      },
      "SolicitudPrediccion": {
        "type": "object", "required": ["edad", "sexo", "departamento"],
        "properties": {
          "edad": {"type": "integer", "minimum": 0, "maximum": 120, "example": 15,
            "description": "Edad en años al momento de la primera dosis"},
          "sexo": {"type": "string", "enum": ["MASCULINO", "FEMENINO"], "example": "MASCULINO"},
          "departamento": {"type": "string", "example": "CUSCO",
            "description": "Departamento de residencia según la división del INEI"},
          "fabricante": {"type": "string", "enum": ["PFIZER", "SINOPHARM", "ASTRAZENECA", ""],
            "example": "PFIZER", "description": "Cadena vacía si no está registrado"},
          "dias_desde_primera_dosis": {"type": "integer", "example": 400,
            "description": "Días transcurridos entre la primera dosis y la fecha de corte"},
          "intervalo_entre_dosis": {"type": "integer", "example": 25,
            "description": "Días entre la primera y la última dosis recibida"},
          "grupo_riesgo_priorizado": {"type": "boolean", "example": false,
            "description": "Verdadero si pertenece a un grupo priorizado por comorbilidad u ocupación"}
        }
      },
      "RespuestaPrediccion": {
        "type": "object",
        "properties": {
          "probabilidad_desercion": {"type": "number", "format": "double", "minimum": 0, "maximum": 1},
          "clasificacion": {"type": "string", "enum": ["DESERTARÁ", "COMPLETARÁ"]},
          "nivel_riesgo": {"type": "string", "enum": ["ALTO", "MEDIO", "BAJO"]},
          "recomendacion": {"type": "string", "description": "Acción sugerida para la campaña de seguimiento"},
          "latencia_ms": {"type": "number", "format": "double"},
          "desde_cache": {"type": "boolean", "description": "Verdadero si la respuesta provino de Redis"}
        }
      },
      "RespuestaLote": {
        "type": "object",
        "properties": {
          "total": {"type": "integer"},
          "latencia_ms": {"type": "number"},
          "latencia_por_item": {"type": "number"},
          "resultados": {"type": "array", "items": {"$ref": "#/components/schemas/RespuestaPrediccion"}}
        }
      },
      "Salud": {
        "type": "object",
        "properties": {
          "estado": {"type": "string"}, "version": {"type": "string"},
          "componentes": {"type": "object", "additionalProperties": {"type": "boolean"}}
        }
      },
      "Metricas": {
        "type": "object",
        "properties": {
          "servicio": {"type": "object"},
          "latencia_ms": {"type": "object",
            "properties": {
              "media": {"type": "number"}, "p50": {"type": "number"},
              "p95": {"type": "number"}, "p99": {"type": "number"}, "max": {"type": "number"}}},
          "cumple_sla_100ms": {"type": "boolean"},
          "modelo": {"type": "object"},
          "cache_redis": {"type": "object"},
          "mongodb": {"type": "object"}
        }
      }
    }
  }
}`

// paginaSwagger renderiza la especificación con Swagger UI desde CDN.
const paginaSwagger = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>API de Predicción de Deserción Vacunal — CC65</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  <style>
    body { margin:0; background:#fafafa; }
    .encabezado { background:#1b3a5c; color:#fff; padding:14px 22px; font-family:system-ui,sans-serif; }
    .encabezado h1 { margin:0; font-size:17px; font-weight:600; }
    .encabezado p { margin:4px 0 0; font-size:12.5px; opacity:.85; }
  </style>
</head>
<body>
  <div class="encabezado">
    <h1>API de Predicción de Deserción Vacunal</h1>
    <p>CC65 Programación Concurrente y Distribuida — Caso 7: Clasificación y Seguimiento de la Vacunación Nacional</p>
  </div>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => {
      SwaggerUIBundle({
        url: '/swagger.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        persistAuthorization: true,
        tryItOutEnabled: true
      });
    };
  </script>
</body>
</html>`
