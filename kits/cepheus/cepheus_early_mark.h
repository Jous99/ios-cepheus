// cepheus_early_mark — "marcador de progreso" del kernel en la fase más temprana; no necesita fuente de texto ni depende de ningún subsistema.
//
// Motivación: el kernel muere en silencio antes de PE_create_console, así que no sirve ninguna consola.
// Pero boot_args.Video ya da el framebuffer (base / rowBytes / width / height / depth),
// así que al kernel le basta con pintar unos bloques de color en la memoria de vídeo para mostrar en pantalla "hasta qué paso llegó".
//
// ⚠️ Disposición (medida en xnu-10063.141.1): boot_args.Video no es un array, sino
//    struct Boot_Video { v_baseAddr; v_display; v_rowBytes; v_width; v_height; v_depth; }
//    Ojo: v_display está en el **2.º** ulong. pexpert/arm/pe_init.c:419-429 lo lee así.
//    Por eso aquí se recibe como "flujo de ulong": sirve para la estructura y es compatible con el antiguo array [base,rowBytes,...].
//
// Uso (muy al principio de arm_init.c):
//     cepheus_mark_init((const unsigned long *)&args->Video);
//     CEPHUS_MARK(1);            // entra en arm_init
//     ...
//
// Cómo leerlo:
//   N bloques de color arriba a la izquierda ⇒ el kernel llegó al punto de control N
//   ninguno                                   ⇒ ni siquiera entró en arm_init (muere en la entrada en ensamblador/MMU)
//   **bloque rojo** arriba a la derecha       ⇒ el framebuffer es escribible, pero la disposición de Video no coincide (desplazada / depth distinto de 32 bpp)

void cepheus_mark_init(const unsigned long *video);
void cepheus_mark(int n);

// Número de marca → color (1 blanco 2 amarillo 3 cian 4 verde 5 magenta 6 naranja 7 azul 8 rojo)
#define CEPHUS_MARK(n) cepheus_mark(n)
