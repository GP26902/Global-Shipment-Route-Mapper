from modules import security


def test_code_format_and_uniqueness():
    codes = {security.new_delete_code() for _ in range(200)}
    assert len(codes) == 200
    c = next(iter(codes))
    assert len(c) == 14 and c.count("-") == 2
    assert not set(c.replace("-", "")) & set("01OIL")


def test_hash_roundtrip_and_no_plaintext():
    code = security.new_delete_code()
    stored = security.hash_code(code)
    assert code not in stored and "$" in stored
    assert security.verify_code(code, stored)


def test_verify_is_forgiving_about_case_and_dashes_but_not_wrong_codes():
    code = "7KQ2-M9XA-C4TH"
    stored = security.hash_code(code)
    assert security.verify_code("7kq2m9xac4th", stored)
    assert not security.verify_code("7KQ2-M9XA-C4TJ", stored)
    assert not security.verify_code("", stored)
    assert not security.verify_code(code, "")
    assert not security.verify_code(code, "garbage")


def test_same_code_gets_different_salts():
    assert security.hash_code("ABCD-EFGH-JKMN") != security.hash_code("ABCD-EFGH-JKMN")


def test_admin_password():
    assert security.check_admin_password("secret", "secret")
    assert not security.check_admin_password("wrong", "secret")
    assert not security.check_admin_password("", "")
    assert not security.check_admin_password("x", "")


def test_attempt_limit():
    assert not security.attempts_exhausted(4)
    assert security.attempts_exhausted(5)
