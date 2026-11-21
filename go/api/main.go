// API REST / WebSocket coordinadora del clúster ML.
//
// ============================================================================
// PARTE C de la arquitectura — API de predicciones
// ----------------------------------------------------------------------------
// Expone el modelo entrenado como servicio web y actúa como coordinador del
// clúster, según describe el enunciado:
//
//   - Expone endpoints REST documentados con OpenAPI/Swagger.
//   - Gestiona la autenticación con tokens JWT.
//   - Coordina el clúster: envía tareas a los nodos de cómputo por TCP y
//     unifica sus resultados.
//   - Persiste predicciones y métricas en MongoDB.
//   - Usa Redis como caché de respuestas precalculadas.
//   - Sirve datos en tiempo real al frontend en JSON mediante WebSocket.
//
// Requisito de latencia: la API debe responder en menos de 100 ms. El modelo
// de regresión logística se mantiene en memoria, de modo que una predicción
// es un producto escalar de quince términos; la persistencia en MongoDB se
// realiza de forma asíncrona para no bloquear la respuesta.
//
// Go PURO: solo biblioteca estándar.
//
// Uso:
//
//	go run ./api -puerto 8080 -mongo localhost:27017 -redis localhost:6379
package main

import (
	"crypto/hmac"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"pc3/almacen"
	"pc3/modelo"
)

// ---------------------------------------------------------------------------
// Estado del servicio
// ---------------------------------------------------------------------------

type servicio struct {
	pesos    []float64
	metricas map[string]float64

	mongo *almacen.Mongo
	redis *almacen.Redis

	secretoJWT []byte

	mu           sync.RWMutex
	predicciones int64
	latencias    []float64 // milisegundos, ventana móvil
	inicio       time.Time

	hub *hub
}

// ---------------------------------------------------------------------------
// Autenticación JWT (HS256), implementada sobre crypto/hmac
// ---------------------------------------------------------------------------

type credenciales struct {
	Usuario    string `json:"usuario"`
	Contrasena string `json:"contrasena"`
}

// usuariosDemo son las cuentas de prueba del sistema. En un despliegue real
// vendrían de MongoDB con las contraseñas cifradas; para el entregable se
// mantienen en memoria y se documentan como datos de prueba.
var usuariosDemo = map[string]struct {
	Clave string
	Rol   string
}{
	"admin":    {"minsa2026", "administrador"},
	"analista": {"vacunas2026", "analista"},
}

func (s *servicio) firmarJWT(usuario, rol string) string {
	cab := base64URL([]byte(`{"alg":"HS256","typ":"JWT"}`))
	cuerpo := base64URL([]byte(fmt.Sprintf(
		`{"sub":%q,"rol":%q,"exp":%d,"iat":%d}`,
		usuario, rol, time.Now().Add(8*time.Hour).Unix(), time.Now().Unix())))
	mensaje := cab + "." + cuerpo
	mac := hmac.New(sha256.New, s.secretoJWT)
	mac.Write([]byte(mensaje))
	return mensaje + "." + base64URL(mac.Sum(nil))
}

func (s *servicio) validarJWT(token string) (usuario, rol string, ok bool) {
	partes := strings.Split(token, ".")
	if len(partes) != 3 {
		return "", "", false
	}
	mensaje := partes[0] + "." + partes[1]
	mac := hmac.New(sha256.New, s.secretoJWT)
	mac.Write([]byte(mensaje))
	if !hmac.Equal([]byte(base64URL(mac.Sum(nil))), []byte(partes[2])) {
		return "", "", false
	}
	cuerpo, err := base64.RawURLEncoding.DecodeString(partes[1])
	if err != nil {
		return "", "", false
	}
	var reclamos struct {
		Sub string `json:"sub"`
		Rol string `json:"rol"`
		Exp int64  `json:"exp"`
	}
	if err := json.Unmarshal(cuerpo, &reclamos); err != nil {
		return "", "", false
	}
	if time.Now().Unix() > reclamos.Exp {
		return "", "", false
	}
	return reclamos.Sub, reclamos.Rol, true
}

func base64URL(b []byte) string {
	return base64.RawURLEncoding.EncodeToString(b)
}

// requiereAuth envuelve un manejador exigiendo un token válido.
func (s *servicio) requiereAuth(siguiente func(http.ResponseWriter, *http.Request, string, string)) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		cab := r.Header.Get("Authorization")
		if !strings.HasPrefix(cab, "Bearer ") {
			responder(w, http.StatusUnauthorized, map[string]string{
				"error": "se requiere cabecera Authorization: Bearer <token>",
			})
			return
		}
		usuario, rol, ok := s.validarJWT(strings.TrimPrefix(cab, "Bearer "))
		if !ok {
			responder(w, http.StatusUnauthorized, map[string]string{
				"error": "token inválido o expirado",
			})
			return
		}
		siguiente(w, r, usuario, rol)
	}
}

// ---------------------------------------------------------------------------
// Predicción
// ---------------------------------------------------------------------------

type solicitudPrediccion struct {
	Edad           int    `json:"edad"`
	Sexo           string `json:"sexo"`         // MASCULINO | FEMENINO
	Departamento   string `json:"departamento"` // LIMA, CUSCO, ...
	Fabricante     string `json:"fabricante"`   // PFIZER | SINOPHARM | ASTRAZENECA | ""
	DiasPrimera    int    `json:"dias_desde_primera_dosis"`
	IntervaloDosis int    `json:"intervalo_entre_dosis"`
	GrupoRiesgo    bool   `json:"grupo_riesgo_priorizado"`
}

type respuestaPrediccion struct {
	Probabilidad  float64 `json:"probabilidad_desercion"`
	Clasificacion string  `json:"clasificacion"`
	Riesgo        string  `json:"nivel_riesgo"`
	Recomendacion string  `json:"recomendacion"`
	LatenciaMs    float64 `json:"latencia_ms"`
	DesdeCache    bool    `json:"desde_cache"`
}

// vectorizar traduce la solicitud al vector de características con el que se
// entrenó el modelo. El orden debe coincidir exactamente con el que define
// go/etiquetado; cualquier discrepancia produciría predicciones sin sentido.
func vectorizar(s solicitudPrediccion) [modelo.NumFeatures]float32 {
	var x [modelo.NumFeatures]float32
	x[0] = 1
	x[1] = float32(s.Edad) / 100.0
	if strings.EqualFold(s.Sexo, "MASCULINO") {
		x[2] = 1
	}
	if strings.EqualFold(s.Sexo, "FEMENINO") {
		x[3] = 1
	}
	x[4] = float32(s.DiasPrimera) / 1800.0
	x[5] = float32(s.IntervaloDosis) / 1800.0
	esLima := strings.EqualFold(s.Departamento, "LIMA")
	if !esLima {
		x[6] = 1
	}
	if s.GrupoRiesgo {
		x[7] = 1
	}
	switch strings.ToUpper(s.Fabricante) {
	case "PFIZER":
		x[8] = 1
	case "SINOPHARM":
		x[9] = 1
	case "ASTRAZENECA":
		x[10] = 1
	default:
		x[11] = 1
	}
	if esLima {
		x[12] = 1
	}
	if s.Edad < 18 {
		x[13] = 1
	}
	if s.Edad >= 60 {
		x[14] = 1
	}
	return x
}

func claveCache(s solicitudPrediccion) string {
	return fmt.Sprintf("pred:%d:%s:%s:%s:%d:%d:%t",
		s.Edad, strings.ToUpper(s.Sexo), strings.ToUpper(s.Departamento),
		strings.ToUpper(s.Fabricante), s.DiasPrimera, s.IntervaloDosis, s.GrupoRiesgo)
}

func nivelRiesgo(p float64) (string, string) {
	switch {
	case p >= 0.70:
		return "ALTO", "Contacto telefónico prioritario y visita domiciliaria de brigada móvil."
	case p >= 0.45:
		return "MEDIO", "Recordatorio por mensaje de texto y seguimiento en el establecimiento."
	default:
		return "BAJO", "Seguimiento regular según el calendario de vacunación."
	}
}

func (s *servicio) manejarPrediccion(w http.ResponseWriter, r *http.Request, usuario, rol string) {
	t0 := time.Now()
	if r.Method != http.MethodPost {
		responder(w, http.StatusMethodNotAllowed, map[string]string{"error": "use POST"})
		return
	}

	var req solicitudPrediccion
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		responder(w, http.StatusBadRequest, map[string]string{
			"error": "cuerpo JSON inválido: " + err.Error(),
		})
		return
	}
	if req.Edad < 0 || req.Edad > 120 {
		responder(w, http.StatusBadRequest, map[string]string{
			"error": "la edad debe estar entre 0 y 120 años",
		})
		return
	}

	clave := claveCache(req)

	// Primer nivel: caché de respuestas precalculadas en Redis.
	if v, ok := s.redis.Obtener(clave); ok {
		var resp respuestaPrediccion
		if json.Unmarshal([]byte(v), &resp) == nil {
			resp.DesdeCache = true
			resp.LatenciaMs = float64(time.Since(t0).Microseconds()) / 1000.0
			s.registrarLatencia(resp.LatenciaMs)
			responder(w, http.StatusOK, resp)
			return
		}
	}

	// Segundo nivel: cálculo con el modelo en memoria.
	x := vectorizar(req)
	p := modelo.Predecir(s.pesos, &x)
	riesgo, recomendacion := nivelRiesgo(p)
	clasificacion := "COMPLETARÁ"
	if p >= 0.5 {
		clasificacion = "DESERTARÁ"
	}

	resp := respuestaPrediccion{
		Probabilidad:  redondear(p, 6),
		Clasificacion: clasificacion,
		Riesgo:        riesgo,
		Recomendacion: recomendacion,
		DesdeCache:    false,
	}
	resp.LatenciaMs = float64(time.Since(t0).Microseconds()) / 1000.0
	s.registrarLatencia(resp.LatenciaMs)

	responder(w, http.StatusOK, resp)

	// La persistencia y la caché se hacen después de responder, para no
	// penalizar la latencia que el enunciado exige por debajo de 100 ms.
	go func() {
		if b, err := json.Marshal(resp); err == nil {
			s.redis.GuardarTTL(clave, string(b), 3600)
		}
		s.redis.Incrementar("contador:predicciones")

		doc := almacen.NuevoDoc().
			Str("usuario", usuario).
			Str("rol", rol).
			Int("edad", int64(req.Edad)).
			Str("sexo", req.Sexo).
			Str("departamento", req.Departamento).
			Str("fabricante", req.Fabricante).
			Int("dias_primera_dosis", int64(req.DiasPrimera)).
			Int("intervalo_dosis", int64(req.IntervaloDosis)).
			Bool("grupo_riesgo", req.GrupoRiesgo).
			Flo("probabilidad", p).
			Str("clasificacion", clasificacion).
			Str("nivel_riesgo", riesgo).
			Flo("latencia_ms", resp.LatenciaMs).
			Int("marca_tiempo", time.Now().Unix())
		s.mongo.Insertar("predicciones", *doc)

		s.hub.difundir(map[string]any{
			"tipo":         "prediccion",
			"probabilidad": resp.Probabilidad,
			"riesgo":       riesgo,
			"departamento": req.Departamento,
			"edad":         req.Edad,
			"latencia_ms":  resp.LatenciaMs,
			"marca_tiempo": time.Now().Format(time.RFC3339),
		})
	}()
}

// manejarLotePrediccion procesa varias solicitudes de forma concurrente.
// Demuestra el uso de goroutines también en la capa de servicio.
func (s *servicio) manejarLote(w http.ResponseWriter, r *http.Request, usuario, rol string) {
	t0 := time.Now()
	var reqs []solicitudPrediccion
	if err := json.NewDecoder(r.Body).Decode(&reqs); err != nil {
		responder(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	if len(reqs) == 0 || len(reqs) > 10000 {
		responder(w, http.StatusBadRequest, map[string]string{
			"error": "el lote debe contener entre 1 y 10000 solicitudes",
		})
		return
	}

	resultados := make([]respuestaPrediccion, len(reqs))
	var wg sync.WaitGroup
	for i := range reqs {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			x := vectorizar(reqs[i])
			p := modelo.Predecir(s.pesos, &x)
			riesgo, rec := nivelRiesgo(p)
			cls := "COMPLETARÁ"
			if p >= 0.5 {
				cls = "DESERTARÁ"
			}
			resultados[i] = respuestaPrediccion{
				Probabilidad: redondear(p, 6), Clasificacion: cls,
				Riesgo: riesgo, Recomendacion: rec,
			}
		}(i)
	}
	wg.Wait()

	ms := float64(time.Since(t0).Microseconds()) / 1000.0
	s.registrarLatencia(ms)
	responder(w, http.StatusOK, map[string]any{
		"total":             len(resultados),
		"latencia_ms":       ms,
		"latencia_por_item": redondear(ms/float64(len(resultados)), 6),
		"resultados":        resultados,
	})
}

// ---------------------------------------------------------------------------
// Métricas y salud
// ---------------------------------------------------------------------------

func (s *servicio) registrarLatencia(ms float64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.predicciones++
	s.latencias = append(s.latencias, ms)
	if len(s.latencias) > 5000 {
		s.latencias = s.latencias[len(s.latencias)-5000:]
	}
}

func (s *servicio) resumenLatencia() (media, p50, p95, p99, max float64) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if len(s.latencias) == 0 {
		return
	}
	c := append([]float64(nil), s.latencias...)
	for i := 1; i < len(c); i++ {
		for j := i; j > 0 && c[j] < c[j-1]; j-- {
			c[j], c[j-1] = c[j-1], c[j]
		}
	}
	var suma float64
	for _, v := range c {
		suma += v
	}
	media = suma / float64(len(c))
	p50 = c[len(c)*50/100]
	p95 = c[min(len(c)*95/100, len(c)-1)]
	p99 = c[min(len(c)*99/100, len(c)-1)]
	max = c[len(c)-1]
	return
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func (s *servicio) manejarMetricas(w http.ResponseWriter, r *http.Request, usuario, rol string) {
	media, p50, p95, p99, max := s.resumenLatencia()
	aciertos, fallos, tasa := s.redis.Estadisticas()

	s.mu.RLock()
	total := s.predicciones
	s.mu.RUnlock()

	var guardadas int64
	if s.mongo.Activo() {
		guardadas, _ = s.mongo.Contar("predicciones")
	}

	responder(w, http.StatusOK, map[string]any{
		"servicio": map[string]any{
			"activo_desde":      s.inicio.Format(time.RFC3339),
			"tiempo_activo_seg": int64(time.Since(s.inicio).Seconds()),
			"predicciones":      total,
			"clientes_ws":       s.hub.cantidad(),
		},
		"latencia_ms": map[string]float64{
			"media": redondear(media, 4), "p50": redondear(p50, 4),
			"p95": redondear(p95, 4), "p99": redondear(p99, 4),
			"max": redondear(max, 4),
		},
		"cumple_sla_100ms": p99 < 100,
		"modelo": map[string]any{
			"algoritmo":              "Regresión Logística Distribuida",
			"caracteristicas":        modelo.NumFeatures,
			"muestras_entrenamiento": 30816349,
			"metricas":               s.metricas,
		},
		"cache_redis": map[string]any{
			"activo": s.redis.Activo(), "aciertos": aciertos,
			"fallos": fallos, "tasa_acierto": redondear(tasa, 4),
			"claves": s.redis.Claves(),
		},
		"mongodb": map[string]any{
			"activo": s.mongo.Activo(), "predicciones_guardadas": guardadas,
		},
	})
}

func (s *servicio) manejarSalud(w http.ResponseWriter, r *http.Request) {
	responder(w, http.StatusOK, map[string]any{
		"estado":  "operativo",
		"version": "1.0.0-pc4",
		"componentes": map[string]bool{
			"modelo":  len(s.pesos) == modelo.NumFeatures,
			"mongodb": s.mongo.Activo(),
			"redis":   s.redis.Activo(),
		},
	})
}

func (s *servicio) manejarLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		responder(w, http.StatusMethodNotAllowed, map[string]string{"error": "use POST"})
		return
	}
	var c credenciales
	if err := json.NewDecoder(r.Body).Decode(&c); err != nil {
		responder(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	u, ok := usuariosDemo[c.Usuario]
	if !ok || u.Clave != c.Contrasena {
		responder(w, http.StatusUnauthorized, map[string]string{
			"error": "usuario o contraseña incorrectos",
		})
		return
	}
	responder(w, http.StatusOK, map[string]any{
		"token":      s.firmarJWT(c.Usuario, u.Rol),
		"usuario":    c.Usuario,
		"rol":        u.Rol,
		"expira_seg": 8 * 3600,
	})
}

// ---------------------------------------------------------------------------
// WebSocket (RFC 6455) sobre la biblioteca estándar
// ---------------------------------------------------------------------------

type hub struct {
	mu       sync.RWMutex
	clientes map[chan []byte]bool
}

func nuevoHub() *hub { return &hub{clientes: make(map[chan []byte]bool)} }

func (h *hub) registrar() chan []byte {
	c := make(chan []byte, 32)
	h.mu.Lock()
	h.clientes[c] = true
	h.mu.Unlock()
	return c
}

func (h *hub) quitar(c chan []byte) {
	h.mu.Lock()
	delete(h.clientes, c)
	h.mu.Unlock()
	close(c)
}

func (h *hub) cantidad() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clientes)
}

func (h *hub) difundir(v any) {
	b, err := json.Marshal(v)
	if err != nil {
		return
	}
	h.mu.RLock()
	defer h.mu.RUnlock()
	for c := range h.clientes {
		select {
		case c <- b:
		default: // cliente lento: se descarta el mensaje en lugar de bloquear
		}
	}
}

const guidWS = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

func (s *servicio) manejarWS(w http.ResponseWriter, r *http.Request) {
	if !strings.EqualFold(r.Header.Get("Upgrade"), "websocket") {
		responder(w, http.StatusBadRequest, map[string]string{
			"error": "este endpoint requiere una conexión WebSocket",
		})
		return
	}
	clave := r.Header.Get("Sec-WebSocket-Key")
	if clave == "" {
		responder(w, http.StatusBadRequest, map[string]string{"error": "falta Sec-WebSocket-Key"})
		return
	}

	hj, ok := w.(http.Hijacker)
	if !ok {
		responder(w, http.StatusInternalServerError, map[string]string{
			"error": "el servidor no soporta hijacking",
		})
		return
	}
	conn, bufrw, err := hj.Hijack()
	if err != nil {
		return
	}
	defer conn.Close()

	// Handshake RFC 6455: SHA-1 de la clave concatenada con el GUID.
	h := sha1.New()
	h.Write([]byte(clave + guidWS))
	aceptar := base64.StdEncoding.EncodeToString(h.Sum(nil))

	fmt.Fprintf(bufrw, "HTTP/1.1 101 Switching Protocols\r\n"+
		"Upgrade: websocket\r\nConnection: Upgrade\r\n"+
		"Sec-WebSocket-Accept: %s\r\n\r\n", aceptar)
	bufrw.Flush()

	canal := s.hub.registrar()
	defer s.hub.quitar(canal)

	// Mensaje inicial con el estado del servicio.
	media, _, p95, _, _ := s.resumenLatencia()
	s.mu.RLock()
	total := s.predicciones
	s.mu.RUnlock()
	inicial, _ := json.Marshal(map[string]any{
		"tipo": "bienvenida", "predicciones": total,
		"latencia_media_ms": redondear(media, 4),
		"latencia_p95_ms":   redondear(p95, 4),
	})
	escribirTramaWS(conn, inicial)

	latido := time.NewTicker(15 * time.Second)
	defer latido.Stop()

	for {
		select {
		case msg, ok := <-canal:
			if !ok {
				return
			}
			if err := escribirTramaWS(conn, msg); err != nil {
				return
			}
		case <-latido.C:
			media, _, p95, _, _ := s.resumenLatencia()
			s.mu.RLock()
			total := s.predicciones
			s.mu.RUnlock()
			b, _ := json.Marshal(map[string]any{
				"tipo": "latido", "predicciones": total,
				"latencia_media_ms": redondear(media, 4),
				"latencia_p95_ms":   redondear(p95, 4),
				"clientes":          s.hub.cantidad(),
				"marca_tiempo":      time.Now().Format(time.RFC3339),
			})
			if err := escribirTramaWS(conn, b); err != nil {
				return
			}
		}
	}
}

// escribirTramaWS emite una trama de texto sin máscara (servidor → cliente).
func escribirTramaWS(conn interface{ Write([]byte) (int, error) }, datos []byte) error {
	n := len(datos)
	var cab []byte
	switch {
	case n < 126:
		cab = []byte{0x81, byte(n)}
	case n < 65536:
		cab = []byte{0x81, 126, byte(n >> 8), byte(n)}
	default:
		cab = []byte{0x81, 127, 0, 0, 0, 0,
			byte(n >> 24), byte(n >> 16), byte(n >> 8), byte(n)}
	}
	if _, err := conn.Write(cab); err != nil {
		return err
	}
	_, err := conn.Write(datos)
	return err
}

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

func responder(w http.ResponseWriter, codigo int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	w.WriteHeader(codigo)
	json.NewEncoder(w).Encode(v)
}

func redondear(v float64, d int) float64 {
	p := 1.0
	for i := 0; i < d; i++ {
		p *= 10
	}
	return float64(int64(v*p+0.5)) / p
}

func conCORS(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodOptions {
			w.Header().Set("Access-Control-Allow-Origin", "*")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			w.WriteHeader(http.StatusNoContent)
			return
		}
		h.ServeHTTP(w, r)
	})
}

// ---------------------------------------------------------------------------

func main() {
	puerto := flag.Int("puerto", 8080, "puerto HTTP")
	dirMongo := flag.String("mongo", "localhost:27017", "dirección de MongoDB")
	dirRedis := flag.String("redis", "localhost:6379", "dirección de Redis")
	rutaModelo := flag.String("modelo", "../docs/historial_entrenamiento.json", "modelo entrenado")
	secreto := flag.String("secreto", "cc65-vacunacion-2026", "secreto para firmar JWT")
	flag.Parse()

	// Permitir configuración por variables de entorno (Docker Compose).
	if v := os.Getenv("MONGO_DIR"); v != "" {
		*dirMongo = v
	}
	if v := os.Getenv("REDIS_DIR"); v != "" {
		*dirRedis = v
	}
	if v := os.Getenv("MODELO_RUTA"); v != "" {
		*rutaModelo = v
	}

	b, err := os.ReadFile(*rutaModelo)
	if err != nil {
		log.Fatalf("no se pudo leer el modelo entrenado: %v", err)
	}
	var entrenado struct {
		Pesos    []float64          `json:"pesos"`
		Metricas map[string]float64 `json:"metricas"`
	}
	if err := json.Unmarshal(b, &entrenado); err != nil {
		log.Fatalf("modelo inválido: %v", err)
	}
	if len(entrenado.Pesos) != modelo.NumFeatures {
		log.Fatalf("el modelo tiene %d pesos y se esperaban %d",
			len(entrenado.Pesos), modelo.NumFeatures)
	}

	s := &servicio{
		pesos:      entrenado.Pesos,
		metricas:   entrenado.Metricas,
		mongo:      almacen.NuevoMongo(*dirMongo, "vacunacion"),
		redis:      almacen.NuevoRedis(*dirRedis),
		secretoJWT: []byte(*secreto),
		inicio:     time.Now(),
		hub:        nuevoHub(),
	}
	defer s.mongo.Cerrar()
	defer s.redis.Cerrar()

	mux := http.NewServeMux()
	mux.HandleFunc("/api/salud", s.manejarSalud)
	mux.HandleFunc("/api/login", s.manejarLogin)
	mux.HandleFunc("/api/predecir", s.requiereAuth(s.manejarPrediccion))
	mux.HandleFunc("/api/predecir/lote", s.requiereAuth(s.manejarLote))
	mux.HandleFunc("/api/metricas", s.requiereAuth(s.manejarMetricas))
	mux.HandleFunc("/ws", s.manejarWS)
	mux.HandleFunc("/swagger.json", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Write([]byte(especificacionOpenAPI))
	})
	mux.HandleFunc("/swagger", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Write([]byte(paginaSwagger))
	})

	fmt.Println("==============================================================")
	fmt.Println("API COORDINADORA — Vacunación Nacional (Caso 7)")
	fmt.Println("==============================================================")
	fmt.Printf("  modelo cargado   : %d características\n", len(entrenado.Pesos))
	fmt.Printf("  exactitud        : %.4f   F1: %.4f\n",
		entrenado.Metricas["exactitud"], entrenado.Metricas["f1"])
	fmt.Printf("  MongoDB          : %v\n", s.mongo.Activo())
	fmt.Printf("  Redis            : %v\n", s.redis.Activo())
	fmt.Println("--------------------------------------------------------------")
	fmt.Printf("  REST   : http://localhost:%d/api/...\n", *puerto)
	fmt.Printf("  Swagger: http://localhost:%d/swagger\n", *puerto)
	fmt.Printf("  WS     : ws://localhost:%d/ws\n", *puerto)
	fmt.Println("==============================================================")

	srv := &http.Server{
		Addr:         fmt.Sprintf(":%d", *puerto),
		Handler:      conCORS(mux),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 0, // sin límite: el WebSocket mantiene la conexión abierta
		IdleTimeout:  120 * time.Second,
	}
	log.Fatal(srv.ListenAndServe())
}
