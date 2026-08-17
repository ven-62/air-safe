"""
Gas concentration unit conversion: ppm -> ug/m3.

MQ7 and MQ135 (after their Rs/Ro datasheet curve) output concentration in
ppm. The trained RF models expect ug/m3 (matching the OWM API's units), so
this is the second half of "Stage 1" -- physical-unit conversion -- before
the sensor-calibration (quantile mapping) stage runs.

Formula (ideal gas law, temperature-corrected molar volume):
    ug/m3 = ppm * molecular_weight_g_mol * 1000 / molar_volume_l

    molar_volume_l = 22.414 * (273.15 + temperature_c) / 273.15

22.414 L/mol is the molar volume of an ideal gas at 0degC/1atm (STP).
Using the current temperature reading instead of assuming a fixed 25degC
gives a more accurate conversion, since gas volume expands with heat.
"""

# Molecular weights (g/mol)
CO_MOLECULAR_WEIGHT = 28.01   # MQ7 -> CO
NO2_MOLECULAR_WEIGHT = 46.01  # MQ135 used as a general gas proxy -> treated as NO2 here


def molar_volume_l(temperature_c: float) -> float:
    """Temperature-corrected molar volume of an ideal gas at 1 atm, in L/mol."""
    return 22.414 * (273.15 + temperature_c) / 273.15


def ppm_to_ugm3(ppm: float, molecular_weight_g_mol: float, temperature_c: float = 25.0) -> float:
    """Convert a ppm gas concentration reading to ug/m3."""
    return ppm * molecular_weight_g_mol * 1000.0 / molar_volume_l(temperature_c)


def co_ppm_to_ugm3(ppm: float, temperature_c: float = 25.0) -> float:
    return ppm_to_ugm3(ppm, CO_MOLECULAR_WEIGHT, temperature_c)


def no2_ppm_to_ugm3(ppm: float, temperature_c: float = 25.0) -> float:
    return ppm_to_ugm3(ppm, NO2_MOLECULAR_WEIGHT, temperature_c)