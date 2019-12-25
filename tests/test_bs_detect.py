import pytest
import bs_detect
bs=bs_detect.BSDetect()
def test_pylint_failed():
    route = "./tests/bs_detect_sample/one_line_a_plus_b.py"
    expect_str=""
    with open(route+".ans" , "r") as f:
        for line in f.readlines():
            expect_str += line
    
    status , responese_str = bs.detect( route , "pylint" , 3)
    assert status == False
    assert responese_str == expect_str

def test_pylint_success():
    route = "./tests/bs_detect_sample/good_coding_style.py"
    expect_str=""
    with open(route+".ans" , "r") as f:
        for line in f.readlines():
            expect_str += line
    
    status , responese_str = bs.detect( route , "pylint" , 3)
    assert status == True
    assert responese_str == expect_str
    
def test_cppcheck_failed():
    route = "./tests/bs_detect_sample/dirty_c_code.c"
    expect_str=""
    with open(route+".ans" , "r") as f:
        for line in f.readlines():
            expect_str += line
    
    status , responese_str = bs.detect( route , "c&cpp_checkers" , 3)
    assert status == False
    assert responese_str == expect_str

def test_cppcheck_success():
    route = "./tests/bs_detect_sample/good_coding_style.cpp"
    expect_str=""
    with open(route+".ans" , "r") as f:
        for line in f.readlines():
            expect_str += line
    
    status , responese_str = bs.detect( route , "pylint" , 3)
    assert status == True
    assert responese_str == expect_str

if __name__ == "__main__":
    test_pylint_failed()
    test_pylint_success()
    test_cppcheck_failed()
    test_pylint_success()