// Inicialización de la base de datos: crea las colecciones del sistema con
// sus índices y valida que los documentos tengan la forma esperada.
db = db.getSiblingDB('vacunacion');

db.createCollection('predicciones', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['usuario', 'edad', 'probabilidad', 'marca_tiempo'],
      properties: {
        usuario:       { bsonType: 'string',  description: 'usuario autenticado que solicitó la predicción' },
        rol:           { bsonType: 'string'  },
        edad:          { bsonType: ['int', 'long'], minimum: 0, maximum: 120 },
        sexo:          { bsonType: 'string'  },
        departamento:  { bsonType: 'string'  },
        fabricante:    { bsonType: 'string'  },
        probabilidad:  { bsonType: 'double', minimum: 0, maximum: 1 },
        clasificacion: { bsonType: 'string'  },
        nivel_riesgo:  { bsonType: 'string'  },
        latencia_ms:   { bsonType: 'double'  },
        marca_tiempo:  { bsonType: ['int', 'long'] }
      }
    }
  }
});

db.predicciones.createIndex({ marca_tiempo: -1 },                 { name: 'idx_tiempo' });
db.predicciones.createIndex({ departamento: 1, nivel_riesgo: 1 }, { name: 'idx_geo_riesgo' });
db.predicciones.createIndex({ usuario: 1, marca_tiempo: -1 },     { name: 'idx_usuario' });

db.createCollection('metricas_cluster');
db.metricas_cluster.createIndex({ marca_tiempo: -1 }, { name: 'idx_tiempo' });

db.createCollection('modelos');
db.modelos.createIndex({ version: 1 }, { name: 'idx_version', unique: true });

print('Base de datos "vacunacion" inicializada: 3 colecciones, 5 índices.');
