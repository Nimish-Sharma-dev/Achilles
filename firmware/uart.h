#ifndef UART_H
#define UART_H
#include <stdint.h>

#define UART0_BASE 0x4000C000u
#define UART_DR (*(volatile uint32_t *)(UART0_BASE + 0x000))
#define UART_FR (*(volatile uint32_t *)(UART0_BASE + 0x018))
#define UART_TXFF (1u << 5)

static inline void uart_putc(char c) {
    while (UART_FR & UART_TXFF) {}
    UART_DR = (uint32_t)c;
}

static inline void uart_puts(const char *s) {
    while (*s) uart_putc(*s++);
}

static inline void uart_putu(uint32_t v) {
    char buf[11];
    int i = 10;
    buf[10] = '\0';
    if (v == 0) { uart_putc('0'); return; }
    while (v && i > 0) { buf[--i] = '0' + (v % 10); v /= 10; }
    uart_puts(&buf[i]);
}

static inline void delay(volatile uint32_t n) { while (n--) {} }

#endif
