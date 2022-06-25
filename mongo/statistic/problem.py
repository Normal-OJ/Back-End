from typing import Dict
from mongo import engine


class ProblemStatistic:
    def __init__(self, problem) -> None:
        self.problem = problem

    def get_submission_status(self) -> Dict[str, int]:
        pipeline = {
            "$group": {
                "_id": "$status",
                "count": {
                    "$sum": 1
                },
            }
        }
        cursor = engine.Submission.objects(problem=self.problem.id).aggregate(
            [pipeline])
        return {item['_id']: item['count'] for item in cursor}

    def get_ac_user_count(self) -> int:
        ac_users = engine.Submission.objects(
            problem=self.problem.id,
            status=0,
        ).distinct('user')
        return len(ac_users)

    def get_tried_user_count(self) -> int:
        tried_users = engine.Submission.objects(
            problem=self.problem.id).distinct('user')
        return len(tried_users)
