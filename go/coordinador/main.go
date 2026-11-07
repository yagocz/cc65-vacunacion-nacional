// Coordinador del clúster ML — Descenso de Gradiente Distribuido.
//
// ============================================================================
// PARTE B de la arquitectura — Motor de entrenamiento distribuido (master)
// ----------------------------------------------------------------------------
// Implementa el patrón Parameter Server sobre TCP:
//
//  1. Escucha conexiones de N nodos de cómputo.
//  2. Reparte el dataset en N shards disjuntos y ordena a cada nodo
//     cargar el suyo.
//  3. En cada ronda t:
//     a) difunde el vector de pesos w_t a los N nodos (broadcast);
//     b) espera los N gradientes locales (barrera de sincronización);
//     c) agrega con media ponderada por número de muestras;
//     d) actualiza  w_{t+1} = w_t − η · ∇L
//  4. Al terminar, pide métricas a los nodos y consolida la matriz de
//     confusión global.
//
// La agregación es el único punto de sincronización: los nodos no comparten
// estado entre sí. Esto corresponde exactamente al esquema que el enunciado
// describe para Logistic Regression Distribuida ("cada nodo procesa un lote,
// calcula el gradiente del error local y transmite los gradientes vía TCP al
// coordinador para actualizar los pesos del modelo").
//
// Go PURO: solo biblioteca estándar.
//
// Uso:
//
//	go run ./coordinador -nodos 4 -rondas 50 -lr 0.5
package main

import (
	"encoding/binary"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"net"
	"os"
	"sync"
	"time"

	"pc3/modelo"
	"pc3/protocolo"
)

const tamRegistro = modelo.NumFeatures*4 + 1

type nodoConn struct {
	id       int
	conn     net.Conn
	muestras int64
}

type registroRonda struct {
	Ronda    int     `json:"ronda"`
	Perdida  float64 `json:"perdida"`
	NormGrad float64 `json:"norma_gradiente"`
	MS       float64 `json:"ms"`
}

func main() {
	datos := flag.String("datos", "../data/processed/muestras.bin", "dataset vectorizado")
	puerto := flag.Int("puerto", 9000, "puerto TCP del coordinador")
	nNodos := flag.Int("nodos", 4, "número de nodos esperados")
	rondas := flag.Int("rondas", 50, "rondas de descenso de gradiente")
	lr := flag.Float64("lr", 0.5, "tasa de aprendizaje")
	l2 := flag.Float64("l2", 1e-6, "regularización L2")
	histJSON := flag.String("hist", "../docs/historial_entrenamiento.json", "historial de pérdida")
	flag.Parse()

	info, err := os.Stat(*datos)
	if err != nil {
		fmt.Fprintln(os.Stderr, "no se encuentra el dataset:", err)
		os.Exit(1)
	}
	totalMuestras := info.Size() / tamRegistro

	fmt.Println("==============================================================")
	fmt.Println("COORDINADOR — Regresión Logística Distribuida (Parameter Server)")
	fmt.Println("==============================================================")
	fmt.Printf("  dataset   : %s\n", *datos)
	fmt.Printf("  muestras  : %s  (%.2f GB)\n", conComas(totalMuestras),
		float64(info.Size())/(1<<30))
	fmt.Printf("  features  : %d\n", modelo.NumFeatures)
	fmt.Printf("  nodos     : %d\n", *nNodos)
	fmt.Printf("  rondas    : %d   |  lr: %.3f  |  L2: %g\n", *rondas, *lr, *l2)
	fmt.Println("--------------------------------------------------------------")

	ln, err := net.Listen("tcp", fmt.Sprintf(":%d", *puerto))
	if err != nil {
		fmt.Fprintln(os.Stderr, "no se pudo escuchar:", err)
		os.Exit(1)
	}
	defer ln.Close()
	fmt.Printf("  escuchando en :%d — esperando %d nodos...\n\n", *puerto, *nNodos)

	// ---- Aceptar los N nodos ----
	nodos := make([]*nodoConn, 0, *nNodos)
	for len(nodos) < *nNodos {
		c, err := ln.Accept()
		if err != nil {
			fmt.Fprintln(os.Stderr, "error al aceptar:", err)
			continue
		}
		tipo, cuerpo, err := protocolo.LeerMensaje(c)
		if err != nil || tipo != protocolo.MsgHola {
			c.Close()
			continue
		}
		id := int(binary.LittleEndian.Uint64(cuerpo))
		nodos = append(nodos, &nodoConn{id: id, conn: c})
		fmt.Printf("  [+] nodo %d conectado desde %s  (%d/%d)\n",
			id, c.RemoteAddr(), len(nodos), *nNodos)
	}
	fmt.Println()

	// ---- Repartir shards disjuntos ----
	tam := totalMuestras / int64(*nNodos)
	resto := totalMuestras % int64(*nNodos)
	ini := int64(0)
	tCarga := time.Now()

	for i, n := range nodos {
		t := tam
		if int64(i) < resto {
			t++
		}
		c := protocolo.CuerpoCargar{Ruta: *datos, Inicio: ini, Fin: ini + t}
		ini += t
		if err := protocolo.EscribirMensaje(n.conn, protocolo.MsgCargar, c.Empaquetar()); err != nil {
			fmt.Fprintf(os.Stderr, "error al enviar shard al nodo %d: %v\n", n.id, err)
			os.Exit(1)
		}
	}

	// Esperar confirmación de carga de los N nodos.
	for _, n := range nodos {
		tipo, cuerpo, err := protocolo.LeerMensaje(n.conn)
		if err != nil || tipo != protocolo.MsgListo {
			fmt.Fprintf(os.Stderr, "nodo %d no confirmó la carga\n", n.id)
			os.Exit(1)
		}
		n.muestras = int64(binary.LittleEndian.Uint64(cuerpo))
	}
	fmt.Printf("  todos los shards cargados en %.2f s\n", time.Since(tCarga).Seconds())
	for _, n := range nodos {
		fmt.Printf("    nodo %d : %14s muestras\n", n.id, conComas(n.muestras))
	}
	fmt.Println()

	// ---- Entrenamiento ----
	w := make([]float64, modelo.NumFeatures)
	grad := make([]float64, modelo.NumFeatures)
	historial := make([]registroRonda, 0, *rondas)

	fmt.Println("--------------------------------------------------------------")
	fmt.Println("ENTRENAMIENTO")
	fmt.Println("--------------------------------------------------------------")
	fmt.Printf("  %-7s %14s %14s %10s\n", "ronda", "pérdida", "‖∇L‖", "ms")

	tEntren := time.Now()
	for t := 1; t <= *rondas; t++ {
		tr := time.Now()
		pesos := protocolo.EmpaquetarFloats(w)

		// (a) Broadcast de los pesos a todos los nodos, en paralelo.
		var wgEnv sync.WaitGroup
		for _, n := range nodos {
			wgEnv.Add(1)
			go func(n *nodoConn) {
				defer wgEnv.Done()
				protocolo.EscribirMensaje(n.conn, protocolo.MsgPesos, pesos)
			}(n)
		}
		wgEnv.Wait()

		// (b) BARRERA: recolectar los N gradientes locales.
		type resp struct {
			g protocolo.CuerpoGradiente
			e error
		}
		respuestas := make([]resp, len(nodos))
		var wgRec sync.WaitGroup
		for i, n := range nodos {
			wgRec.Add(1)
			go func(i int, n *nodoConn) {
				defer wgRec.Done()
				tipo, cuerpo, err := protocolo.LeerMensaje(n.conn)
				if err != nil {
					respuestas[i] = resp{e: err}
					return
				}
				if tipo != protocolo.MsgGradiente {
					respuestas[i] = resp{e: fmt.Errorf("tipo inesperado %d", tipo)}
					return
				}
				respuestas[i] = resp{g: protocolo.DesempaquetarGradiente(cuerpo)}
			}(i, n)
		}
		wgRec.Wait()

		// (c) Agregación: media ponderada por número de muestras.
		for j := range grad {
			grad[j] = 0
		}
		var perdida float64
		var totalN int64
		for _, r := range respuestas {
			if r.e != nil {
				fmt.Fprintln(os.Stderr, "error de nodo:", r.e)
				os.Exit(1)
			}
			peso := float64(r.g.Muestras)
			for j := range grad {
				grad[j] += r.g.Grad[j] * peso
			}
			perdida += r.g.Perdida * peso
			totalN += r.g.Muestras
		}
		inv := 1.0 / float64(totalN)
		for j := range grad {
			grad[j] *= inv
		}
		perdida *= inv

		// (d) Actualización de pesos con regularización L2 (sin penalizar
		// el sesgo, que es la práctica estándar).
		var norma float64
		for j := range w {
			g := grad[j]
			if j > 0 {
				g += *l2 * w[j]
			}
			w[j] -= *lr * g
			norma += g * g
		}
		norma = math.Sqrt(norma)

		ms := float64(time.Since(tr).Microseconds()) / 1000.0
		historial = append(historial, registroRonda{t, perdida, norma, ms})

		if t <= 5 || t%10 == 0 || t == *rondas {
			fmt.Printf("  %-7d %14.8f %14.8f %10.1f\n", t, perdida, norma, ms)
		}
	}
	dEntren := time.Since(tEntren)

	// ---- Evaluación distribuida ----
	fmt.Println()
	fmt.Println("--------------------------------------------------------------")
	fmt.Println("EVALUACIÓN (matriz de confusión global, umbral 0.5)")
	fmt.Println("--------------------------------------------------------------")

	pesos := protocolo.EmpaquetarFloats(w)
	for _, n := range nodos {
		protocolo.EscribirMensaje(n.conn, protocolo.MsgEvaluar, pesos)
	}
	var global modelo.Metricas
	for _, n := range nodos {
		tipo, cuerpo, err := protocolo.LeerMensaje(n.conn)
		if err != nil || tipo != protocolo.MsgMetricas {
			continue
		}
		c := protocolo.DesempaquetarMetricas(cuerpo)
		global.Acumular(modelo.Metricas{
			VP: c.VP, VN: c.VN, FP: c.FP, FN: c.FN,
			Perdida: c.Perdida, N: c.N,
		})
	}

	fmt.Printf("  muestras evaluadas : %s\n", conComas(global.N))
	fmt.Printf("  VP=%s  VN=%s  FP=%s  FN=%s\n",
		conComas(global.VP), conComas(global.VN),
		conComas(global.FP), conComas(global.FN))
	fmt.Println()
	fmt.Printf("  Exactitud     : %.4f\n", global.Exactitud())
	fmt.Printf("  Precisión     : %.4f\n", global.Precision())
	fmt.Printf("  Exhaustividad : %.4f\n", global.Exhaustividad())
	fmt.Printf("  F1            : %.4f\n", global.F1())
	if global.N > 0 {
		fmt.Printf("  Pérdida media : %.6f\n", global.Perdida/float64(global.N))
	}

	// ---- Pesos aprendidos ----
	nombres := [modelo.NumFeatures]string{
		"sesgo", "edad_norm", "sexo_M", "sexo_F",
		"dias_desde_1a_dosis", "intervalo_1a_ultima",
		"fuera_de_lima", "grupo_priorizado",
		"fab_PFIZER", "fab_SINOPHARM", "fab_ASTRAZENECA", "fab_no_registrado",
		"depto_LIMA", "menor_18", "mayor_60",
	}
	fmt.Println()
	fmt.Println("--------------------------------------------------------------")
	fmt.Println("PESOS APRENDIDOS  (signo + = mayor probabilidad de deserción)")
	fmt.Println("--------------------------------------------------------------")
	for j := 0; j < modelo.NumFeatures; j++ {
		fmt.Printf("  %-24s %+12.6f\n", nombres[j], w[j])
	}

	fmt.Println()
	fmt.Println("==============================================================")
	fmt.Printf("  tiempo de entrenamiento : %.2f s  (%d rondas)\n",
		dEntren.Seconds(), *rondas)
	fmt.Printf("  tiempo por ronda        : %.1f ms\n",
		dEntren.Seconds()*1000/float64(*rondas))
	fmt.Printf("  throughput              : %s muestras/s\n",
		conComas(int64(float64(totalMuestras)*float64(*rondas)/dEntren.Seconds())))
	fmt.Println("==============================================================")

	// Guardar historial y modelo.
	if b, err := json.MarshalIndent(map[string]any{
		"nodos": *nNodos, "rondas": *rondas, "lr": *lr,
		"muestras": totalMuestras, "features": modelo.NumFeatures,
		"segundos":  dEntren.Seconds(),
		"historial": historial,
		"pesos":     w,
		"metricas": map[string]float64{
			"exactitud": global.Exactitud(), "precision": global.Precision(),
			"exhaustividad": global.Exhaustividad(), "f1": global.F1(),
		},
	}, "", "  "); err == nil {
		os.WriteFile(*histJSON, b, 0644)
		fmt.Printf("\n  historial guardado en %s\n", *histJSON)
	}

	for _, n := range nodos {
		protocolo.EscribirMensaje(n.conn, protocolo.MsgFin, nil)
		n.conn.Close()
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
