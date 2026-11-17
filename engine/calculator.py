import math

from engine.specs import load_specs

SPECS = load_specs()
MM_PER_INCH = 25.4
EPSILON = 1e-9                                                     

def _pitch_entry(pitch_mm, specs = SPECS):
    for entry in specs["pitches"]:
        if math.isclose(entry["pitch_mm"], pitch_mm):
            return entry
    availabe = [entry["pitch_mm"] for entry in specs["pitches"]]
    raise ValueError(f"Unknown pitch {pitch_mm} mm. Available: {availabe}")


def fit_wall(width_m, height_m, specs=SPECS):
    if width_m <= 0 or height_m <= 0:
        raise ValueError("Wall width and height must be positive.")
    
    cabinet = specs["cabinet"]
    cols = math.floor(width_m * 1000 /  cabinet["width_mm"] + EPSILON)
    rows = math.floor(height_m * 1000 / cabinet["height_mm"] + EPSILON)
    if cols < 1 or rows < 1:
        raise ValueError(
            f"Wall is smaller than one cabinet ({cabinet['width_mm']} x {cabinet['height_mm']} mm)."
        )
    return cols, rows


def screen_size_mm(cols, rows, specs=SPECS):
    cabinet = specs["cabinet"]
    return cols * cabinet["width_mm"], rows * cabinet["height_mm"]


def area_m2(cols, rows, specs=SPECS):
    width_mm, height_mm = screen_size_mm(cols, rows, specs)
    return round(width_mm * height_mm / 1_000_000, 2)


def diagonal_inches(cols, rows, specs=SPECS):
    width_mm, height_mm = screen_size_mm(cols, rows, specs)
    return round(math.hypot(width_mm, height_mm) / MM_PER_INCH)


def resolution(cols, rows, pitch_mm, specs=SPECS):
    entry = _pitch_entry(pitch_mm, specs)
    return cols * entry["pixels_w"], rows * entry["pixels_h"]


def max_pitch_for_distance(viewing_distance_m, specs=SPECS):
    if viewing_distance_m <= 0:
        raise ValueError("Viewing distance must be positive.")
    factor = specs["viewing_distance_rule"]["max_pitch_mm_per_metre"]
    return viewing_distance_m * factor


def allowed_pitches(viewing_distance_m = None, specs = SPECS):
    pitches = [entry["pitch_mm"] for entry in specs["pitches"]]
    if viewing_distance_m is None:
        return pitches
    limit = max_pitch_for_distance(viewing_distance_m, specs)
    return [pitch for pitch in pitches if pitch <= limit + EPSILON]


def describe_grid(cols, rows, specs=SPECS):
    width_mm, height_mm = screen_size_mm(cols, rows, specs)
    return {
        "grid" : {"cols" : cols, "rows" : rows, "cabinets" : cols * rows},
        "size_mm" : {"width" : width_mm, "height" : height_mm},
        "area_m2" : area_m2(cols, rows, specs),
        "diagonal_inches" : diagonal_inches(cols, rows, specs),
    }


def recommend_screen(width_m, height_m, viewing_distance_m = None, specs = SPECS):
    cols, rows = fit_wall(width_m, height_m, specs)
    result = describe_grid(cols, rows, specs)

    width_mm, height_mm = screen_size_mm(cols, rows, specs)
    result["leftover_mm"] = {
        "width": round(width_m * 1000 - width_mm, 1),
        "height": round(height_m * 1000 - height_mm, 1)
    }

    if viewing_distance_m is not None:
        result["max_pitch_mm"] = max_pitch_for_distance(viewing_distance_m, specs)

    result["options"] = []
    for pitch in allowed_pitches(viewing_distance_m, specs):
        res_w, res_h = resolution(cols, rows, pitch, specs)
        result["options"].append({
            "pitch_mm": pitch, 
            "resolution": {"width": res_w, "height": res_h},
            "total_pixels": res_w * res_h, 
             }
        )
    return result


def _space_text(max_width_m, max_height_m):
    """Describe the user's space, e.g. '4 m wide and 2.5 m high'."""
    parts = []
    if max_width_m is not None:
        parts.append(f"{max_width_m:g} m wide")
    if max_height_m is not None:
        parts.append(f"{max_height_m:g} m high")
    return " and ".join(parts)


def options_for_resolution(target_width_px, target_height_px, viewing_distance_m = None, max_width_m = None, max_height_m = None, specs = SPECS):
    if target_width_px <= 0 or target_height_px <= 0:
        raise ValueError("Target resolution must be positive.")
    options = []
    for pitch in allowed_pitches(viewing_distance_m, specs):
        entry = _pitch_entry(pitch, specs)
        cols = math.ceil(target_width_px / entry["pixels_w"])
        rows = math.ceil(target_height_px / entry["pixels_h"])
        option = describe_grid(cols, rows, specs)
        res_w, res_h = resolution(cols, rows, pitch, specs)
        option["pitch_mm"] = pitch
        option["resolution"] = {"width": res_w, "height": res_h}
        option["total_pixels"] = res_w * res_h
        options.append(option)

    options.sort(key = lambda option: option["area_m2"])

    if max_width_m is not None or max_height_m is not None:
        for option in options:
            width_ok = max_width_m is None or option["size_mm"]["width"] <= max_width_m * 1000 + EPSILON
            height_ok = max_height_m is None or option["size_mm"]["height"] <= max_height_m * 1000 + EPSILON
            option["fits_space"] = width_ok and height_ok

        if options and not any(option["fits_space"] for option in options):
            smallest = options[0]["size_mm"]
            need_w = smallest["width"] / 1000
            need_h = smallest["height"] / 1000
            shortfall = []
            if max_width_m is not None and need_w > max_width_m + EPSILON:
                shortfall.append(f"{round(need_w - max_width_m, 3):g} m wider")
            if max_height_m is not None and need_h > max_height_m + EPSILON:
                shortfall.append(f"{round(need_h - max_height_m, 3):g} m taller")
                
            raise ValueError(
                f"No configuration reaches {target_width_px} x {target_height_px} pixels "
                f"in a space {_space_text(max_width_m, max_height_m)}. "
                f"The smallest screen that reaches it is {need_w:g} x {need_h:g} m, "
                f"so the space would need to be {' and '.join(shortfall)}."
            )
    return sorted(options, key = lambda option: option["area_m2"])


def get_specs(specs = SPECS):
    return specs