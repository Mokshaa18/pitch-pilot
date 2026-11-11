import pytest

from engine.calculator import (
    allowed_pitches,
    area_m2,
    diagonal_inches,
    fit_wall,
    max_pitch_for_distance,
    options_for_resolution,
    recommend_screen,
    resolution,
    screen_size_mm
)

from engine.specs import load_specs


#Specs

def test_specs_load_with_five_pitches():
    specs = load_specs()
    assert specs["cabinet"] == {"width_mm": 600, "height_mm": 337.5}
    assert len(specs["pitches"]) == 5


#Values copied from reference table

@pytest.mark.parametrize(
    "n, pitch, expected",
    [
        (2, 0.625, (1920, 1080)),
        (3, 0.9375, (1920, 1080)),
        (4, 1.25, (1920, 1080)),
        (5, 1.5625, (1920, 1080)),
        (6, 1.875, (1920, 1080)),
        (4, 0.625, (3840, 2160)),
        (6, 0.9375, (3840, 2160)),
        (8, 1.25, (3840, 2160)),
        (10, 1.5625, (3840, 2160)),
        (12, 1.875, (3840, 2160)),
        (8, 0.625, (7680, 4320)),
        (12, 0.9375, (7680, 4320)),
        (7, 1.5625, (2688, 1512)),
        (9, 0.9375, (5760, 3240)),
        (11, 1.25, (5280, 2970)),
    ],
)
def test_resolution_matches_table(n, pitch, expected):
    assert resolution(n, n, pitch) == expected


@pytest.mark.parametrize(
    "n, expected_mm",
    [(2, (1200, 675)), (7, (4200, 2362.5)), (10, (6000, 3375)), (12, (7200, 4050))],
)
def test_screen_size_matches_table(n, expected_mm):
    assert screen_size_mm(n, n) == expected_mm


@pytest.mark.parametrize(
    "n, expected",
    [(2, 0.81), (3, 1.82), (5, 5.06), (7, 9.92), (10, 20.25), (12, 29.16)]
)
def test_area_matches_table(n, expected):
    assert area_m2(n, n) == expected


@pytest.mark.parametrize(
    "n, expected",
    [(2, 54), (5, 136), (8, 217), (10, 271), (12, 325)],
)
def test_diagonal_matches_table(n, expected):
    assert diagonal_inches(n, n) == expected


#Cases

def test_non_square_grid():
    #6 cols x 384 px = 2304, 7 rows x 216 px = 1512
    assert resolution(6, 7, 1.5625) == (2304, 1512)


def test_fit_wall_basic():
    # 6000/600 = 10 cols, 3400 / 337.5 = 10.07 -> 10 rows
    assert fit_wall(6, 3.4) == (10, 10)


def test_fit_wall_rounds_down_partial_cabinets():
    #6350 / 600 = 10.58 -> 10 cols
    assert fit_wall(0.6, 0.3375) == (1, 1)


def test_fit_wall_exact_one_cabinet():
    #Needs EPSILON to avoid 0.9999.. -> 0
    assert fit_wall(0.6, 0.3375) == (1, 1)

@pytest.mark.parametrize("width, height", [(0.5, 1.0), (1.0, 0.3), (0, 1), (-2, 1)])
def test_fit_wall_rejects_too_small_or_invalid(width, height):
    with pytest.raises(ValueError):
        fit_wall(width, height)


#Viewing distance rule

def test_max_pitch_for_distance():
    assert max_pitch_for_distance(3) == 3.0


def test_far_viewing_allows_all_pitches():
    assert allowed_pitches(3) == [1.875, 1.5625, 1.25, 0.9375, 0.625]


def test_close_viewing_allows_only_fine_pitches():
    assert allowed_pitches(1) == [0.9375, 0.625]


def test_too_case_allows_none():
    assert allowed_pitches(0.5) == []


def test_no_distance_allows_all_pitches():
    assert len(allowed_pitches()) == 5


#Rules to always hold
@pytest.mark.parametrize(
    "width, height",
     [(6, 3.4), (4, 2.5), (2.4, 1.35), (7.9, 4.4), (1.25, 0.7)],
)
def test_grid_fits_and_is_largest_possible(width, height):
    cols, rows = fit_wall(width, height)
    width_mm, height_mm = screen_size_mm(cols, rows)
    assert width_mm <= width * 1000 and height_mm <= height * 1000
    assert(cols + 1) * 600 > width * 1000
    assert(rows + 1) * 337.5 > height * 1000


#Combined functions

def test_recommend_screen_6_by_3_4_at_3m():
    result = recommend_screen(6, 3.4, 3)
    assert result["grid"] == {"cols": 10, "rows": 10, "cabinets": 100}
    assert result["size_mm"] == {"width": 6000, "height": 3375}
    assert result["leftover_mm"] == {"width": 0.0, "height": 25.0}
    assert result["max_pitch_mm"] == 3.0
    assert len(result["options"]) == 5
    assert{"pitch_mm": 1.5625, "resolution": {"width": 3840, "height": 2160}} in result["options"]


def test_options_for_4k_at_1m():
    options = options_for_resolution(3840, 2160, viewing_distance_m= 1)
    assert[o["pitch_mm"] for o in options] == [0.625, 0.9375]


def test_options_for_4k_match_table():
    options = options_for_resolution(3840, 2160)
    grids = {o["pitch_mm"]: (o["grid"]["cols"], o["grid"]["rows"]) for o in options}
    assert grids == {1.875: (12, 12), 1.5625: (10, 10), 1.25: (8, 8), 0.9375: (6, 6), 0.625: (4, 4)}
    assert options[0]["pitch_mm"] == 0.625


def test_options_reject_invalid_target():
    with pytest.raises(ValueError):
        options_for_resolution(0, 2160)