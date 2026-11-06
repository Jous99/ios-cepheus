// cepheus_early_mark — kernel "progress marker" for the earliest stage; needs no text font and depends on no subsystem.
//
// Motivation: the kernel dies silently before PE_create_console, so no console is of any use.
// But boot_args.Video already gives the framebuffer (base / rowBytes / width / height / depth),
// so the kernel only needs to paint a few colored blocks into video memory to show on screen "how far it got".
//
// ⚠️ Layout (measured on xnu-10063.141.1): boot_args.Video is not an array, but
//    struct Boot_Video { v_baseAddr; v_display; v_rowBytes; v_width; v_height; v_depth; }
//    Note: v_display is in the **2nd** ulong. pexpert/arm/pe_init.c:419-429 reads it this way.
//    That is why it is received here as a "ulong stream": it works for the structure and is compatible with the old [base,rowBytes,...] array.
//
// Usage (very early in arm_init.c):
//     cepheus_mark_init((const unsigned long *)&args->Video);
//     CEPHUS_MARK(1);            // enters arm_init
//     ...
//
// How to read it:
//   N colored blocks at the top left       ⇒ the kernel reached checkpoint N
//   none                                   ⇒ it did not even enter arm_init (dies in the assembly/MMU entry)
//   **red block** at the top right         ⇒ the framebuffer is writable, but the Video layout does not match (shifted / depth other than 32 bpp)

void cepheus_mark_init(const unsigned long *video);
void cepheus_mark(int n);

// Mark number → color (1 white 2 yellow 3 cyan 4 green 5 magenta 6 orange 7 blue 8 red)
#define CEPHUS_MARK(n) cepheus_mark(n)
