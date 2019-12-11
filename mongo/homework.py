from . import engine

#todo: need course field 
class HomeWork:
    
    @staticmethod
    def add_hw(course_name,hw_name,start,end,problemIds,participants):
        # course = engine.Course.objects(course_name =course_name).first()
        # courseId = course.id
        homework = engine.Homework(homeworkName=hw_name,
                                   courseId = '1',
                                   problemIds = problemIds
                                  )
        homework.duration.start = start
        homework.duration.end = end
        #init student status         
        userIds = {}
        userProblems = {}
        for problemId in problemIds:
            userProblems[str(problemId)] =  {"score": 0,"problemStatus":1,"submissonIds":[]}

        for userid in participants:
            userIds[str(userid)] = userProblems        

        homework.studentStatus = userIds
        homework.save()
        #get homeworkId then store in the correspond course
        # course = engine.Course.objects(courseId=courseId).first()
        # course.homework_ids.append(homeworkId)     
        # course.save()
        return homework

    @staticmethod
    def update(course_name,hw_name,start,end,problemIds,participants):
        # course = engine.Course.objects(course_name =course_name).first()
        # courseId = course.id
        homework = engine.Homework.objects(courseId=1,
                                 homeworkName = hw_name,
                                 ).first()
        homework.problemIds = problemIds
        homework.duration.start = start
        homework.duration.end = end
        homework.save()
        return homework

     #delete  problems/paticipants in hw
    @staticmethod
    def delete_problems(course_name,hw_name,start,end,problemIds,participants):
        # course = engine.Course.objects(course_name =course_name).first();
        # courseId = course.id
        homework = engine.Homework.objects(courseId=1,
                                 homeworkName=hw_name,                                 
                                 start = start,
                                 end = end
                                 ).first()
        studentStatus = homework.studentStatus
        for userId in participants:
            studentStatus.pop(str(userId))

        for id in problemIds:
            homework.problemIds.remove(id)
            pass       
        homework.save()
        return homework

    #delete hw in a course
    @staticmethod
    def delete_hw(course_name,hw_name,start,end,hw_id,problemIds):
        # course = engine.Course.objects(course_name =course_name).first()
        # courseId = course.id
        homework = engine.Homework.objects(courseId=1,
                                 homeworkName=hw_name,
                                 start = start,
                                 end = end
                                 ).first()
        homeworkId = homework.id           
        course.homework_ids.remove(homeworkId)
        homework.delete()                          

    @staticmethod
    def get_homeworks(course_name):
        # course = engine.Course.objects(course_name =course_name).first()
        # courseId = course.id
        homeworks = engine.Homework.objects(courseId=1)
        return homeworks

    @staticmethod
    def get_signal_homework(id):
        homework = engine.Homework.objects(id = id).first()
        return homework


