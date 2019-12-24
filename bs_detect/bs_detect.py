import subprocess
class bad_smell_detection:
    
    pylint_args=[]
    cppcheck_args=[]

    @staticmethod
    def set_settings():
        pass
    
    @staticmethod
    def detect(code_filename , language_type , time_limit):
        command = []
        if language_type == "python3":
            command.append("pylint")
            
        elif language_type == "c_cpp":
            command.append("cppcheck")
        subprocess.Popen()