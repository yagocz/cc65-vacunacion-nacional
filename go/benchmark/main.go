// Benchmark de escalabilidad del entrenamiento.
//
// Compara el cálculo del gradiente sobre el dataset completo en modo
// secuencial (1 goroutine) contra el modo concurrente con K goroutines,
// que es exactamente el trabajo que cada nodo del clúster realiza sobre
// su shard. Permite medir el Speedup del motor de entrenamiento aislado
// del costo de red.
//
// Se cronometra SOLO el cálculo del gradiente, con los datos ya en memoria:
// la carga del dataset es una fase que ninguna de las dos versiones
// paraleliza y su inclusión distorsionaría la comparación.
//
// Go PURO: solo biblioteca estándar.
//
// Uso:
//
//	go run ./benchmark -datos ../data/processed/muestras.bin -n 10
package main

import (
	"bufio"
	"encoding/binary"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"runtime"
	"sort"
	"sync"
	"time"

	"pc3/modelo"
)

const tamRegistro = modelo.NumFeatures*4 + 1

func cargar(ruta string, limite int64) ([]modelo.Muestra, error) {
	f, err := os.Open(ruta)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	info, _ := f.Stat()
	n := info.Size() / tamRegistro
	if limite > 0 && limite < n {
		n = limite
	}
	ms := make([]modelo.Muestra, 0, n)
	r := bufio.NewReaderSize(f, 16<<20)
	buf := make([]byte, tamRegistro)
	for i := int64(0); i < n; i++ {
		k := 0
		for k < len(buf) {
			j, err := r.Read(buf[k:])
			k += j
			if err != nil {
				return ms, nil
			}
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

// gradienteSecuencial: una sola goroutine sobre todo el dataset.
func gradienteSecuencial(w []float64, ms []modelo.Muestra) float64 {
	g := make([]float64, modelo.NumFeatures)
	t0 := time.Now()
	modelo.GradienteLote(w, ms, g)
	return float64(time.Since(t0).Microseconds()) / 1000.0
}

// gradienteConcurrente: K goroutines con acumuladores privados y una sola
// sección crítica por goroutine (el mismo patrón que usa cada nodo).
func gradienteConcurrente(w []float64, ms []modelo.Muestra, k int) float64 {
	t0 := time.Now()

	gradGlobal := make([]float64, modelo.NumFeatures)
	var mu sync.Mutex
	var wg sync.WaitGroup

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
			gl := make([]float64, modelo.NumFeatures)
			modelo.GradienteLote(w, lote, gl)
			peso := float64(len(lote))
			mu.Lock()
			for j := range gradGlobal {
				gradGlobal[j] += gl[j] * peso
			}
			mu.Unlock()
		}(lote)
	}
	wg.Wait()
	return float64(time.Since(t0).Microseconds()) / 1000.0
}

func mediaRecortada(xs []float64) float64 {
	if len(xs) <= 2 {
		s := 0.0
		for _, x := range xs {
			s += x
		}
		return s / float64(len(xs))
	}
	c := append([]float64(nil), xs...)
	sort.Float64s(c)
	c = c[1 : len(c)-1]
	s := 0.0
	for _, x := range c {
		s += x
	}
	return s / float64(len(c))
}

func main() {
	datos := flag.String("datos", "../data/processed/muestras.bin", "dataset")
	n := flag.Int("n", 10, "corridas por configuración")
	limite := flag.Int64("limite", 0, "limitar muestras (0 = todas)")
	salida := flag.String("salida", "../docs/benchmark_speedup.json", "resultados JSON")
	flag.Parse()

	fmt.Println("==============================================================")
	fmt.Println("BENCHMARK DE ESCALABILIDAD — cálculo del gradiente")
	fmt.Println("==============================================================")
	fmt.Printf("  SO/arch    : %s/%s   Go %s\n", runtime.GOOS, runtime.GOARCH, runtime.Version())
	fmt.Printf("  NumCPU     : %d   GOMAXPROCS: %d\n", runtime.NumCPU(), runtime.GOMAXPROCS(0))

	fmt.Print("  cargando dataset... ")
	tc := time.Now()
	ms, err := cargar(*datos, *limite)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
	fmt.Printf("%s muestras en %.1f s\n", conComas(int64(len(ms))), time.Since(tc).Seconds())
	fmt.Printf("  corridas   : %d por configuración\n", *n)
	fmt.Println("--------------------------------------------------------------")

	w := make([]float64, modelo.NumFeatures)
	for i := range w {
		w[i] = 0.1
	}

	// Calentamiento: evita medir el primer acceso en frío a la memoria.
	gradienteConcurrente(w, ms, 4)

	fmt.Print("  secuencial    : ")
	sec := make([]float64, 0, *n)
	for i := 0; i < *n; i++ {
		t := gradienteSecuencial(w, ms)
		sec = append(sec, t)
		fmt.Printf("%.0f ", t)
	}
	fmt.Println()
	base := mediaRecortada(sec)

	configs := []int{2, 4, 6, 8, 12, 16}
	type fila struct {
		W          int     `json:"workers"`
		Recortada  float64 `json:"ms_recortada"`
		Speedup    float64 `json:"speedup"`
		Eficiencia float64 `json:"eficiencia"`
	}
	resultados := []fila{}

	for _, k := range configs {
		fmt.Printf("  concurrente K=%-2d: ", k)
		ts := make([]float64, 0, *n)
		for i := 0; i < *n; i++ {
			t := gradienteConcurrente(w, ms, k)
			ts = append(ts, t)
			fmt.Printf("%.0f ", t)
		}
		fmt.Println()
		rec := mediaRecortada(ts)
		resultados = append(resultados, fila{k, rec, base / rec, base / rec / float64(k)})
	}

	fmt.Println()
	fmt.Println("==============================================================")
	fmt.Println("SPEEDUP Y EFICIENCIA  (media recortada de", *n, "corridas)")
	fmt.Println("==============================================================")
	fmt.Printf("  %-12s %14s %12s %12s\n", "config", "tiempo (ms)", "speedup", "eficiencia")
	fmt.Printf("  %-12s %14.2f %12s %12s\n", "secuencial", base, "—", "—")
	for _, r := range resultados {
		fmt.Printf("  K=%-10d %14.2f %11.4fx %11.2f%%\n",
			r.W, r.Recortada, r.Speedup, r.Eficiencia*100)
	}
	fmt.Println("==============================================================")

	if b, err := json.MarshalIndent(map[string]any{
		"muestras":   len(ms),
		"features":   modelo.NumFeatures,
		"corridas":   *n,
		"secuencial": base,
		"resultados": resultados,
		"numcpu":     runtime.NumCPU(),
	}, "", "  "); err == nil {
		os.WriteFile(*salida, b, 0644)
		fmt.Printf("\n  resultados en %s\n", *salida)
	}
}

func conComas(n int64) string {
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
