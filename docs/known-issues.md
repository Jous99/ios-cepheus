# Último fallo observado (foto del Mi 9, 2026-10-25, código del repo ios-cepheus anterior, basado en sweet)

```
SWEET EARLY 1: arm_init entered ...
SWEET EARLY 2: PE_init_platform
SWEET EARLY 3: ml_parse_cpu_topology done
SWEET EARLY 4: cpu_bootstrap done
SWEET EARLY PANIC: Invalid ticket lock 0xfffffe0007b2.... <0x00000000 0x00000000 0x00000000 0x00000000> @lock_ticket.c:134
ENTRY FFFFFE000747B488 | SEGS n=0000000A end=02448000 | BOOTARG pa=0244C000 top=02450000 | JUMP 000000010147B488
XNU jumping (fbcon clears screen)
```
(Transcrito de una foto; algún dígito de la dirección del lock es aproximado.)

Pista, **no confirmada**: el contenido del lock sale todo a ceros, lo que suele indicar un lock sin inicializar
(datos estáticos sin cargar o memoria mal mapeada). Comprobar con la nueva cadena si se repite tras `cpu_bootstrap`.
Con UniXNU, los marcadores equivalentes son `cepheus_early_mark(1..4)` (parche 0010).
