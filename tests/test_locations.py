import re

from modules.locations import _countries, country_names, state_names


def test_country_list_basics():
    names = country_names()
    assert 240 <= len(names) <= 260 and names == sorted(names)
    for expected in ("United States", "India", "Germany", "China", "Bangladesh", "South Korea",
                     "Vietnam", "Russia", "Turkey"):
        assert expected in names
    assert "Korea, Republic of" not in names


def test_country_names_do_not_break_the_app_matching():
    from modules.places import canon_country
    assert canon_country("United States") == "United States"
    assert canon_country("India") == "India" and canon_country("Germany") == "Germany"


def test_us_states_are_50_plus_dc_and_no_territories():
    s = state_names("United States")
    assert len(s) == 51 and "Texas" in s and "District of Columbia" in s
    assert "Guam" not in s and "Puerto Rico" not in s


def test_india_and_germany_use_english_clean_names():
    india = state_names("India")
    assert "Karnataka" in india and "Maharashtra" in india and "Chandigarh" in india
    de = state_names("Germany")
    assert len(de) == 16
    assert "North Rhine-Westphalia" in de and "Saxony" in de and "Bavaria" in de
    assert "Nordrhein-Westfalen" not in de


def test_china_and_uae_cleanups():
    cn = state_names("China")
    assert "Guangdong" in cn and "Ningxia" in cn and "Beijing" in cn
    assert not any(n.endswith(" Sheng") or n.endswith(" Shi") for n in cn)
    assert "Dubai" in state_names("United Arab Emirates")


def test_uk_has_no_bracket_noise():
    assert "Wales" in state_names("United Kingdom")
    assert all("[" not in n for c in country_names() for n in state_names(c))


def test_every_region_name_is_clean_unique_and_ascii():
    for c in country_names():
        names = state_names(c)
        assert len(names) == len(set(names)), c
        for n in names:
            assert n and n == n.strip() and re.fullmatch(r"[A-Za-z0-9 .,'()/&-]+", n), (c, n)


def test_unknown_or_empty_country_has_no_regions():
    assert state_names(None) == [] and state_names("") == [] and state_names("Atlantis") == []


def test_countries_without_regions_return_a_list():
    assert isinstance(state_names("Vatican City"), list)
