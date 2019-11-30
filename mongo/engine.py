from mongoengine import *

connect('normal-oj', host='mongo')


class Profile(EmbeddedDocument):
    displayed_name = StringField(db_field='displayedName',
                                 required=True,
                                 max_length=16)
    bio = StringField(max_length=64, required=True, default='')


class EditorConfig(EmbeddedDocument):
    font_size = IntField(db_field='fontSize',
                         min_value=8,
                         max_value=72,
                         default=14)
    theme = StringField(default='default',
                        choices=[
                            "default", "base16-dark", "base16-light",
                            "dracula", "eclipse", "material", "monokai"
                        ])
    indent_type = IntField(db_field='indentType', default=1, choices=[0, 1])
    tab_size = IntField(db_field='tabSize',
                        default=4,
                        min_value=1,
                        max_value=8)
    language = IntField(default=0, choices=[0, 1, 2])


class User(Document):
    user_id = StringField(db_field='userId',
                          max_length=24,
                          required=True,
                          unique=True)
    username = StringField(max_length=16, required=True, unique=True)
    email = EmailField(required=True, unique=True)
    active = BooleanField(default=False)
    role = IntField(default=2, choices=[0, 1, 2])
    profile = EmbeddedDocumentField(Profile, default=Profile, null=True)
    editor_config = EmbeddedDocumentField(EditorConfig,
                                          db_field='editorConfig',
                                          default=EditorConfig,
                                          null=True)
    # contest_id = ReferenceField('Contest', db_field='contestId')
    course_ids = ListField(ReferenceField('Course'), db_field='courseIds')
    # submission_ids = ListField(ReferenceField('Submission'), db_field='submissionIds')


class Course(Document):
    course_id = StringField(db_field='courseId',
                            max_length=24,
                            required=True,
                            unique=True)
    course_status = IntField(default=0, choices=[0, 1])
    course_name = StringField(max_length=64, required=True, unique=True)
    teacher_id = ReferenceField('User', db_field='teacherId')
    ta_ids = ListField(ReferenceField('User'), db_field='taIds')
    #students: {
    #    userId: { "studentName": String },
    #    ...
    #},
    # contest_ids = ListField(ReferenceField('Contest'), db_field='contestIds')
    # homework_ids = ListField(ReferenceField('Homework'), db_field='homeworkIds')
    # announcement_ids = ListField(ReferenceField('Announcement'), db_field='announcementIds')
    # post_ids = ListField(ReferenceField('Post'), db_field='postIds')
