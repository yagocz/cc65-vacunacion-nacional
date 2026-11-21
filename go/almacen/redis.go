package almacen

import (
	"bufio"
	"fmt"
	"net"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Redis es un cliente mínimo del protocolo RESP. Cubre las operaciones que
// el proyecto necesita como caché de predicciones precalculadas: GET, SETEX,
// INCR, DBSIZE y PING.
//
// El enunciado pide Redis para "recomendaciones precalculadas o respuestas
// parciales". En este sistema cumple exactamente esa función: una predicción
// depende solo del perfil del solicitante, de modo que dos consultas con los
// mismos atributos producen el mismo resultado y la segunda puede responderse
// desde la caché sin recalcular.
type Redis struct {
	mu     sync.Mutex
	conn   net.Conn
	lector *bufio.Reader
	dir    string
	activo bool

	Aciertos int64 // hits de caché
	Fallos   int64 // misses
}

func NuevoRedis(dir string) *Redis {
	r := &Redis{dir: dir}
	if err := r.conectar(); err != nil {
		fmt.Printf("[redis] sin conexión a %s (%v); la API operará sin caché\n", dir, err)
		return r
	}
	r.activo = true
	fmt.Printf("[redis] conectado a %s\n", dir)
	return r
}

func (r *Redis) conectar() error {
	c, err := net.DialTimeout("tcp", r.dir, 3*time.Second)
	if err != nil {
		return err
	}
	r.conn = c
	r.lector = bufio.NewReader(c)
	return nil
}

func (r *Redis) Activo() bool { return r != nil && r.activo }

func (r *Redis) Cerrar() {
	if r != nil && r.conn != nil {
		r.conn.Close()
	}
}

// comando serializa una orden en RESP y devuelve la respuesta en texto.
func (r *Redis) comando(partes ...string) (string, error) {
	if !r.activo {
		return "", fmt.Errorf("redis inactivo")
	}
	r.mu.Lock()
	defer r.mu.Unlock()

	var sb strings.Builder
	fmt.Fprintf(&sb, "*%d\r\n", len(partes))
	for _, p := range partes {
		fmt.Fprintf(&sb, "$%d\r\n%s\r\n", len(p), p)
	}

	r.conn.SetDeadline(time.Now().Add(2 * time.Second))
	if _, err := r.conn.Write([]byte(sb.String())); err != nil {
		r.activo = false
		return "", err
	}
	return r.leerRespuesta()
}

func (r *Redis) leerRespuesta() (string, error) {
	linea, err := r.lector.ReadString('\n')
	if err != nil {
		r.activo = false
		return "", err
	}
	linea = strings.TrimRight(linea, "\r\n")
	if linea == "" {
		return "", fmt.Errorf("respuesta vacía")
	}

	switch linea[0] {
	case '+', ':':
		return linea[1:], nil
	case '-':
		return "", fmt.Errorf("error de redis: %s", linea[1:])
	case '$':
		n, _ := strconv.Atoi(linea[1:])
		if n < 0 {
			return "", nil // nil bulk string: la clave no existe
		}
		buf := make([]byte, n+2)
		leido := 0
		for leido < len(buf) {
			k, err := r.lector.Read(buf[leido:])
			leido += k
			if err != nil {
				r.activo = false
				return "", err
			}
		}
		return string(buf[:n]), nil
	default:
		return linea, nil
	}
}

// Obtener lee una clave de la caché y contabiliza el acierto o el fallo.
func (r *Redis) Obtener(clave string) (string, bool) {
	if !r.activo {
		return "", false
	}
	v, err := r.comando("GET", clave)
	if err != nil || v == "" {
		r.mu.Lock()
		r.Fallos++
		r.mu.Unlock()
		return "", false
	}
	r.mu.Lock()
	r.Aciertos++
	r.mu.Unlock()
	return v, true
}

// GuardarTTL escribe una clave con tiempo de expiración en segundos.
func (r *Redis) GuardarTTL(clave, valor string, segundos int) error {
	if !r.activo {
		return nil
	}
	_, err := r.comando("SETEX", clave, strconv.Itoa(segundos), valor)
	return err
}

// Incrementar aumenta un contador atómico.
func (r *Redis) Incrementar(clave string) int64 {
	if !r.activo {
		return 0
	}
	v, err := r.comando("INCR", clave)
	if err != nil {
		return 0
	}
	n, _ := strconv.ParseInt(v, 10, 64)
	return n
}

// Claves devuelve el número de claves almacenadas.
func (r *Redis) Claves() int64 {
	if !r.activo {
		return 0
	}
	v, err := r.comando("DBSIZE")
	if err != nil {
		return 0
	}
	n, _ := strconv.ParseInt(v, 10, 64)
	return n
}

// Estadisticas devuelve los contadores de la caché y su tasa de acierto.
func (r *Redis) Estadisticas() (aciertos, fallos int64, tasa float64) {
	if r == nil {
		return 0, 0, 0
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	total := r.Aciertos + r.Fallos
	if total > 0 {
		tasa = float64(r.Aciertos) / float64(total)
	}
	return r.Aciertos, r.Fallos, tasa
}
