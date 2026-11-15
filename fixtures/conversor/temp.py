"""Conversor de temperatura con bug en la fórmula de Fahrenheit a Celsius."""


def fahrenheit_a_celsius(f):
    return (f - 32) * 5 / 9 + 1  # ← la fórmula correcta no lleva +1
