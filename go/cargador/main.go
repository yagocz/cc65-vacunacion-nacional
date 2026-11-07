// Cargador concurrente del Registro Nacional de Vacunación COVID-19 (MINSA).
//
// ============================================================================
// PARTE A de la arquitectura — Cargador de datos concurrente
// ----------------------------------------------------------------------------
// Lee el CSV nominal del MINSA (9.91 GB, 93,675,827 filas) dividiendo el
// archivo en bloques y asignando cada bloque a un worker distinto, en lugar
// de recorrerlo línea por línea de forma secuencial.
//
// Patrón: Worker Pool con fan-out / fan-in sobre channels.
//
//	main ──> [chan bloque] ──> W workers ──> [chan parcial] ──> reductor
//
// Cada worker recibe un rango de bytes del archivo, lo parsea de forma
// independiente y emite un agregado parcial. El reductor consolida los
// parciales. No hay memoria compartida mutable entre workers, de modo que
// la única sincronización necesaria es el cierre de los canales.
//
// Go PURO: solo biblioteca estándar.
//
// Uso:
//
//	go run ./cargador -datos ../data/raw/vacunas_covid.csv -w 12
package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"runtime"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

// Columnas del CSV (separador ';'), según el diccionario oficial del MINSA:
// FECHA_CORTE;UUID;GRUPO_RIESGO;EDAD;SEXO;FECHA_VACUNACION;DOSIS;FABRICANTE;
// DIRESA;DEPARTAMENTO;PROVINCIA;DISTRITO;TIPO_EDAD;CLASIFICACION_VACUNA
const (
	colUUID         = 1
	colGrupoRiesgo  = 2
	colEdad         = 3
	colSexo         = 4
	colFechaVac     = 5
	colDosis        = 6
	colFabricante   = 7
	colDepartamento = 9
	colProvincia    = 10
	colDistrito     = 11
	numCols         = 14
)

// bloque describe un rango de bytes del archivo asignado a un worker.
// Los límites se ajustan a frontera de línea antes de repartirlos, de modo
// que ningún registro queda partido entre dos workers.
type bloque struct {
	id     int
	inicio int64
	fin    int64
}

// parcial es el agregado que produce un worker sobre su bloque.
// Al ser privado de cada goroutine, se construye sin locks.
type parcial struct {
	filas         int64
	malformadas   int64
	porDosis      map[string]int64
	porDepto      map[string]int64
	porFabricante map[string]int64
	porGrupo      map[string]int64
	edadSuma      int64
	edadValidas   int64
	edadMin       int
	edadMax       int
}

func nuevoParcial() *parcial {
	return &parcial{
		porDosis:      make(map[string]int64),
		porDepto:      make(map[string]int64),
		porFabricante: make(map[string]int64),
		porGrupo:      make(map[string]int64),
		edadMin:       1 << 30,
		edadMax:       -1,
	}
}

func (p *parcial) fusionar(o *parcial) {
	p.filas += o.filas
	p.malformadas += o.malformadas
	p.edadSuma += o.edadSuma
	p.edadValidas += o.edadValidas
	if o.edadMin < p.edadMin {
		p.edadMin = o.edadMin
	}
	if o.edadMax > p.edadMax {
		p.edadMax = o.edadMax
	}
	for k, v := range o.porDosis {
		p.porDosis[k] += v
	}
	for k, v := range o.porDepto {
		p.porDepto[k] += v
	}
	for k, v := range o.porFabricante {
		p.porFabricante[k] += v
	}
	for k, v := range o.porGrupo {
		p.porGrupo[k] += v
	}
}

// dividirEnBloques calcula W rangos de bytes alineados a frontera de línea.
// Se abre el archivo y, para cada corte tentativo, se avanza hasta el
// siguiente '\n'. Así se garantiza que cada worker empieza en el inicio de
// un registro y termina al final de otro.
func dividirEnBloques(ruta string, w int) ([]bloque, int64, error) {
	f, err := os.Open(ruta)
	if err != nil {
		return nil, 0, err
	}
	defer f.Close()

	info, err := f.Stat()
	if err != nil {
		return nil, 0, err
	}
	total := info.Size()

	// Saltar la cabecera: el primer bloque arranca después del primer '\n'.
	r := bufio.NewReaderSize(f, 1<<20)
	cab, err := r.ReadString('\n')
	if err != nil {
		return nil, 0, err
	}
	inicioDatos := int64(len(cab))

	cortes := make([]int64, 0, w+1)
	cortes = append(cortes, inicioDatos)

	tam := (total - inicioDatos) / int64(w)
	buf := make([]byte, 1<<16)

	for i := 1; i < w; i++ {
		pos := inicioDatos + tam*int64(i)
		if pos >= total {
			break
		}
		// Avanzar hasta la próxima frontera de línea.
		if _, err := f.Seek(pos, 0); err != nil {
			return nil, 0, err
		}
		n, _ := f.Read(buf)
		desp := -1
		for j := 0; j < n; j++ {
			if buf[j] == '\n' {
				desp = j
				break
			}
		}
		if desp < 0 {
			continue
		}
		cortes = append(cortes, pos+int64(desp)+1)
	}
	cortes = append(cortes, total)

	bs := make([]bloque, 0, len(cortes)-1)
	for i := 0; i < len(cortes)-1; i++ {
		if cortes[i] >= cortes[i+1] {
			continue
		}
		bs = append(bs, bloque{id: i, inicio: cortes[i], fin: cortes[i+1]})
	}
	return bs, total, nil
}

// procesarBloque parsea el rango [b.inicio, b.fin) y devuelve su agregado.
// Es la función que corre dentro de cada goroutine del pool.
func procesarBloque(ruta string, b bloque, leidos *int64) (*parcial, error) {
	f, err := os.Open(ruta)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	if _, err := f.Seek(b.inicio, 0); err != nil {
		return nil, err
	}

	p := nuevoParcial()
	r := bufio.NewReaderSize(f, 4<<20)

	restante := b.fin - b.inicio
	campos := make([]string, 0, numCols)
	var linea []byte

	for restante > 0 {
		linea, err = r.ReadSlice('\n')
		if len(linea) == 0 && err != nil {
			break
		}
		restante -= int64(len(linea))

		// Recortar CR/LF del final.
		l := linea
		for len(l) > 0 && (l[len(l)-1] == '\n' || l[len(l)-1] == '\r') {
			l = l[:len(l)-1]
		}
		if len(l) == 0 {
			if err != nil {
				break
			}
			continue
		}

		// Separar por ';' RESPETANDO comillas dobles. El campo GRUPO_RIESGO
		// contiene valores como "AFECCIONES CARDIACAS; INSUFICIENCIA ..."
		// donde el ';' es parte del texto, no un separador. Un parser
		// ingenuo descarta esas 17,105 filas; este las conserva.
		campos = campos[:0]
		ini := 0
		enComillas := false
		for i := 0; i <= len(l); i++ {
			if i < len(l) && l[i] == '"' {
				enComillas = !enComillas
				continue
			}
			if i == len(l) || (l[i] == ';' && !enComillas) {
				c := l[ini:i]
				// Quitar comillas envolventes si las hay.
				if len(c) >= 2 && c[0] == '"' && c[len(c)-1] == '"' {
					c = c[1 : len(c)-1]
				}
				campos = append(campos, string(c))
				ini = i + 1
			}
		}

		if len(campos) != numCols {
			p.malformadas++
			if err != nil {
				break
			}
			continue
		}

		p.filas++
		p.porDosis[campos[colDosis]]++
		p.porDepto[campos[colDepartamento]]++
		p.porFabricante[campos[colFabricante]]++
		p.porGrupo[campos[colGrupoRiesgo]]++

		if e, ok := aEntero(campos[colEdad]); ok && e >= 0 && e <= 120 {
			p.edadSuma += int64(e)
			p.edadValidas++
			if e < p.edadMin {
				p.edadMin = e
			}
			if e > p.edadMax {
				p.edadMax = e
			}
		}

		if p.filas%500_000 == 0 {
			atomic.AddInt64(leidos, 500_000)
		}

		if err != nil {
			break
		}
	}
	return p, nil
}

func aEntero(s string) (int, bool) {
	if s == "" {
		return 0, false
	}
	n := 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		n = n*10 + int(c-'0')
	}
	return n, true
}

func main() {
	datos := flag.String("datos", "../data/raw/vacunas_covid.csv", "ruta del CSV del MINSA")
	workers := flag.Int("w", runtime.NumCPU(), "número de workers (goroutines)")
	flag.Parse()

	fmt.Println("==============================================================")
	fmt.Println("CARGADOR CONCURRENTE — Registro Nacional de Vacunación COVID-19")
	fmt.Println("==============================================================")
	fmt.Printf("  archivo    : %s\n", *datos)
	fmt.Printf("  workers    : %d\n", *workers)
	fmt.Printf("  GOMAXPROCS : %d  |  NumCPU: %d\n", runtime.GOMAXPROCS(0), runtime.NumCPU())
	fmt.Println("--------------------------------------------------------------")

	inicio := time.Now()

	bloques, total, err := dividirEnBloques(*datos, *workers)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error al dividir el archivo:", err)
		os.Exit(1)
	}
	fmt.Printf("  tamaño     : %.2f GB\n", float64(total)/1024/1024/1024)
	fmt.Printf("  bloques    : %d (alineados a frontera de línea)\n\n", len(bloques))

	// ---- FAN-OUT: repartir bloques por un canal ----
	chBloques := make(chan bloque, len(bloques))
	for _, b := range bloques {
		chBloques <- b
	}
	close(chBloques)

	// ---- Workers: cada uno consume bloques y emite su parcial ----
	chParciales := make(chan *parcial, len(bloques))
	var wg sync.WaitGroup
	var leidos int64

	for i := 0; i < *workers; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for b := range chBloques {
				p, err := procesarBloque(*datos, b, &leidos)
				if err != nil {
					fmt.Fprintf(os.Stderr, "worker %d, bloque %d: %v\n", id, b.id, err)
					continue
				}
				chParciales <- p
			}
		}(i)
	}

	// Cerrar el canal de parciales cuando todos los workers terminen.
	go func() {
		wg.Wait()
		close(chParciales)
	}()

	// ---- FAN-IN: el reductor consolida los parciales ----
	global := nuevoParcial()
	nBloques := 0
	for p := range chParciales {
		global.fusionar(p)
		nBloques++
	}

	transcurrido := time.Since(inicio)

	// ---------------- Reporte ----------------
	fmt.Println("==============================================================")
	fmt.Println("RESULTADO DE LA CARGA")
	fmt.Println("==============================================================")
	fmt.Printf("  bloques procesados : %d\n", nBloques)
	fmt.Printf("  registros leídos   : %s\n", conComas(global.filas))
	fmt.Printf("  filas malformadas  : %s\n", conComas(global.malformadas))
	fmt.Printf("  tiempo             : %.2f s\n", transcurrido.Seconds())
	fmt.Printf("  rendimiento        : %s registros/s\n",
		conComas(int64(float64(global.filas)/transcurrido.Seconds())))
	fmt.Printf("  throughput         : %.1f MB/s\n",
		float64(total)/1024/1024/transcurrido.Seconds())
	fmt.Println()

	fmt.Println("--------------------------------------------------------------")
	fmt.Println("DISTRIBUCIÓN POR DOSIS  (variable objetivo del caso de uso)")
	fmt.Println("--------------------------------------------------------------")
	imprimirTop(global.porDosis, global.filas, 10)

	fmt.Println("--------------------------------------------------------------")
	fmt.Println("TOP 10 DEPARTAMENTOS")
	fmt.Println("--------------------------------------------------------------")
	imprimirTop(global.porDepto, global.filas, 10)

	fmt.Println("--------------------------------------------------------------")
	fmt.Println("FABRICANTES")
	fmt.Println("--------------------------------------------------------------")
	imprimirTop(global.porFabricante, global.filas, 8)

	fmt.Println("--------------------------------------------------------------")
	fmt.Println("TOP 10 GRUPOS DE RIESGO")
	fmt.Println("--------------------------------------------------------------")
	imprimirTop(global.porGrupo, global.filas, 10)

	if global.edadValidas > 0 {
		fmt.Println("--------------------------------------------------------------")
		fmt.Println("EDAD")
		fmt.Println("--------------------------------------------------------------")
		fmt.Printf("  válidas : %s  (%.2f%%)\n", conComas(global.edadValidas),
			float64(global.edadValidas)/float64(global.filas)*100)
		fmt.Printf("  rango   : %d – %d años\n", global.edadMin, global.edadMax)
		fmt.Printf("  media   : %.2f años\n",
			float64(global.edadSuma)/float64(global.edadValidas))
	}
	fmt.Println("==============================================================")
}

func imprimirTop(m map[string]int64, total int64, n int) {
	type par struct {
		k string
		v int64
	}
	ps := make([]par, 0, len(m))
	for k, v := range m {
		ps = append(ps, par{k, v})
	}
	sort.Slice(ps, func(i, j int) bool { return ps[i].v > ps[j].v })
	if n > len(ps) {
		n = len(ps)
	}
	for i := 0; i < n; i++ {
		etiqueta := ps[i].k
		if etiqueta == "" {
			etiqueta = "(vacío)"
		}
		fmt.Printf("  %-34s %14s  %6.2f%%\n", etiqueta, conComas(ps[i].v),
			float64(ps[i].v)/float64(total)*100)
	}
	if len(ps) > n {
		fmt.Printf("  ... y %d categorías más\n", len(ps)-n)
	}
	fmt.Println()
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
