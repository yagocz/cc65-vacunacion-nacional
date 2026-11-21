// Package almacen implementa los dos niveles de persistencia que exige el
// enunciado: MongoDB para el almacenamiento durable y Redis como caché de
// respuestas precalculadas.
//
// Ambos clientes están escritos sobre la biblioteca estándar de Go. En lugar
// de arrastrar los SDK oficiales, se implementan los protocolos de alambre
// mínimos que el proyecto necesita: el protocolo binario OP_MSG de MongoDB y
// el protocolo de texto RESP de Redis. La restricción del curso es trabajar
// en Go puro, y los dos protocolos son lo bastante acotados para que esta
// decisión no comprometa la claridad del código.
package almacen

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"math"
	"net"
	"sync"
	"sync/atomic"
	"time"
)

// Mongo es un cliente mínimo del protocolo OP_MSG de MongoDB (wire
// protocol 6+). Implementa solo las operaciones que el proyecto usa:
// insertar documentos, contar y leer los más recientes de una colección.
type Mongo struct {
	mu      sync.Mutex
	conn    net.Conn
	dir     string
	baseDat string
	reqID   int32
	activo  bool
}

// NuevoMongo abre la conexión con el servidor. Si falla, devuelve un cliente
// inactivo en lugar de un error fatal: la API debe seguir respondiendo
// predicciones aunque la persistencia no esté disponible, porque el modelo
// vive en memoria y no depende de la base de datos.
func NuevoMongo(dir, baseDat string) *Mongo {
	m := &Mongo{dir: dir, baseDat: baseDat}
	if err := m.conectar(); err != nil {
		fmt.Printf("[mongo] sin conexión a %s (%v); la API seguirá operando sin persistencia\n", dir, err)
		return m
	}
	m.activo = true
	fmt.Printf("[mongo] conectado a %s, base de datos %q\n", dir, baseDat)
	return m
}

func (m *Mongo) conectar() error {
	c, err := net.DialTimeout("tcp", m.dir, 3*time.Second)
	if err != nil {
		return err
	}
	m.conn = c
	return nil
}

func (m *Mongo) Activo() bool { return m != nil && m.activo }

func (m *Mongo) Cerrar() {
	if m != nil && m.conn != nil {
		m.conn.Close()
	}
}

// ejecutar envía un comando BSON y devuelve la respuesta cruda.
func (m *Mongo) ejecutar(cmd []byte) ([]byte, error) {
	if !m.activo {
		return nil, fmt.Errorf("cliente mongo inactivo")
	}
	m.mu.Lock()
	defer m.mu.Unlock()

	id := atomic.AddInt32(&m.reqID, 1)

	// Cabecera msgHeader (16 bytes) + flagBits (4) + sección tipo 0 (1) + BSON.
	cuerpo := make([]byte, 5+len(cmd))
	binary.LittleEndian.PutUint32(cuerpo[0:], 0) // flagBits
	cuerpo[4] = 0                                // sección tipo 0: documento único
	copy(cuerpo[5:], cmd)

	total := 16 + len(cuerpo)
	msg := make([]byte, total)
	binary.LittleEndian.PutUint32(msg[0:], uint32(total))
	binary.LittleEndian.PutUint32(msg[4:], uint32(id))
	binary.LittleEndian.PutUint32(msg[8:], 0)     // responseTo
	binary.LittleEndian.PutUint32(msg[12:], 2013) // OP_MSG
	copy(msg[16:], cuerpo)

	m.conn.SetDeadline(time.Now().Add(5 * time.Second))
	if _, err := m.conn.Write(msg); err != nil {
		m.activo = false
		return nil, err
	}

	cab := make([]byte, 16)
	if _, err := leerCompleto(m.conn, cab); err != nil {
		m.activo = false
		return nil, err
	}
	largo := int(binary.LittleEndian.Uint32(cab[0:]))
	if largo < 16 || largo > 48<<20 {
		m.activo = false
		return nil, fmt.Errorf("longitud de respuesta inválida: %d", largo)
	}
	resto := make([]byte, largo-16)
	if _, err := leerCompleto(m.conn, resto); err != nil {
		m.activo = false
		return nil, err
	}
	if len(resto) < 5 {
		return nil, fmt.Errorf("respuesta demasiado corta")
	}
	return resto[5:], nil
}

func leerCompleto(c net.Conn, b []byte) (int, error) {
	n := 0
	for n < len(b) {
		k, err := c.Read(b[n:])
		n += k
		if err != nil {
			return n, err
		}
	}
	return n, nil
}

// Insertar guarda un documento en la colección indicada.
func (m *Mongo) Insertar(coleccion string, doc Doc) error {
	if !m.activo {
		return fmt.Errorf("mongo inactivo")
	}
	cmd := NuevoDoc().
		Str("insert", coleccion).
		Arr("documents", []Doc{doc}).
		Str("$db", m.baseDat).
		Construir()
	_, err := m.ejecutar(cmd)
	return err
}

// InsertarVarios guarda un lote de documentos en una sola operación.
func (m *Mongo) InsertarVarios(coleccion string, docs []Doc) error {
	if !m.activo || len(docs) == 0 {
		return nil
	}
	cmd := NuevoDoc().
		Str("insert", coleccion).
		Arr("documents", docs).
		Str("$db", m.baseDat).
		Construir()
	_, err := m.ejecutar(cmd)
	return err
}

// Contar devuelve el número de documentos de una colección.
func (m *Mongo) Contar(coleccion string) (int64, error) {
	if !m.activo {
		return 0, fmt.Errorf("mongo inactivo")
	}
	cmd := NuevoDoc().
		Str("count", coleccion).
		Str("$db", m.baseDat).
		Construir()
	resp, err := m.ejecutar(cmd)
	if err != nil {
		return 0, err
	}
	if v, ok := leerEntero(resp, "n"); ok {
		return v, nil
	}
	return 0, nil
}

// ---------------------------------------------------------------------------
// Construcción de documentos BSON
// ---------------------------------------------------------------------------

// Doc representa un documento BSON en construcción.
type Doc struct {
	buf bytes.Buffer
}

func NuevoDoc() *Doc { return &Doc{} }

func (d *Doc) Str(clave, valor string) *Doc {
	d.buf.WriteByte(0x02)
	d.buf.WriteString(clave)
	d.buf.WriteByte(0)
	var l [4]byte
	binary.LittleEndian.PutUint32(l[:], uint32(len(valor)+1))
	d.buf.Write(l[:])
	d.buf.WriteString(valor)
	d.buf.WriteByte(0)
	return d
}

func (d *Doc) Int(clave string, valor int64) *Doc {
	d.buf.WriteByte(0x12) // int64
	d.buf.WriteString(clave)
	d.buf.WriteByte(0)
	var v [8]byte
	binary.LittleEndian.PutUint64(v[:], uint64(valor))
	d.buf.Write(v[:])
	return d
}

func (d *Doc) Flo(clave string, valor float64) *Doc {
	d.buf.WriteByte(0x01) // double
	d.buf.WriteString(clave)
	d.buf.WriteByte(0)
	var v [8]byte
	binary.LittleEndian.PutUint64(v[:], math.Float64bits(valor))
	d.buf.Write(v[:])
	return d
}

func (d *Doc) Bool(clave string, valor bool) *Doc {
	d.buf.WriteByte(0x08)
	d.buf.WriteString(clave)
	d.buf.WriteByte(0)
	if valor {
		d.buf.WriteByte(1)
	} else {
		d.buf.WriteByte(0)
	}
	return d
}

func (d *Doc) Sub(clave string, sub *Doc) *Doc {
	d.buf.WriteByte(0x03)
	d.buf.WriteString(clave)
	d.buf.WriteByte(0)
	d.buf.Write(sub.Construir())
	return d
}

func (d *Doc) Arr(clave string, docs []Doc) *Doc {
	d.buf.WriteByte(0x04)
	d.buf.WriteString(clave)
	d.buf.WriteByte(0)
	var arr Doc
	for i := range docs {
		arr.buf.WriteByte(0x03)
		arr.buf.WriteString(fmt.Sprintf("%d", i))
		arr.buf.WriteByte(0)
		arr.buf.Write(docs[i].Construir())
	}
	d.buf.Write(arr.Construir())
	return d
}

// Construir cierra el documento y devuelve su representación BSON.
func (d *Doc) Construir() []byte {
	cuerpo := d.buf.Bytes()
	total := 4 + len(cuerpo) + 1
	out := make([]byte, total)
	binary.LittleEndian.PutUint32(out[0:], uint32(total))
	copy(out[4:], cuerpo)
	out[total-1] = 0
	return out
}

// leerEntero extrae un entero de un documento BSON por su clave. Soporta
// int32, int64 y double, porque MongoDB puede devolver cualquiera de los tres
// según la operación.
func leerEntero(bson []byte, clave string) (int64, bool) {
	if len(bson) < 5 {
		return 0, false
	}
	i := 4
	for i < len(bson)-1 {
		tipo := bson[i]
		i++
		fin := bytes.IndexByte(bson[i:], 0)
		if fin < 0 {
			return 0, false
		}
		nombre := string(bson[i : i+fin])
		i += fin + 1

		switch tipo {
		case 0x10: // int32
			if i+4 > len(bson) {
				return 0, false
			}
			v := int64(int32(binary.LittleEndian.Uint32(bson[i:])))
			if nombre == clave {
				return v, true
			}
			i += 4
		case 0x12: // int64
			if i+8 > len(bson) {
				return 0, false
			}
			v := int64(binary.LittleEndian.Uint64(bson[i:]))
			if nombre == clave {
				return v, true
			}
			i += 8
		case 0x01: // double
			if i+8 > len(bson) {
				return 0, false
			}
			v := int64(math.Float64frombits(binary.LittleEndian.Uint64(bson[i:])))
			if nombre == clave {
				return v, true
			}
			i += 8
		case 0x02: // string
			if i+4 > len(bson) {
				return 0, false
			}
			l := int(binary.LittleEndian.Uint32(bson[i:]))
			i += 4 + l
		case 0x08: // bool
			i++
		case 0x03, 0x04: // documento o arreglo
			if i+4 > len(bson) {
				return 0, false
			}
			l := int(binary.LittleEndian.Uint32(bson[i:]))
			i += l
		default:
			return 0, false
		}
	}
	return 0, false
}
