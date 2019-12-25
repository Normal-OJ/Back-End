import subprocess
import json
import sys
import os
__all__=[
    "bs_detect"
]
class bs_detect:
    __profile__={}
    __pylint_args__=[]
    __cppcheck_args__=[]

    def __init__(self):
        data=""
        with open("./.config/bs_detect.json") as f:
            line = f.readlines()
            while line != "":
                data += line
        
        try:
            self.__profile__ = json.loads(s=data)
            self.__pylint_args__ = self.profile["pylint"]["default"]
            self.__cppcheck_args__ = self.profile["cppcheck"]["default"]
        except json.JSONDecodeError:
            print("json file format error, use null config by default" , file=sys.stderr)
            self.__profile__ = {}
            self.__pylint_args__ = []
            self.__cppcheck_args__ = []
        except KeyError:
            print("missing default key in initialization, use null config by default", file=sys.stderr)
            self.__pylint_args__ = []
            self.__cppcheck_args__ = []

    @classmethod
    def set_settings(cls , detector_type , mode):
        try:
            cls.__pylint_args__=cls.__profile__[detector_type][mode]
        except KeyError:
            print("can not found matched detector or mode configuration" , file=sys.stderr)
                
    
    @classmethod
    def detect(cls,code_filename , detector_type , time_limit):
        command = []
        if detector_type == "python3":
            command.append("pylint")

            disable_item = "--disable="
            for item in cls.__pylint_args__:
                disable_item += item
                disable_item += ","
            if len(cls.__pylint_args__):
                disable_item = disable_item[:-1]
            command.append(disable_item)

        elif detector_type == "c_cpp":
            command.append("cppcheck")
            command.append(cls.__cppcheck_args__)
        else:
            raise KeyError("unexpected detector type:{0}".format(detector_type))
        
        process_read , process_write = os.pipe()
        process_read  = os.fdopen(process_read)
        process_write = os.fdopen(process_write)
        process = subprocess.Popen(command , stdout=process_write)
        process_read
        