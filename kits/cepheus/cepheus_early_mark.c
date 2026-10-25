// Implementación: solo escrituras de memoria normal (base + rowBytes*y + 4*x); no toca ningún registro,
// no asigna memoria y un fallo nunca hace panic: en el peor caso, no aparece nada más en pantalla.
//
// Este archivo se mantiene igual que los MKC / MKH en línea de UniXNU/scripts/build-xnu-4k-baseline.sh
// (el CI usa esa versión en línea; este directorio es el espejo fuente con comentarios).

#include "cepheus_early_mark.h"
#include <stddef.h>

static volatile unsigned int *g_fb = NULL;
static unsigned long g_px = 0;      // píxeles por fila = rowBytes / 4
static unsigned int  g_w  = 0;
static unsigned int  g_h  = 0;
static int           g_slot = 0;    // en qué ranura se dibuja la siguiente marca

static void fill(unsigned int x0, unsigned int y0, unsigned int w, unsigned int h, unsigned int c)
{
	unsigned int x, y, xe = x0 + w, ye = y0 + h;
	if (g_fb == NULL) {
		return;
	}
	if (xe > g_w) {
		xe = g_w;
	}
	if (ye > g_h) {
		ye = g_h;
	}
	for (y = y0; y < ye; y++) {
		for (x = x0; x < xe; x++) {
			g_fb[(unsigned long)y * g_px + x] = c;
		}
	}
}

static int sane(unsigned long row, unsigned long w, unsigned long h)
{
	return row >= 4 && row <= 65536 && w >= 1 && w <= 8192 && h >= 1 && h <= 8192;
}

void cepheus_mark_init(const unsigned long *v)
{
	unsigned long row, w, h;
	int fallback = 0;

	g_fb = NULL;
	g_px = 0;
	g_w = 0;
	g_h = 0;
	g_slot = 0;

	if (v == NULL || v[0] == 0) {
		return;                 // sin framebuffer: se abandona en silencio
	}

	// orden de struct Boot_Video: base, display, rowBytes, width, height, depth
	row = v[2];
	w   = v[3];
	h   = v[4];
	if (!sane(row, w, h)) {
		// orden del array antiguo: base, rowBytes, width, height, depth, display
		row = v[1];
		w   = v[2];
		h   = v[3];
		fallback = 1;
		if (!sane(row, w, h)) {
			// la geometría no está disponible en absoluto, pero base parece escribible:
			// se dibuja un puntito rojo para poder distinguir "framebuffer sin mapear" de "mapeado pero con parámetros basura"
			g_fb = (volatile unsigned int *)(unsigned long)v[0];
			g_px = 4096;
			g_w  = 4096;
			g_h  = 4096;
			fill(0, 0, 16, 16, 0xFFFF0000);
			g_fb = NULL;
			return;
		}
	}

	g_fb = (volatile unsigned int *)(unsigned long)v[0];
	g_px = row / 4;
	g_w  = (unsigned int)w;
	g_h  = (unsigned int)h;

	// primero se extiende una franja negra, para asegurar el contraste de los bloques
	fill(0, 0, g_w, 112, 0xFF000000);

	// si se usó el fallback (o depth no es de 32 bpp), se dibuja un bloque rojo en el extremo derecho de la franja para avisar de que la disposición falla
	if (fallback || (v[5] & 0xFF) != 32) {
		fill(32 + 7 * 64, 32, 48, 48, 0xFFFF0000);
	}
}

void cepheus_mark(int n)
{
	static const unsigned int colors[9] = {
		0,          // 0 sin usar
		0xFFFFFFFF, // 1 blanco
		0xFFFFFF00, // 2 amarillo
		0xFF00FFFF, // 3 cian
		0xFF00FF00, // 4 verde
		0xFFFF00FF, // 5 magenta
		0xFFFF8000, // 6 naranja
		0xFF0000FF, // 7 azul
		0xFFFF0000, // 8 rojo (solo para errores)
	};

	if (g_fb == NULL || n < 1 || n > 8 || g_slot >= 8) {
		return;
	}
	fill(32 + (unsigned int)g_slot * 64, 32, 48, 48, colors[n]);
	g_slot++;
}
