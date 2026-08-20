#include "uart.h"

/* GridSentinel demo firmware — CLEAN BASELINE.
 * Simulates a relay IED's main loop: boot banner, then periodic status
 * telemetry over UART. This is the "golden" image every scan diffs against. */

volatile uint32_t relay_state = 0; /* 0 = OPEN (safe) */

int main(void) {
    uart_puts("GRIDSENTINEL-IED-FW v1.0.0-BASELINE BOOT OK\r\n");
    uart_puts("NODE=RELAY-02 TYPE=relay VENDOR=ABB MODEL=REF615\r\n");

    for (uint32_t tick = 0; tick < 6; tick++) {
        uart_puts("STATUS tick=");
        uart_putu(tick);
        uart_puts(" relay_state=OPEN voltage=230 current=18\r\n");
        delay(300000);
    }

    uart_puts("FW_LOOP_END\r\n");
    while (1) { delay(1000000); }
}
