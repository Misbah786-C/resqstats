"""Reference data: Karachi towns, major hospitals, and ambulance stations.

Coordinates are approximate town/facility centroids - good enough for a
simulator whose purpose is realistic *patterns*, not navigation.
Population weights are rough relative densities used to place incidents.
"""

# (name, lat, lon, incident_weight)
TOWNS: list[tuple[str, float, float, float]] = [
    ("Saddar", 24.8556, 67.0226, 8.0),
    ("Lyari", 24.8694, 66.9967, 7.0),
    ("Kemari", 24.8480, 66.9776, 4.0),
    ("Clifton", 24.8138, 67.0300, 4.5),
    ("DHA", 24.7926, 67.0466, 4.0),
    ("Garden", 24.8736, 67.0184, 4.0),
    ("Liaquatabad", 24.9024, 67.0414, 7.5),
    ("Nazimabad", 24.9100, 67.0260, 6.0),
    ("North Nazimabad", 24.9387, 67.0364, 6.5),
    ("New Karachi", 24.9750, 67.0670, 7.0),
    ("North Karachi", 24.9886, 67.0570, 7.0),
    ("Surjani", 25.0280, 67.0710, 4.0),
    ("Orangi", 24.9494, 66.9817, 9.0),
    ("Baldia", 24.9077, 66.9494, 5.0),
    ("SITE", 24.8920, 66.9920, 5.5),
    ("Gulshan-e-Iqbal", 24.9180, 67.0971, 8.0),
    ("Gulistan-e-Johar", 24.9129, 67.1382, 6.5),
    ("Shah Faisal", 24.8770, 67.1450, 5.5),
    ("Korangi", 24.8450, 67.1297, 9.0),
    ("Landhi", 24.8505, 67.2066, 7.5),
    ("Malir", 24.8932, 67.2066, 6.5),
    ("Gadap", 25.0500, 67.2300, 2.0),
]

# (name, lat, lon)
HOSPITALS: list[tuple[str, float, float]] = [
    ("Jinnah Postgraduate Medical Centre", 24.8497, 67.0397),
    ("Civil Hospital Karachi", 24.8568, 67.0104),
    ("Aga Khan University Hospital", 24.8917, 67.0747),
    ("Abbasi Shaheed Hospital", 24.9211, 67.0327),
    ("Liaquat National Hospital", 24.8935, 67.0780),
    ("Indus Hospital Korangi", 24.8170, 67.1430),
    ("Ziauddin Hospital North Nazimabad", 24.9370, 67.0410),
    ("Jinnah Hospital Landhi", 24.8520, 67.1900),
    ("Sindh Govt Hospital New Karachi", 24.9780, 67.0660),
]

# (name, short_code, lat, lon, ambulance_count)
STATIONS: list[tuple[str, str, float, float, int]] = [
    ("Saddar Station", "SAD", 24.8570, 67.0250, 8),
    ("Lyari Station", "LYA", 24.8700, 66.9950, 6),
    ("Clifton Station", "CLF", 24.8200, 67.0330, 5),
    ("Liaquatabad Station", "LQB", 24.9030, 67.0420, 7),
    ("North Karachi Station", "NKR", 24.9850, 67.0600, 7),
    ("Orangi Station", "ORG", 24.9480, 66.9830, 7),
    ("SITE Station", "SIT", 24.8930, 66.9930, 6),
    ("Gulshan Station", "GUL", 24.9190, 67.0980, 8),
    ("Korangi Station", "KOR", 24.8460, 67.1300, 8),
    ("Malir Station", "MLR", 24.8940, 67.2050, 6),
]
