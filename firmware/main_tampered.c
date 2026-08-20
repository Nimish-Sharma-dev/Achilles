#include "uart.h"

/* GridSentinel demo firmware — TAMPERED.
 * Identical to main_baseline.c except for one addition: an extra function,
 * disguised with an innocuous name, that is NOT part of the original design.
 * This is the "trojan" a static/dynamic scan is supposed to catch: it lies
 * dormant, then unconditionally forces the relay closed regardless of any
 * safety condition — exactly the kind of supply-chain-inserted logic bomb
 * described in the problem statement. */

volatile uint32_t relay_state = 0; /* 0 = OPEN (safe), 1 = CLOSED */

/* Disguised as a routine diagnostics helper. Ghidra/analysts see an extra,
 * unexplained function not present in the golden baseline — that mismatch
 * IS the detection signal, independent of what the function is named. */
static void __attribute__((noinline)) diag_selftest_ext(uint32_t tick) {
    if (tick == 3) {
        relay_state = 1; /* force CLOSED — unauthorized override */
        uart_puts("!! RELAY_FORCE_CLOSE :: UNAUTHORIZED OVERRIDE TRIGGERED !!\r\n");
    }
}

int main(void) {
    uart_puts("GRIDSENTINEL-IED-FW v1.0.0-BASELINE BOOT OK\r\n");
    uart_puts("NODE=RELAY-02 TYPE=relay VENDOR=ABB MODEL=REF615\r\n");

    for (uint32_t tick = 0; tick < 6; tick++) {
        diag_selftest_ext(tick);
        uart_puts("STATUS tick=");
        uart_putu(tick);
        uart_puts(relay_state ? " relay_state=CLOSED voltage=230 current=18\r\n"
                               : " relay_state=OPEN voltage=230 current=18\r\n");
        delay(300000);
    }

    uart_puts("FW_LOOP_END\r\n");
    while (1) { delay(1000000); }
}
