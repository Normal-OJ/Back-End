import pytest
import bs_detect
import subprocess
bs = bs_detect.BSDetect()


def test_pylint_failed():
    route = "./tests/bs_detect_sample/one_line_a_plus_b.py"
    status, responese_str = bs.detect(route, "pylint", 3)
    assert status == False


def test_pylint_success():
    route = "./tests/bs_detect_sample/good_coding_style.py"
    status, responese_str = bs.detect(route, "pylint", 3)
    assert status == True


def test_cppcheck_failed():
    route = "./tests/bs_detect_sample/dirty_c_code.c"
    status, responese_str = bs.detect(route, "cpp_checkers", 3)
    assert status == False


def test_cppcheck_success():
    route = "./tests/bs_detect_sample/good_coding_style.cpp"
    status, responese_str = bs.detect(route, "pylint", 3)
    assert status == True


def test_set_settings():
    route = "./tests/bs_detect_sample/one_line_a_plus_b.py"
    nbs = bs_detect.BSDetect()
    nbs.set_settings("pylint", "shutUp")
    status, responese_str = nbs.detect(route, "pylint", 3)
    assert status == True


def test_time_out_exception():
    route = "./tests/bs_detect_sample/one_line_a_plus_b.py"
    excpt = False
    try:
        status, responese_str = bs.detect(route, "pylint", 0.0001)
    except subprocess.TimeoutExpired:
        excpt = True
    assert excpt


if __name__ == "__main__":
    test_pylint_failed()
    test_pylint_success()
    test_cppcheck_success()
    test_cppcheck_failed()
    test_set_settings()
    test_time_out_exception()
