from pathlib import Path
from zipfile import ZipFile
import pandas as pd
from re import findall, sub
from difflib import ndiff


def merge_folders(path_from: str, path_to: str):
    p = Path(path_from)
    Path(path_to).mkdir(parents=True, exist_ok=True)
    user_counter = 0
    for zip_path in p.glob('*.zip'):
        with ZipFile(zip_path) as zip_file:
            current_directory = "None"
            for zipinfo in zip_file.infolist():
                if current_directory not in zipinfo.filename:
                    user_counter += 1
                    current_directory = zipinfo.filename
                zipinfo.filename = f'user_{user_counter}{zipinfo.filename.removeprefix(current_directory[:-1])}'
                zip_file.extract(zipinfo, path_to)
        print("extracted: " + zip_file.filename)


def get_activity_tracker_df(path: Path) -> pd.DataFrame:
    cols_names = ['Timestamp', 'EventType', 'EventData', 'FocusedComponent', 'CurrentFile', 'EditorLine',
                  'EditorColumn']

    df_at_path = [path for path in path.rglob('*.csv') if 'ide-events' in path.stem][0]
    df_at = pd.read_csv(df_at_path, names=cols_names, header=None,
                        skipfooter=1, on_bad_lines='skip', engine='python')

    df_at = df_at.loc[df_at.CurrentFile != '*']
    df_at.Timestamp = pd.to_datetime(df_at.Timestamp)
    return df_at.reset_index(drop=True)


def get_task_tracker_df(path: Path, *, skipfooter: int = 1, nrows: int | None = None) -> pd.DataFrame:
    df_t_path = [path for path in path.rglob('*.csv') if 'ide-events' not in path.stem][0]
    df_t = pd.read_csv(df_t_path, skipfooter=skipfooter, nrows=nrows, on_bad_lines='skip',
                       engine='python')
    df_t.date = pd.to_datetime(df_t.date)
    df_t = df_t.loc[df_t.timestamp != 0, :]
    return df_t


def get_user_group(df_at: pd.DataFrame) -> list:
    filtered_df = df_at.drop_duplicates(subset='CurrentFile')
    return list(filtered_df.CurrentFile.apply(lambda x: int(x.removesuffix('.ipynb'))))


def get_user_data(path: Path) -> tuple:
    group = get_user_group(get_activity_tracker_df(path))
    df_t = get_task_tracker_df(path, skipfooter=0, nrows=10)
    row = df_t.iloc[-1]
    return row['email'], row['answers'], group, row['date']


def get_task_time(task: dict) -> pd.Timedelta:
    df_at = task['activity_tracker']
    task_name = task['name']

    df_at = df_at.loc[df_at.CurrentFile == f'{task_name}.ipynb']
    return pd.Timedelta(df_at.iloc[-1].Timestamp - df_at.iloc[0].Timestamp)


def count_events(task: dict) -> int:
    df_at = task['activity_tracker']
    task_name = task['name']

    df_at = df_at.loc[(df_at.CurrentFile == f'{task_name}.ipynb') & (df_at.EventType == 'Action')]
    return df_at.shape[0]


def get_snapshot(task: dict, index: int = -1) -> str:
    df_t = task['task_tracker']
    frg = sub('#%%[^>]+screen.\n#%%\n', '', df_t.iloc[index].fragment)
    return frg.replace('#%%\n', '')


def get_from_open_to_start_time(task: dict) -> pd.Timedelta:
    df_at = task['activity_tracker']
    df_t = task['task_tracker']
    task = task['name']

    open_time = df_at.loc[df_at.CurrentFile == f'{task}.ipynb'].iloc[0].Timestamp
    time_diff = df_t.loc[:, 'date'] - open_time
    return time_diff.iloc[0]


def get_row_average_time(task: dict) -> float:
    time_volume = get_task_time(task).total_seconds()
    return time_volume / get_rows_count(task)


def get_brutto_coding_speed(task: dict) -> float:
    df_t = task['task_tracker']
    first_row = df_t.iloc[0]
    time_volume = get_task_time(task).total_seconds()
    return (df_t.shape[0] - first_row.name - 1) / time_volume


def get_netto_coding_speed(task: dict) -> float:
    time_volume = get_task_time(task).total_seconds()
    fragment_size = len(get_snapshot(task))
    return fragment_size / time_volume


def get_edits_count(task: dict) -> float:
    df_t = task['task_tracker']
    df_t['frag_len'] = df_t.fragment.apply(len)
    edit_counter = sum(df_t.frag_len < df_t.frag_len.shift(1))
    return edit_counter


def get_rows_count(task: dict) -> int:
    fragment = get_snapshot(task).strip()
    return len(findall('\n', fragment)) + 1  # adding last row without \n to counter


def get_start_task_time(df_at: pd.DataFrame, task: str) -> pd.Timestamp:
    task_df_at = df_at.loc[df_at.CurrentFile == f'{task}.ipynb', :]
    return task_df_at.iloc[0].Timestamp


def count_diffs(task: dict) -> int:
    before = get_snapshot(task, 0)
    after = get_snapshot(task)
    diff = ndiff(before.splitlines(keepends=True), after.splitlines(keepends=True))
    diff = ''.join(diff)
    return diff.count("\n?")


def count_fixed_bugs(task: dict) -> int:
    fragment, bugs = task['task_tracker'].iloc[-1].fragment, task['bugs']
    return _count_fixed_bugs(fragment, bugs)


def _count_fixed_bugs(fragment: str, bugs: dict) -> int:
    ans = 0
    for b, c in bugs.items():
        if fragment.count(b) != c:
            ans += 1
    return ans


def get_first_bug_time(task: dict) -> pd.Timedelta:
    df_t, df_at, task, bugs = task['task_tracker'], task['activity_tracker'], task['name'], task['bugs']
    time = get_start_task_time(df_at, task)
    rows_first_bug_df = df_t.loc[df_t['fragment'].apply(lambda x: _count_fixed_bugs(x, bugs) == 1)]
    return pd.Timedelta(rows_first_bug_df.iloc[0].date - time)


task_list = {'Coding': [('time', get_task_time), ('events_count', count_events), ('snapshot', get_snapshot),
                        ('first_symbol_time', get_from_open_to_start_time), ('time_for_row', get_row_average_time),
                        ('edits', get_edits_count), ('rows', get_rows_count),
                        ('coding_speed_all', get_brutto_coding_speed), ('coding_speed_result', get_netto_coding_speed)],
             'Debugging': [('time', get_task_time), ('diffs', count_diffs), ('fixed_bugs', count_fixed_bugs),
                           ('events_count', count_events), ('first_bug_time', get_first_bug_time),
                           ('snapshot', get_snapshot)]}


def generate_flat_mapping(task_list: dict):
    flat_mapping = []
    for ttype in task_list.keys():
        for task in task_list[ttype]:
            tasks = list(task)
            tasks.append(ttype)
            flat_mapping.append(tasks)
    return flat_mapping
