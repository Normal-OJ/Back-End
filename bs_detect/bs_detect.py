import subprocess
import time
import json
import sys
import os
__all__ = ["BSDetect"]


class BSDetect:
    """
        FreeBSD(Free Bad Smell Detection) is a static code analyzer , which currently

        supports C/C++ , Python3 . 
    """
    __profile__ = {}
    __pylint_args__ = []
    __cppcheck_args__ = []
    __clang_format_args__ = []
    __diff_args__ = []

    def __init__(self):
        """
            Read bs_detect.json inside the .config folder and initialize the parameter,

            if any required key in the config file was missing , use None as config
        """
        data = ""
        with open("./.config/bs_detect.json") as f:
            lines = f.readlines()
            for line in lines:
                data += line
        try:
            self.__profile__ = json.loads(s=data)
            self.__pylint_args__ = self.__profile__["pylint"]["default"]
            self.__cppcheck_args__ = self.__profile__["cpp_checkers"][
                "default"]["cppcheck"]
            self.__clang_format_args__ = self.__profile__["cpp_checkers"][
                "default"]["clang-format"]
            self.__diff_args__ = self.__profile__["cpp_checkers"]["default"][
                "diff"]

        except json.JSONDecodeError:
            print("json file format error, use null config by default",
                  file=sys.stderr)
            self.__profile__ = {}
            self.__pylint_args__ = []
            self.__cppcheck_args__ = []
            self.__clang_format_args__ = []
            self.__diff_args__ = []
        except KeyError:
            print(
                "missing default key in initialization, use null config by default",
                file=sys.stderr)
            self.__pylint_args__ = []
            self.__cppcheck_args__ = []
            self.__clang_format_args__ = []
            self.__diff_args__ = []

    def set_settings(self, detector_type, mode):
        """
            and api for adjust configuration

            Parameter:

            detector_type: the type of detector(ex:pylint)

            mode: the mode to be loaded(ex:inferno)

            Return Vaule:

            None
        """
        try:
            if detector_type == "pylint":
                self.__pylint_args__ = self.__profile__[detector_type][mode]
            elif detector_type == "cpp_checkers":
                self.__cppcheck_args__ = self.__profile__[detector_type][mode][
                    "cppcheck"]
                self.__clang_format_args__ = self.__profile__[detector_type][
                    mode]["clang-format"]
                self.__diff_args__ = self.__profile__[detector_type][mode][
                    "diff"]
        except KeyError:
            print("can not found matched detector or mode configuration",
                  file=sys.stderr)

    @staticmethod
    def __command_runner__(command, args, time_limit):
        full_command = []
        full_command.append(command)
        for arg in args:
            full_command.append(arg)
        process = subprocess.Popen(full_command, stdout=subprocess.PIPE)
        try:
            cur = time.time()
            p = process.communicate(timeout=time_limit)[0]
            result = bytes(p).decode()
            return result, time.time() - cur
        except subprocess.TimeoutExpired:
            process.kill()
            raise subprocess.TimeoutExpired(full_command, time_limit)

    def __python_checker__(self, code_filename, time_limit):
        command_args = []
        disable_item = "--disable="
        for item in self.__pylint_args__:
            disable_item += item
            disable_item += ","
        if len(self.__pylint_args__):
            disable_item = disable_item[:-1]
        command_args.append(disable_item)
        command_args.append(code_filename)
        # run bad smell detection & set up timer
        result, _ = self.__command_runner__("pylint", command_args, time_limit)
        return len([
            line
            for line in result.splitlines() if str(line).strip("\n ") != ""
        ]) <= 2, result

    def __c_checker__(self, code_filename, time_limit):
        report = {}
        # cppcheck
        cppcheck_args = [code_filename]
        for arg in self.__cppcheck_args__:
            cppcheck_args.append(arg)

        result, use_time = self.__command_runner__("cppcheck", cppcheck_args,
                                                   time_limit)
        report.update({"cppcheck": result})
        time_limit -= use_time

        #  clang-format
        clang_format_args = [code_filename]

        for arg in self.__clang_format_args__:
            clang_format_args.append(arg)
        result, use_time = self.__command_runner__("clang-format",
                                                   clang_format_args,
                                                   time_limit)
        time_limit -= use_time

        # create tmp files
        filename = os.path.basename(code_filename)
        with open("/tmp/{0}".format(filename), "w+") as f:
            f.write(result)

        # diff
        diff_args = [code_filename, "/tmp/{0}".format(filename)]
        for arg in self.__diff_args__:
            diff_args.append(arg)
        result, _ = self.__command_runner__("diff", diff_args, time_limit)
        formated_result = ""
        if result != "":
            result = result.splitlines()[2:]
            for line in result:
                formated_result += line
                formated_result += "\n"
            formated_result = formated_result[:-1]
        # export result
        os.remove("/tmp/{0}".format(filename))
        report.update({"clang-format": formated_result})
        formated_report = "cppcheck:\n{0}\n".format(
            report["cppcheck"]) + "clang-format:\n{0}\n".format(
                report["clang-format"])
        return report["cppcheck"] == "" and report[
            "clang-format"] == "", formated_report

    def detect(self, code_filename, detector_type, time_limit):
        """
            the trigger to run detection task .if its runtime exceeed time_limit ,

            it will raise a subprocess.TimeoutExpired exception.

            Parameter:

            code_filename: input file

            detector_type: the type of detector

            time_limit: the time limit of this function
        """
        if detector_type == "pylint":
            return self.__python_checker__(code_filename, time_limit)

        elif detector_type == "cpp_checkers":
            return self.__c_checker__(code_filename, time_limit)
        else:
            raise KeyError(
                "unexpected detector type:{0}".format(detector_type))
