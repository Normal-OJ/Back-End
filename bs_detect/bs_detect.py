import subprocess
import time
import json
import sys
import os
__all__=[
    "BSDetect"
]
class BSDetect:
    __profile__={}
    __pylint_args__=[]
    __cppcheck_args__=[]
    __clang_format_args__=[]
    __diff_args__=[]

    def __init__(self):
        data=""
        with open("./.config/bs_detect.json") as f:
            lines = f.readlines()
            for line in lines:
                data += line
        try:
            self.__profile__ = json.loads(s=data)
            self.__pylint_args__ = self.__profile__["pylint"]["default"]
            self.__cppcheck_args__ = self.__profile__["c&cpp_checkers"]["default"]["cppcheck"]
            self.__clang_format_args__ = self.__profile__["c&cpp_checkers"]["default"]["clang-format"]
            self.__diff_args__ = self.__profile__["c&cpp_checkers"]["default"]["diff"]

        except json.JSONDecodeError:
            print("json file format error, use null config by default" , file=sys.stderr)
            self.__profile__ = {}
            self.__pylint_args__ = []
            self.__cppcheck_args__ = []
            self.__clang_format_args__ = []
            self.__diff_args__ = []
        except KeyError:
            print("missing default key in initialization, use null config by default", file=sys.stderr)
            self.__pylint_args__ = []
            self.__cppcheck_args__ = []
            self.__clang_format_args__ = []
            self.__diff_args__ = []
    
    def set_settings(self , detector_type , mode):
        try:
            if detector_type == "pylint":
                self.__pylint_args__=self.__profile__[detector_type][mode]
            elif detector_type == "c&cpp_checkers":
                self.__cppcheck_args__     = self.__profile__[detector_type][mode]["cppcheck"]
                self.__clang_format_args__ = self.__profile__[detector_type][mode]["clang-format"]
                self.__diff_args__         = self.__profile__[detector_type][mode]["diff"]
        except KeyError:
            print("can not found matched detector or mode configuration" , file=sys.stderr)
    
    @staticmethod
    def command_runner(command , args ,time_limit):
        full_command = []
        full_command.append(command)
        for arg in args:
            full_command.append(arg)
        process = subprocess.Popen(full_command, stdout= subprocess.PIPE)
        try:
            cur = time.time()
            p = process.communicate(timeout=time_limit)[0]
            result = bytes(p).decode()
            return result , time.time() - cur 
        except TimeoutError:
            process.kill()
            raise TimeoutError

    
    def python_checker(self , code_filename , time_limit):
        command_args=[]
        disable_item = "--disable="
        for item in self.__pylint_args__:
            disable_item += item
            disable_item += ","
        if len(self.__pylint_args__):
            disable_item = disable_item[:-1]
        command_args.append(disable_item)
        command_args.append(code_filename)
        # run bad smell detection & set up timer
        try:
            result , _ = self.command_runner("pylint" , command_args ,time_limit)
        except TimeoutError:
            print("waiting too long for python bad smelling , wait for over {0} second(s)".format(str(time_limit)) , file = sys.stderr)
            raise TimeoutError
        return len([ line for line in result.splitlines() if str(line).strip("\n ") != "" ]) <= 2 , result
    
    def c_checker(self , code_filename , time_limit):
        report = {}
        # cppcheck
        cppcheck_args = [ code_filename ]
        for arg in self.__cppcheck_args__:
            cppcheck_args.append(arg)
        try:
            result , use_time = self.command_runner("cppcheck" , cppcheck_args ,time_limit)
        except TimeoutError:
            print("wait too long for cppcheck , wait for over {0} seccond(s)".format(str(time_limit)) , file = sys.stderr )
        report.update({
            "cppcheck" : result
        })
        time_limit -= use_time

        #  clang-format
        clang_format_args = [ code_filename ]

        for arg in self.__clang_format_args__:
            clang_format_args.append(arg)
        try:
            result , use_time = self.command_runner("clang-format" , clang_format_args ,time_limit)
        except TimeoutError:
            print("wait too long for cppcheck , wait for over {0} seccond(s)".format(str(time_limit)) , file = sys.stderr )
        time_limit -= use_time

        # create tmp files
        filename = os.path.basename(code_filename)
        with open("/tmp/{0}".format(filename) , "w+") as f:
            f.write(result)
        
        # diff
        diff_args = [ code_filename ,"/tmp/{0}".format(filename) ]
        for arg in self.__diff_args__:
            diff_args.append(arg)
        try:
            result , _ = self.command_runner("diff" , diff_args , time_limit)
        except TimeoutError:
            print("wait too long for diff , wait for over {0} seccond(s)".format(str(time_limit)) , file = sys.stderr )
        formated_result = ""
        if result != "":
            result = result.splitlines()[2:]
            for line in result:
                formated_result += line
                formated_result += "\n"
            formated_result = formated_result[:-1]
        # export result
        os.remove("/tmp/{0}".format(filename))
        report.update({
            "clang-format":formated_result
        })
        formated_report = "cppcheck:\n{0}\n".format(report["cppcheck"]) + "clang-format:\n{0}\n".format(report["clang-format"])
        return report["cppcheck"] == "" and report["clang-format"] == "" , formated_report

    
    def detect(self,code_filename , detector_type , time_limit):
        if detector_type == "pylint":
            return self.python_checker(code_filename , time_limit)

        elif detector_type == "c&cpp_checkers":
            return self.c_checker(code_filename , time_limit)
        else:
            raise KeyError("unexpected detector type:{0}".format(detector_type))