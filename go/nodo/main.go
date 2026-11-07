// Nodo de cómputo del clúster ML.
//
// ============================================================================
// PARTE B de la arquitectura — Motor de entrenamiento distribuido
// ----------------------------------------------------------------------------
// Cada nodo:
//  1. Se conecta al coordinador por TCP y anuncia su identidad.
//  2. Recibe la orden de cargar un SHARD del dataset (rango de muestras).
//  3. En cada ronda recibe los pesos globales, calcula el gradiente local
//     sobre su shard —paralelizado internamente con goroutines— y lo
//     devuelve al coordinador.
//
// Doble nivel de paralelismo:
//   - DISTRIBUIDO : N nodos, cada uno con un shard disjunto del dataset.
//   - CONCURRENTE : dentro del nodo, K goroutines dividen el shard y
//     acumulan gradientes parciales en memoria privada.
//
// La reducción interna usa acumuladores locales por goroutine y una sola
// sección crítica al final (sync.Mutex), de modo que el número de
// adquisiciones de lock por ronda es K y no el número de muestras.
//
// Go PURO: solo biblioteca estándar.
//
// Uso:
//
//	go run ./nodo -id 1 -coord localhost:9000
package main

import (
	"bufio"
	"encoding/binary"
	"flag"
	"fmt"
	"math"
	"net"
	"os"
	"runtime"
	"sync"
	"time"

	"pc3/modelo"
	"pc3/protocolo"
)

const tamRegistro = modelo.NumFeatures*4 + 1

// cargarShard lee del dataset binario el rango [inicio, fin) de muestras.
func cargarShard(ruta string, inicio, fin int64) ([]modelo.Muestra, error) {
	f, err := os.Open(ruta)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	if _, err := f.Seek(inicio*tamRegistro, 0); err != nil {
		return nil, err
	}
	n := fin - inicio
	ms := make([]modelo.Muestra, 0, n)

	r := bufio.NewReaderSize(f, 8<<20)
	buf := make([]byte, tamRegistro)
	for i := int64(0); i < n; i++ {
		if _, err := ioReadFull(r, buf); err != nil {
			break
		}
		var m modelo.Muestra
		for j := 0; j < modelo.NumFeatures; j++ {
			m.X[j] = math.Float32frombits(binary.LittleEndian.Uint32(buf[j*4:]))
		}
		m.Y = buf[modelo.NumFeatures*4]
		ms = append(ms, m)
	}
	return ms, nil
}

func ioReadFull(r *bufio.Reader, b []byte) (int, error) {
	n := 0
	for n < len(b) {
		k, err := r.Read(b[n:])
		n += k
		if err != nil {
			return n, err
		}
	}
	return n, nil
}

// gradienteLocal calcula el gradiente sobre el shard usando K goroutines.
// Cada una acumula en su propio buffer y solo al terminar vuelca al global
// bajo mutex: K adquisiciones por ronda, no una por muestra.
func gradienteLocal(w []float64, ms []modelo.Muestra, k int) ([]float64, float64, int64) {
	gradGlobal := make([]float64, modelo.NumFeatures)
	var perdidaGlobal float64
	var mu sync.Mutex
	var wg sync.WaitGroup

	if k > len(ms) {
		k = 1
	}
	if k < 1 {
		k = 1
	}
	tam := len(ms) / k
	resto := len(ms) % k

	ini := 0
	for i := 0; i < k; i++ {
		t := tam
		if i < resto {
			t++
		}
		if t == 0 {
			continue
		}
		lote := ms[ini : ini+t]
		ini += t

		wg.Add(1)
		go func(lote []modelo.Muestra) {
			defer wg.Done()
			// Memoria PRIVADA de esta goroutine: sin sincronización.
			gradLocal := make([]float64, modelo.NumFeatures)
			perdida, _ := modelo.GradienteLote(w, lote, gradLocal)

			peso := float64(len(lote))
			// ---- SECCIÓN CRÍTICA (una sola vez por goroutine) ----
			mu.Lock()
			for j := range gradGlobal {
				gradGlobal[j] += gradLocal[j] * peso
			}
			perdidaGlobal += perdida * peso
			mu.Unlock()
		}(lote)
	}
	wg.Wait()

	inv := 1.0 / float64(len(ms))
	for j := range gradGlobal {
		gradGlobal[j] *= inv
	}
	return gradGlobal, perdidaGlobal * inv, int64(len(ms))
}

func main() {
	id := flag.Int("id", 0, "identificador del nodo")
	coord := flag.String("coord", "localhost:9000", "dirección del coordinador")
	hilos := flag.Int("hilos", runtime.NumCPU(), "goroutines internas por nodo")
	flag.Parse()

	conn, err := net.Dial("tcp", *coord)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[nodo %d] no se pudo conectar a %s: %v\n", *id, *coord, err)
		os.Exit(1)
	}
	defer conn.Close()

	fmt.Printf("[nodo %d] conectado a %s  (hilos internos: %d)\n", *id, *coord, *hilos)

	// Anunciar identidad.
	hola := make([]byte, 8)
	binary.LittleEndian.PutUint64(hola, uint64(*id))
	if err := protocolo.EscribirMensaje(conn, protocolo.MsgHola, hola); err != nil {
		fmt.Fprintln(os.Stderr, "[nodo] error al saludar:", err)
		os.Exit(1)
	}

	var shard []modelo.Muestra
	rondas := 0
	t0 := time.Now()

	for {
		tipo, cuerpo, err := protocolo.LeerMensaje(conn)
		if err != nil {
			fmt.Printf("[nodo %d] conexión cerrada: %v\n", *id, err)
			return
		}

		switch tipo {
		case protocolo.MsgCargar:
			c := protocolo.DesempaquetarCargar(cuerpo)
			tc := time.Now()
			shard, err = cargarShard(c.Ruta, c.Inicio, c.Fin)
			if err != nil {
				fmt.Fprintf(os.Stderr, "[nodo %d] error al cargar shard: %v\n", *id, err)
				os.Exit(1)
			}
			fmt.Printf("[nodo %d] shard cargado: %s muestras [%d, %d) en %.2f s\n",
				*id, conComas(int64(len(shard))), c.Inicio, c.Fin, time.Since(tc).Seconds())

			resp := make([]byte, 8)
			binary.LittleEndian.PutUint64(resp, uint64(len(shard)))
			protocolo.EscribirMensaje(conn, protocolo.MsgListo, resp)

		case protocolo.MsgPesos:
			w := protocolo.DesempaquetarFloats(cuerpo)
			grad, perdida, n := gradienteLocal(w, shard, *hilos)
			rondas++
			cg := protocolo.CuerpoGradiente{Grad: grad, Perdida: perdida, Muestras: n}
			if err := protocolo.EscribirMensaje(conn, protocolo.MsgGradiente, cg.Empaquetar()); err != nil {
				fmt.Fprintln(os.Stderr, "[nodo] error al enviar gradiente:", err)
				return
			}

		case protocolo.MsgEvaluar:
			w := protocolo.DesempaquetarFloats(cuerpo)
			m := modelo.Evaluar(w, shard, 0.5)
			cm := protocolo.CuerpoMetricas{
				VP: m.VP, VN: m.VN, FP: m.FP, FN: m.FN,
				Perdida: m.Perdida * float64(m.N), N: m.N,
			}
			protocolo.EscribirMensaje(conn, protocolo.MsgMetricas, cm.Empaquetar())

		case protocolo.MsgFin:
			fmt.Printf("[nodo %d] fin: %d rondas en %.2f s\n",
				*id, rondas, time.Since(t0).Seconds())
			return
		}
	}
}

func conComas(n int64) string {
	if n < 0 {
		return "-" + conComas(-n)
	}
	s := fmt.Sprintf("%d", n)
	if len(s) <= 3 {
		return s
	}
	var out []byte
	for i, c := range []byte(s) {
		if i > 0 && (len(s)-i)%3 == 0 {
			out = append(out, ',')
		}
		out = append(out, c)
	}
	return string(out)
}
