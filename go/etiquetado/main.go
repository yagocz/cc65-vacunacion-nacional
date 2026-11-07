// Construcción del dataset de entrenamiento: etiquetado de deserción
// y vectorización de características.
//
// ============================================================================
// De 93.6M dosis a 30.8M personas etiquetadas y vectorizadas
// ----------------------------------------------------------------------------
// El CSV del MINSA tiene una fila por DOSIS APLICADA, no por persona. Para
// responder la pregunta del caso de uso —¿quién abandona el esquema de
// vacunación?— hay que reconstruir la trayectoria de cada individuo.
//
// Variable objetivo (el caso 7 pregunta por la deserción en 2ª y 3ª dosis):
//
//	y = 1 (DESERTÓ)  : la persona alcanzó 1 o 2 dosis y, transcurridos al
//	                   menos VENTANA días hasta la fecha de corte, no recibió
//	                   la dosis siguiente.
//	y = 0 (COMPLETÓ) : la persona alcanzó 3 o más dosis.
//
// Las personas cuya última dosis es demasiado reciente (menos de VENTANA
// días antes del corte) se EXCLUYEN: todavía están a tiempo de completar el
// esquema y etiquetarlas como desertoras sería censura a la derecha, el
// sesgo clásico en análisis de supervivencia.
//
// Estrategia concurrente: PARTICIÓN POR HASH DEL UUID.
// Cada worker posee un shard disjunto del espacio de UUIDs, de modo que
// todas las dosis de una misma persona caen SIEMPRE en el mismo worker.
// Eso elimina la necesidad de un mapa compartido con lock: cada agregador
// escribe solo en su propio mapa y la consolidación ocurre al final.
//
//	lectores (N bloques) ──> [colas por shard] ──> agregadores (N shards)
//
// Go PURO: solo biblioteca estándar.
//
// Uso:
//
//	go run ./etiquetado -datos ../data/raw/vacunas_covid.csv -w 12
package main

import (
	"bufio"
	"encoding/binary"
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

// ventanaDias es el plazo tras el cual se considera que una persona que no
// recibió la dosis siguiente efectivamente desertó. El esquema nacional
// recomienda 21–28 días entre 1ª y 2ª dosis y unos 5 meses para el refuerzo;
// se toma 180 días como umbral conservador.
const ventanaDias = 180

// persona resume la trayectoria de vacunación de un individuo.
type persona struct {
	dosisMax     uint8
	fechaUltima  int32 // días desde epoch
	fechaPrimera int32
	edad         uint8
	sexo         uint8 // 1=M, 2=F, 0=otro
	depto        uint16
	provincia    uint16
	grupo        uint16
	fabricante   uint8
}

type shard struct {
	personas map[uint32]*persona
}

// catalogo asigna un id numérico estable a cada valor categórico.
type catalogo struct {
	mu  sync.Mutex
	ids map[string]uint16
	inv []string
}

func nuevoCatalogo() *catalogo {
	return &catalogo{ids: make(map[string]uint16), inv: []string{""}}
}

func (c *catalogo) id(s string) uint16 {
	c.mu.Lock()
	defer c.mu.Unlock()
	if v, ok := c.ids[s]; ok {
		return v
	}
	v := uint16(len(c.inv))
	c.ids[s] = v
	c.inv = append(c.inv, s)
	return v
}

func (c *catalogo) nombre(id uint16) string {
	c.mu.Lock()
	defer c.mu.Unlock()
	if int(id) < len(c.inv) {
		return c.inv[id]
	}
	return ""
}

// aDias convierte AAAAMMDD a días desde 1970-01-01 (algoritmo de Howard
// Hinnant, sin usar time para no penalizar el hot path).
func aDias(s string) (int32, bool) {
	if len(s) != 8 {
		return 0, false
	}
	n, ok := aEntero(s)
	if !ok {
		return 0, false
	}
	y, m, d := n/10000, (n/100)%100, n%100
	if m < 1 || m > 12 || d < 1 || d > 31 || y < 2020 || y > 2030 {
		return 0, false
	}
	yy := y
	if m <= 2 {
		yy--
	}
	era := yy / 400
	yoe := yy - era*400
	mp := (m + 9) % 12
	doy := (153*mp+2)/5 + d - 1
	doe := yoe*365 + yoe/4 - yoe/100 + doy
	return int32(era*146097 + doe - 719468), true
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

// hash32 es FNV-1a: determinista y rápido, lo que garantiza que una misma
// persona siempre caiga en el mismo shard.
func hash32(s string) uint32 {
	var h uint32 = 2166136261
	for i := 0; i < len(s); i++ {
		h ^= uint32(s[i])
		h *= 16777619
	}
	return h
}

type bloque struct{ inicio, fin int64 }

func dividir(ruta string, w int) ([]bloque, int64, error) {
	f, err := os.Open(ruta)
	if err != nil {
		return nil, 0, err
	}
	defer f.Close()
	info, _ := f.Stat()
	total := info.Size()

	r := bufio.NewReaderSize(f, 1<<20)
	cab, err := r.ReadString('\n')
	if err != nil {
		return nil, 0, err
	}
	ini := int64(len(cab))

	cortes := []int64{ini}
	tam := (total - ini) / int64(w)
	buf := make([]byte, 1<<16)
	for i := 1; i < w; i++ {
		pos := ini + tam*int64(i)
		if pos >= total {
			break
		}
		f.Seek(pos, 0)
		n, _ := f.Read(buf)
		for j := 0; j < n; j++ {
			if buf[j] == '\n' {
				cortes = append(cortes, pos+int64(j)+1)
				break
			}
		}
	}
	cortes = append(cortes, total)

	var bs []bloque
	for i := 0; i < len(cortes)-1; i++ {
		if cortes[i] < cortes[i+1] {
			bs = append(bs, bloque{cortes[i], cortes[i+1]})
		}
	}
	return bs, total, nil
}

// partirCampos separa por ';' RESPETANDO comillas dobles. El campo
// GRUPO_RIESGO contiene valores como "AFECCIONES CARDIACAS; INSUFICIENCIA
// CARDIACA, ..." donde el ';' es parte del texto. Un parser ingenuo
// descarta esas 17,105 filas; este las conserva.
func partirCampos(l []byte, campos []string) []string {
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
			if len(c) >= 2 && c[0] == '"' && c[len(c)-1] == '"' {
				c = c[1 : len(c)-1]
			}
			campos = append(campos, string(c))
			ini = i + 1
		}
	}
	return campos
}

type registro struct {
	uuid  uint32
	dosis uint8
	fecha int32
	edad  uint8
	sexo  uint8
	depto uint16
	prov  uint16
	grupo uint16
	fab   uint8
}

func main() {
	datos := flag.String("datos", "../data/raw/vacunas_covid.csv", "CSV del MINSA")
	workers := flag.Int("w", runtime.NumCPU(), "workers")
	salida := flag.String("salida", "../data/processed/muestras.bin", "dataset vectorizado")
	flag.Parse()

	fmt.Println("==============================================================")
	fmt.Println("ETIQUETADO Y VECTORIZACIÓN — deserción en 2ª/3ª dosis")
	fmt.Println("==============================================================")
	fmt.Printf("  workers      : %d\n", *workers)
	fmt.Printf("  ventana      : %d días sin dosis siguiente = deserción\n", ventanaDias)
	fmt.Println("--------------------------------------------------------------")

	t0 := time.Now()
	bloques, total, err := dividir(*datos, *workers)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
	fmt.Printf("  archivo      : %.2f GB en %d bloques\n\n", float64(total)/(1<<30), len(bloques))

	catDepto := nuevoCatalogo()
	catProv := nuevoCatalogo()
	catGrupo := nuevoCatalogo()
	catFab := nuevoCatalogo()

	shards := make([]*shard, *workers)
	for i := range shards {
		shards[i] = &shard{personas: make(map[uint32]*persona, 4_000_000)}
	}

	colas := make([]chan []registro, *workers)
	for i := range colas {
		colas[i] = make(chan []registro, 64)
	}

	var wgLect sync.WaitGroup
	var fechaCorte int32
	var muCorte sync.Mutex

	// ---- Lectores: un bloque cada uno, enrutan por hash al shard dueño ----
	for _, b := range bloques {
		wgLect.Add(1)
		go func(b bloque) {
			defer wgLect.Done()
			f, err := os.Open(*datos)
			if err != nil {
				return
			}
			defer f.Close()
			f.Seek(b.inicio, 0)
			r := bufio.NewReaderSize(f, 4<<20)
			restante := b.fin - b.inicio

			lotes := make([][]registro, *workers)
			for i := range lotes {
				lotes[i] = make([]registro, 0, 4096)
			}
			campos := make([]string, 0, numCols)
			var corteLocal int32

			emitir := func(k int) {
				if len(lotes[k]) > 0 {
					colas[k] <- lotes[k]
					lotes[k] = make([]registro, 0, 4096)
				}
			}

			for restante > 0 {
				linea, errL := r.ReadSlice('\n')
				if len(linea) == 0 && errL != nil {
					break
				}
				restante -= int64(len(linea))
				l := linea
				for len(l) > 0 && (l[len(l)-1] == '\n' || l[len(l)-1] == '\r') {
					l = l[:len(l)-1]
				}
				if len(l) == 0 {
					if errL != nil {
						break
					}
					continue
				}
				campos = partirCampos(l, campos)
				if len(campos) != numCols {
					if errL != nil {
						break
					}
					continue
				}

				fv, ok := aDias(campos[colFechaVac])
				if !ok {
					if errL != nil {
						break
					}
					continue
				}
				if fc, ok2 := aDias(campos[0]); ok2 && fc > corteLocal {
					corteLocal = fc
				}
				d, ok := aEntero(campos[colDosis])
				if !ok || d < 1 || d > 9 {
					if errL != nil {
						break
					}
					continue
				}
				e, _ := aEntero(campos[colEdad])
				if e < 0 || e > 120 {
					e = 0
				}
				var sx uint8
				switch campos[colSexo] {
				case "MASCULINO":
					sx = 1
				case "FEMENINO":
					sx = 2
				}

				h := hash32(campos[colUUID])
				k := int(h % uint32(*workers))
				lotes[k] = append(lotes[k], registro{
					uuid:  h,
					dosis: uint8(d),
					fecha: fv,
					edad:  uint8(e),
					sexo:  sx,
					depto: catDepto.id(campos[colDepartamento]),
					prov:  catProv.id(campos[colProvincia]),
					grupo: catGrupo.id(campos[colGrupoRiesgo]),
					fab:   uint8(catFab.id(campos[colFabricante])),
				})
				if len(lotes[k]) >= 4096 {
					emitir(k)
				}
				if errL != nil {
					break
				}
			}
			for k := range lotes {
				emitir(k)
			}
			muCorte.Lock()
			if corteLocal > fechaCorte {
				fechaCorte = corteLocal
			}
			muCorte.Unlock()
		}(b)
	}

	// ---- Agregadores: cada uno dueño exclusivo de su mapa (sin locks) ----
	var wgAgg sync.WaitGroup
	for i := 0; i < *workers; i++ {
		wgAgg.Add(1)
		go func(k int) {
			defer wgAgg.Done()
			m := shards[k].personas
			for lote := range colas[k] {
				for _, r := range lote {
					p, ok := m[r.uuid]
					if !ok {
						m[r.uuid] = &persona{
							dosisMax: r.dosis, fechaUltima: r.fecha,
							fechaPrimera: r.fecha, edad: r.edad, sexo: r.sexo,
							depto: r.depto, provincia: r.prov,
							grupo: r.grupo, fabricante: r.fab,
						}
						continue
					}
					if r.dosis > p.dosisMax {
						p.dosisMax = r.dosis
					}
					if r.fecha > p.fechaUltima {
						p.fechaUltima = r.fecha
					}
					if r.fecha < p.fechaPrimera {
						p.fechaPrimera = r.fecha
						p.edad = r.edad
						p.grupo = r.grupo
						p.fabricante = r.fab
					}
				}
			}
		}(i)
	}

	wgLect.Wait()
	for i := range colas {
		close(colas[i])
	}
	wgAgg.Wait()
	tAgg := time.Since(t0)

	// ---- Identificar categorías de interés para la vectorización ----
	idLima := catDepto.id("LIMA")
	idPfizer := uint16(catFab.id("PFIZER"))
	idSino := uint16(catFab.id("SINOPHARM"))
	idAstra := uint16(catFab.id("ASTRAZENECA"))
	idVacio := uint16(catFab.id(""))

	// Grupos de riesgo priorizados por el MINSA (no etarios genéricos).
	esPriorizado := func(g uint16) bool {
		n := catGrupo.nombre(g)
		if n == "" {
			return false
		}
		// Los grupos etarios empiezan con "PERSONAS DE" o "60 AÑOS";
		// el resto son comorbilidades y personal esencial.
		if len(n) >= 11 && n[:11] == "PERSONAS DE" {
			return false
		}
		if len(n) >= 7 && n[:7] == "60 AÑOS" {
			return false
		}
		return true
	}

	// ---- Etiquetado + vectorización ----
	var totalPersonas, desertaron, completaron, excluidas int64
	porDosisMax := make(map[uint8]int64)

	f, err := os.Create(*salida)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error al crear la salida:", err)
		os.Exit(1)
	}
	bw := bufio.NewWriterSize(f, 8<<20)
	buf := make([]byte, modelo.NumFeatures*4+1)

	for _, s := range shards {
		for _, p := range s.personas {
			totalPersonas++
			porDosisMax[p.dosisMax]++

			if fechaCorte-p.fechaUltima < ventanaDias {
				excluidas++ // censura a la derecha: aún a tiempo
				continue
			}

			var y uint8
			if p.dosisMax < 3 {
				y = 1
				desertaron++
			} else {
				completaron++
			}

			var x [modelo.NumFeatures]float32
			x[0] = 1 // sesgo
			x[1] = float32(p.edad) / 100.0
			if p.sexo == 1 {
				x[2] = 1
			}
			if p.sexo == 2 {
				x[3] = 1
			}
			x[4] = float32(fechaCorte-p.fechaPrimera) / 1800.0
			x[5] = float32(p.fechaUltima-p.fechaPrimera) / 1800.0
			if p.depto != idLima {
				x[6] = 1 // fuera de Lima: proxy de zona no metropolitana
			}
			if esPriorizado(p.grupo) {
				x[7] = 1
			}
			switch uint16(p.fabricante) {
			case idPfizer:
				x[8] = 1
			case idSino:
				x[9] = 1
			case idAstra:
				x[10] = 1
			case idVacio:
				x[11] = 1
			}
			if p.depto == idLima {
				x[12] = 1
			}
			if p.edad < 18 {
				x[13] = 1
			}
			if p.edad >= 60 {
				x[14] = 1
			}

			for j := 0; j < modelo.NumFeatures; j++ {
				binary.LittleEndian.PutUint32(buf[j*4:], math.Float32bits(x[j]))
			}
			buf[modelo.NumFeatures*4] = y
			bw.Write(buf)
		}
	}
	if err := bw.Flush(); err != nil {
		fmt.Fprintln(os.Stderr, "error al volcar la salida:", err)
		os.Exit(1)
	}
	if err := f.Close(); err != nil {
		fmt.Fprintln(os.Stderr, "error al cerrar la salida:", err)
		os.Exit(1)
	}

	// ---------------- Reporte ----------------
	fmt.Println("==============================================================")
	fmt.Println("RESULTADO DEL ETIQUETADO")
	fmt.Println("==============================================================")
	fmt.Printf("  tiempo total        : %.2f s   (agregación %.2f s)\n",
		time.Since(t0).Seconds(), tAgg.Seconds())
	fmt.Printf("  fecha de corte      : día %d desde epoch\n", fechaCorte)
	fmt.Println()
	fmt.Printf("  PERSONAS ÚNICAS     : %s\n", conComas(totalPersonas))
	fmt.Printf("  dosis totales       : 93,675,827\n")
	fmt.Printf("  dosis por persona   : %.2f\n", 93675827.0/float64(totalPersonas))
	fmt.Println()
	fmt.Println("--------------------------------------------------------------")
	fmt.Println("DISTRIBUCIÓN POR DOSIS MÁXIMA ALCANZADA")
	fmt.Println("--------------------------------------------------------------")
	var claves []int
	for k := range porDosisMax {
		claves = append(claves, int(k))
	}
	sort.Ints(claves)
	for _, k := range claves {
		v := porDosisMax[uint8(k)]
		fmt.Printf("  %d dosis : %14s  %6.2f%%\n", k, conComas(v),
			float64(v)/float64(totalPersonas)*100)
	}
	fmt.Println()
	fmt.Println("--------------------------------------------------------------")
	fmt.Println("ETIQUETA BINARIA (variable objetivo)")
	fmt.Println("--------------------------------------------------------------")
	etiquetadas := desertaron + completaron
	fmt.Printf("  DESERTÓ    (y=1)    : %14s  %6.2f%%\n", conComas(desertaron),
		float64(desertaron)/float64(etiquetadas)*100)
	fmt.Printf("  COMPLETÓ   (y=0)    : %14s  %6.2f%%\n", conComas(completaron),
		float64(completaron)/float64(etiquetadas)*100)
	fmt.Printf("  etiquetadas         : %14s\n", conComas(etiquetadas))
	fmt.Printf("  excluidas (censura) : %14s  %6.2f%%\n", conComas(excluidas),
		float64(excluidas)/float64(totalPersonas)*100)
	fmt.Println()
	fmt.Printf("  SUPERA 1,000,000 registros etiquetados: %s\n",
		map[bool]string{true: "SÍ", false: "NO"}[etiquetadas > 1_000_000])

	info, _ := os.Stat(*salida)
	fmt.Println()
	fmt.Printf("  dataset vectorizado : %s  (%.2f MB, %d features)\n",
		*salida, float64(info.Size())/(1<<20), modelo.NumFeatures)
	fmt.Println("==============================================================")
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
