// Package modelo contiene el núcleo compartido de la Regresión Logística
// Distribuida: representación de features, función sigmoide, cálculo de
// gradientes y métricas de evaluación.
//
// Go PURO: solo biblioteca estándar.
//
// Curso CC65 — Trabajo Final — Caso 7: Clasificación y Seguimiento de la
// Vacunación Nacional (predicción de deserción en 2ª/3ª dosis).
package modelo

import (
	"math"
)

// NumFeatures es la dimensión del vector de características.
//
//	 0 : sesgo (siempre 1.0)
//	 1 : edad normalizada
//	 2 : sexo masculino (one-hot)
//	 3 : sexo femenino (one-hot)
//	 4 : días entre la 1ª dosis y el corte, normalizado
//	 5 : intervalo entre 1ª y última dosis, normalizado
//	 6 : es zona rural / provincia distinta a capital (binaria)
//	 7 : pertenece a grupo de riesgo priorizado (binaria)
//	 8 : fabricante PFIZER (one-hot)
//	 9 : fabricante SINOPHARM (one-hot)
//	10 : fabricante ASTRAZENECA (one-hot)
//	11 : fabricante no registrado (one-hot)
//	12 : departamento LIMA (binaria; concentra el 36.85% de las dosis)
//	13 : edad < 18 años (binaria)
//	14 : edad >= 60 años (binaria)
const NumFeatures = 15

// Muestra es un registro de entrenamiento ya vectorizado.
type Muestra struct {
	X [NumFeatures]float32
	Y uint8 // 1 = desertó, 0 = completó
}

// Sigmoide acotada: evita overflow en exp para |z| grande.
func Sigmoide(z float64) float64 {
	if z >= 0 {
		return 1.0 / (1.0 + math.Exp(-z))
	}
	e := math.Exp(z)
	return e / (1.0 + e)
}

// Predecir devuelve P(y=1 | x) para los pesos dados.
func Predecir(w []float64, x *[NumFeatures]float32) float64 {
	var z float64
	for i := 0; i < NumFeatures; i++ {
		z += w[i] * float64(x[i])
	}
	return Sigmoide(z)
}

// GradienteLote acumula el gradiente de la log-verosimilitud negativa sobre
// un lote de muestras, junto con la pérdida.
//
// Para regresión logística, el gradiente respecto de w_j es:
//
//	∂L/∂w_j = (1/n) · Σ (σ(wᵀx_i) − y_i) · x_ij
//
// Esta función NO toca estado compartido: el llamante le pasa su propio
// buffer `grad`. Es lo que permite que cada nodo del clúster calcule su
// gradiente local sin sincronización alguna.
func GradienteLote(w []float64, muestras []Muestra, grad []float64) (perdida float64, n int) {
	for i := range grad {
		grad[i] = 0
	}
	if len(muestras) == 0 {
		return 0, 0
	}
	for i := range muestras {
		m := &muestras[i]
		p := Predecir(w, &m.X)
		y := float64(m.Y)

		// Pérdida logarítmica, acotada para evitar log(0).
		const eps = 1e-12
		if y == 1 {
			perdida -= math.Log(math.Max(p, eps))
		} else {
			perdida -= math.Log(math.Max(1-p, eps))
		}

		err := p - y
		for j := 0; j < NumFeatures; j++ {
			grad[j] += err * float64(m.X[j])
		}
	}
	inv := 1.0 / float64(len(muestras))
	for j := range grad {
		grad[j] *= inv
	}
	return perdida * inv, len(muestras)
}

// Metricas resume la calidad del clasificador sobre un conjunto de datos.
type Metricas struct {
	VP, VN, FP, FN int64
	Perdida        float64
	N              int64
}

func (m *Metricas) Acumular(o Metricas) {
	m.VP += o.VP
	m.VN += o.VN
	m.FP += o.FP
	m.FN += o.FN
	m.Perdida += o.Perdida
	m.N += o.N
}

func (m Metricas) Exactitud() float64 {
	t := m.VP + m.VN + m.FP + m.FN
	if t == 0 {
		return 0
	}
	return float64(m.VP+m.VN) / float64(t)
}

func (m Metricas) Precision() float64 {
	if m.VP+m.FP == 0 {
		return 0
	}
	return float64(m.VP) / float64(m.VP+m.FP)
}

func (m Metricas) Exhaustividad() float64 {
	if m.VP+m.FN == 0 {
		return 0
	}
	return float64(m.VP) / float64(m.VP+m.FN)
}

func (m Metricas) F1() float64 {
	p, r := m.Precision(), m.Exhaustividad()
	if p+r == 0 {
		return 0
	}
	return 2 * p * r / (p + r)
}

// Evaluar calcula las métricas de un conjunto con el umbral dado.
func Evaluar(w []float64, muestras []Muestra, umbral float64) Metricas {
	var m Metricas
	const eps = 1e-12
	for i := range muestras {
		s := &muestras[i]
		p := Predecir(w, &s.X)
		if s.Y == 1 {
			m.Perdida -= math.Log(math.Max(p, eps))
		} else {
			m.Perdida -= math.Log(math.Max(1-p, eps))
		}
		pred := uint8(0)
		if p >= umbral {
			pred = 1
		}
		switch {
		case pred == 1 && s.Y == 1:
			m.VP++
		case pred == 0 && s.Y == 0:
			m.VN++
		case pred == 1 && s.Y == 0:
			m.FP++
		default:
			m.FN++
		}
	}
	m.N = int64(len(muestras))
	if m.N > 0 {
		m.Perdida /= float64(m.N)
	}
	return m
}
