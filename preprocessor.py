from json import load
from pathlib import Path
from natsort import natsorted
import util


class Preprocessor:
    def __init__(self, user_path: Path):
        self.user_path = user_path

    def read_tasks(self) -> list[dict]:
        self.tasks = []
        df_activity_tracker = util.get_activity_tracker_df(self.user_path)
        bugs = self._read_bugs()
        sorted_tasks = natsorted([f for f in self.user_path.glob('*/') if f.is_dir()], key=str)

        for task_path in sorted_tasks:
            df_task_tracker = util.get_task_tracker_df(task_path)
            self.tasks.append({'name': task_path.name,
                               'type': self._get_task_type(task_path.name),
                               'task_tracker': df_task_tracker,
                               'activity_tracker': df_activity_tracker,
                               'bugs': self._get_bugs_dict(bugs, task_path.name)})

        return self.tasks

    def _get_task_type(self, task: str) -> str:
        if int(task) in range(0, 4):
            return 'Coding'
        return 'Debugging'

    def get_user_info(self) -> dict:
        user_info = util.get_user_data(self.user_path)
        return {'email': user_info[0], 'answers': user_info[1], 'group': user_info[2], 'date': user_info[3]}

    def calculate_features(self, task: dict) -> dict:

        task_features = dict()
        feature_mapping = util.generate_flat_mapping(util.task_list)
        for feature in feature_mapping:
            if feature[2] == task['type']:
                task_features[feature[0]] = feature[1](task)

        return task_features

    def _get_bugs_dict(self, bugs: list, task: str) -> dict:
        if int(task) in range(0, 4):
            return None
        elif int(task) in range(4, 6):
            return bugs[0]
        else:
            return bugs[1]

    def _read_bugs(self):
        with open('bugs.json') as f:
            return load(f)
