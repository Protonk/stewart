def latest_readings(readings):
    """Return one reading per sensor, keyed by sensor name."""
    latest = {}
    for reading in readings:
        sensor = reading["sensor"]
        previous = latest.get(sensor)
        if previous is None or reading["timestamp"] > previous["timestamp"]:
            latest[sensor] = reading
    return latest
