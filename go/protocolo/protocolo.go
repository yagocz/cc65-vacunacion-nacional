// Package protocolo define el formato de mensajes TCP entre el coordinador
// y los nodos de cómputo del clúster.
//
// El enunciado exige que los nodos "comuniquen resultados al coordinador
// (API) mediante TCP interno". Este paquete implementa ese protocolo con
// un marco binario simple y explícito, sin dependencias externas.
//
// Esquema de una ronda de Descenso de Gradiente Distribuido:
//
//	coordinador --[PESOS]--> nodo_i      (broadcast de w en la iteración t)
//	nodo_i: calcula ∇L_i sobre su shard local
//	nodo_i --[GRADIENTE]--> coordinador  (∇L_i + pérdida + nº de muestras)
//	coordinador: w_{t+1} = w_t − η · (Σ n_i·∇L_i / Σ n_i)
//
// Es el patrón Parameter Server: el coordinador posee los pesos globales y
// los nodos solo devuelven gradientes locales. No hay estado compartido
// entre nodos, de modo que la única sincronización es la barrera implícita
// de esperar los N gradientes de cada ronda.
//
// Go PURO: solo biblioteca estándar.
package protocolo

import (
	"encoding/binary"
	"fmt"
	"io"
	"math"
)

// Tipos de mensaje.
const (
	MsgHola      uint8 = 1 // nodo -> coordinador: anuncia su identidad
	MsgCargar    uint8 = 2 // coordinador -> nodo: rango del shard a cargar
	MsgListo     uint8 = 3 // nodo -> coordinador: shard cargado, nº muestras
	MsgPesos     uint8 = 4 // coordinador -> nodo: vector de pesos
	MsgGradiente uint8 = 5 // nodo -> coordinador: gradiente local
	MsgEvaluar   uint8 = 6 // coordinador -> nodo: pedir métricas
	MsgMetricas  uint8 = 7 // nodo -> coordinador: métricas locales
	MsgFin       uint8 = 8 // coordinador -> nodo: terminar
)

// Cabecera de todo mensaje: tipo (1 byte) + longitud del cuerpo (4 bytes).
const tamCabecera = 5

// EscribirMensaje serializa un mensaje con su cabecera.
func EscribirMensaje(w io.Writer, tipo uint8, cuerpo []byte) error {
	cab := make([]byte, tamCabecera)
	cab[0] = tipo
	binary.LittleEndian.PutUint32(cab[1:], uint32(len(cuerpo)))
	if _, err := w.Write(cab); err != nil {
		return err
	}
	if len(cuerpo) > 0 {
		if _, err := w.Write(cuerpo); err != nil {
			return err
		}
	}
	return nil
}

// LeerMensaje lee un mensaje completo.
func LeerMensaje(r io.Reader) (uint8, []byte, error) {
	cab := make([]byte, tamCabecera)
	if _, err := io.ReadFull(r, cab); err != nil {
		return 0, nil, err
	}
	n := binary.LittleEndian.Uint32(cab[1:])
	if n > 64<<20 {
		return 0, nil, fmt.Errorf("cuerpo de mensaje demasiado grande: %d bytes", n)
	}
	cuerpo := make([]byte, n)
	if n > 0 {
		if _, err := io.ReadFull(r, cuerpo); err != nil {
			return 0, nil, err
		}
	}
	return cab[0], cuerpo, nil
}

// EmpaquetarFloats serializa un vector de float64 little-endian.
func EmpaquetarFloats(v []float64) []byte {
	b := make([]byte, 8*len(v))
	for i, x := range v {
		binary.LittleEndian.PutUint64(b[i*8:], math.Float64bits(x))
	}
	return b
}

// DesempaquetarFloats deserializa un vector de float64.
func DesempaquetarFloats(b []byte) []float64 {
	n := len(b) / 8
	v := make([]float64, n)
	for i := 0; i < n; i++ {
		v[i] = math.Float64frombits(binary.LittleEndian.Uint64(b[i*8:]))
	}
	return v
}

// CuerpoCargar describe el shard que debe cargar un nodo.
type CuerpoCargar struct {
	Ruta   string
	Inicio int64 // índice de la primera muestra
	Fin    int64 // índice (exclusivo) de la última
}

func (c CuerpoCargar) Empaquetar() []byte {
	b := make([]byte, 16+len(c.Ruta))
	binary.LittleEndian.PutUint64(b[0:], uint64(c.Inicio))
	binary.LittleEndian.PutUint64(b[8:], uint64(c.Fin))
	copy(b[16:], c.Ruta)
	return b
}

func DesempaquetarCargar(b []byte) CuerpoCargar {
	return CuerpoCargar{
		Inicio: int64(binary.LittleEndian.Uint64(b[0:])),
		Fin:    int64(binary.LittleEndian.Uint64(b[8:])),
		Ruta:   string(b[16:]),
	}
}

// CuerpoGradiente transporta el gradiente local de un nodo.
type CuerpoGradiente struct {
	Grad     []float64
	Perdida  float64
	Muestras int64
}

func (c CuerpoGradiente) Empaquetar() []byte {
	b := make([]byte, 16+8*len(c.Grad))
	binary.LittleEndian.PutUint64(b[0:], math.Float64bits(c.Perdida))
	binary.LittleEndian.PutUint64(b[8:], uint64(c.Muestras))
	for i, x := range c.Grad {
		binary.LittleEndian.PutUint64(b[16+i*8:], math.Float64bits(x))
	}
	return b
}

func DesempaquetarGradiente(b []byte) CuerpoGradiente {
	c := CuerpoGradiente{
		Perdida:  math.Float64frombits(binary.LittleEndian.Uint64(b[0:])),
		Muestras: int64(binary.LittleEndian.Uint64(b[8:])),
	}
	n := (len(b) - 16) / 8
	c.Grad = make([]float64, n)
	for i := 0; i < n; i++ {
		c.Grad[i] = math.Float64frombits(binary.LittleEndian.Uint64(b[16+i*8:]))
	}
	return c
}

// CuerpoMetricas transporta la matriz de confusión local de un nodo.
type CuerpoMetricas struct {
	VP, VN, FP, FN int64
	Perdida        float64
	N              int64
}

func (c CuerpoMetricas) Empaquetar() []byte {
	b := make([]byte, 48)
	binary.LittleEndian.PutUint64(b[0:], uint64(c.VP))
	binary.LittleEndian.PutUint64(b[8:], uint64(c.VN))
	binary.LittleEndian.PutUint64(b[16:], uint64(c.FP))
	binary.LittleEndian.PutUint64(b[24:], uint64(c.FN))
	binary.LittleEndian.PutUint64(b[32:], math.Float64bits(c.Perdida))
	binary.LittleEndian.PutUint64(b[40:], uint64(c.N))
	return b
}

func DesempaquetarMetricas(b []byte) CuerpoMetricas {
	return CuerpoMetricas{
		VP:      int64(binary.LittleEndian.Uint64(b[0:])),
		VN:      int64(binary.LittleEndian.Uint64(b[8:])),
		FP:      int64(binary.LittleEndian.Uint64(b[16:])),
		FN:      int64(binary.LittleEndian.Uint64(b[24:])),
		Perdida: math.Float64frombits(binary.LittleEndian.Uint64(b[32:])),
		N:       int64(binary.LittleEndian.Uint64(b[40:])),
	}
}
