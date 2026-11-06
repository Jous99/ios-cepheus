// Implementation: only normal memory writes (base + rowBytes*y + 4*x); it touches no register,
// allocates no memory and a failure never panics: in the worst case, nothing more appears on screen.
//
// This file is kept identical to the inline MKC / MKH in UniXNU/scripts/build-xnu-4k-baseline.sh
// (the CI uses that inline version; this directory is the commented source mirror).

#include "cepheus_early_mark.h"
#include <stddef.h>

static volatile unsigned int *g_fb = NULL;
static unsigned long g_px = 0;      // pixels per row = rowBytes / 4
static unsigned int  g_w  = 0;
static unsigned int  g_h  = 0;
static int           g_slot = 0;    // slot where the next mark is drawn

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
		return;                 // no framebuffer: give up silently
	}

	// struct Boot_Video order: base, display, rowBytes, width, height, depth
	row = v[2];
	w   = v[3];
	h   = v[4];
	if (!sane(row, w, h)) {
		// old array order: base, rowBytes, width, height, depth, display
		row = v[1];
		w   = v[2];
		h   = v[3];
		fallback = 1;
		if (!sane(row, w, h)) {
			// the geometry is not available at all, but base looks writable:
			// a small red dot is drawn to tell "framebuffer not mapped" apart from "mapped but with garbage parameters"
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

	// first a black strip is laid down, to ensure the blocks have contrast
	fill(0, 0, g_w, 112, 0xFF000000);

	// if the fallback was used (or depth is not 32 bpp), a red block is drawn at the right end of the strip to warn that the layout is wrong
	if (fallback || (v[5] & 0xFF) != 32) {
		fill(32 + 7 * 64, 32, 48, 48, 0xFFFF0000);
	}
}

void cepheus_mark(int n)
{
	static const unsigned int colors[9] = {
		0,          // 0 unused
		0xFFFFFFFF, // 1 white
		0xFFFFFF00, // 2 yellow
		0xFF00FFFF, // 3 cyan
		0xFF00FF00, // 4 green
		0xFFFF00FF, // 5 magenta
		0xFFFF8000, // 6 orange
		0xFF0000FF, // 7 blue
		0xFFFF0000, // 8 red (errors only)
	};

	if (g_fb == NULL || n < 1 || n > 8 || g_slot >= 8) {
		return;
	}
	fill(32 + (unsigned int)g_slot * 64, 32, 48, 48, colors[n]);
	g_slot++;
}
