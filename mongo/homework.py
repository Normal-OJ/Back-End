from . import engine

#todo: need course field 
class HomeWork:
    
    @staticmethod
    def add_hw_in_course(course_id,hw_id,start,end,problemIds):  
        homework = engine.Homework(homeworkId=hw_id,
                                   courseId = course_id,
                                   problemIds = problemIds
                                  );
        homework.duration.start = start;
        homework.duration.end = end;
        homework.save();
        course = engine.Course(course_id=course_id,course_status=0).first();
        course.homework_ids.append(hw_id);       
        course.save();
        return homework;

    @staticmethod
    def update_hw_in_course(course_id,hw_id,start,end,problemIds):
        homework = engine.Homework.objects(course_id=course_id,
                                 homeworkId = hw_id,
                                 ).first();
        homework.problemIds = problemIds;
        homework.duration.start = start;
        homework.duration.end = end;
        homework.save();
        return homework;

    @staticmethod
    def delete_hw_in_course(course_id,start,end,hw_id,problemIds):
        homework = engine.Homework.objects(course_id=course_id,
                                 homeworkId = hw_id,
                                 ).first();
        homework.duration.start = start;
        homework.duration.end = end;
        for id in problemIds:
            homework.problemIds.remove(id);
            pass       
        homework.save();
        return homework;



