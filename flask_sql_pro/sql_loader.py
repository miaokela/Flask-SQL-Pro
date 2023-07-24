import os
import threading
import typing

import yaml
import jinja2


class GlobalData:
    sql_group = {}


class Loader:
    loader = None


class SingletonType(type):
    _instance_lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            with SingletonType._instance_lock:
                if not hasattr(cls, "_instance"):
                    cls._instance = super(SingletonType, cls).__call__(*args, **kwargs)
        return cls._instance


class SqlLoader(metaclass=SingletonType):
    """
    The sql_id is used to read the sql corresponding to the key in the specified yml file
    """

    SQL_FILE_PATH = None
    page_param = None
    page_size_param = None

    def __init__(self):
        self.sql_data = SqlLoader.get_sql_data(self.SQL_FILE_PATH)

    @classmethod
    def preload_all_sqls(cls):
        """
        Preloac all sqls into memory
        """
        for _path, _, files in os.walk(cls.SQL_FILE_PATH):
            if os.path.samefile(_path, cls.SQL_FILE_PATH):  # root path
                for _f in files:
                    c_file = os.path.join(_path, _f)
                    c_file_name = _f.replace('.yml', '')

                    with open(c_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        sql_group = yaml.load(content, Loader=yaml.FullLoader)
                        if not sql_group:
                            continue

                        for _k in sql_group.keys():
                            _sql_id = '%s.%s' % (c_file_name, _k)
                            GlobalData.sql_group[_sql_id] = sql_group[_k]
                continue

            relative_path = _path.replace(cls.SQL_FILE_PATH, '')

            if relative_path.startswith(os.sep):
                relative_path = relative_path[1:]
            if relative_path.endswith(os.sep):
                relative_path = relative_path[:-1]

            prefix_sql_id = relative_path.replace(os.sep, '.')

            for _f in files:
                c_file = os.path.join(_path, _f)
                c_file_name = _f.replace('.yml', '')

                with open(c_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    sql_group = yaml.load(content, Loader=yaml.FullLoader)
                    if not sql_group:
                        continue

                    for _k in sql_group.keys():
                        _sql_id = '%s.%s.%s' % (prefix_sql_id, c_file_name, _k)
                        GlobalData.sql_group[_sql_id] = sql_group[_k]

        return True

    def get_sql(self, sql_id: str) -> str:
        if not hasattr(GlobalData, 'sql_group'):
            GlobalData.sql_group = {}
        if sql_id in GlobalData.sql_group:
            return GlobalData.sql_group[sql_id]
        else:
            sql = self.__load_sql(sql_id)
            GlobalData.sql_group[sql_id] = sql
            return sql

    def __load_sql(self, sql_id: str) -> str:
        # Find the file name and sql_id prefix based on the sql_id passed in
        sql_id_prefix = '.'.join(sql_id.split('.')[:-1])
        c_file = self.sql_data.get(sql_id_prefix)
        if not c_file:
            raise Exception('sql file not found')
        with open(c_file, 'r', encoding='utf-8') as f:
            content = f.read()
            sql_group = yaml.load(content, Loader=yaml.FullLoader)
            if not sql_group:
                raise Exception('sql file is empty')
            # Obtain sql based on sql_id
            sql_keys = sql_id.split('.')
            if len(sql_keys) > 1:
                sql_key = sql_keys[-1]
            else:
                raise Exception('sql_id pattern error')
            sql = sql_group.get(sql_key)
            if not sql:
                raise Exception('sql_id: %s not found' % sql_id)
        return sql

    @staticmethod
    def get_files(path: str) -> typing.List[str]:
        file_list = []
        for file in os.listdir(path):
            file_path = os.path.join(path, file)
            if os.path.isdir(file_path):
                file_list.extend(SqlLoader.get_files(file_path))
            else:
                file_list.append(file_path)
        return file_list

    @staticmethod
    def get_sql_data(path: str) -> typing.Dict[str, str]:
        file_list = SqlLoader.get_files(path)
        return {
            file.replace(
                path if path.endswith(os.sep) else path + os.sep, '')
            .replace('.yml', '').replace(os.sep, '.'): file
            for file in file_list
        }

    def preload_sql(self, sql_id: str, options: typing.Dict = None) -> str:
        """
        Preloaded sql

        Add paging: Convert page and page_size in options to limit and offset
        {
        "page": 1,
        "page_size": 20,
        }
        :param sql_id: id of the sql query
        :param options: Dynamically add parameter dictionary
        :return:
        """
        if not options:
            options = {}

        c_sql = self.get_sql(sql_id)
        
        page_num = options.get(self.page_param)
        page_size = options.get(self.page_size_param)

        if page_num:
            del options[self.page_param]
        if page_size:
            del options[self.page_size_param]

        if any([page_num, page_size]):
            page_num = page_num if page_num else 1
            options['limit'] = int(page_size if page_size else 10)
            options['offset'] = int((page_num - 1) * options['limit'])

            c_sql += """
            {% if limit and not offset %}
                LIMIT {{ limit }}
                {% elif limit and offset %}
                LIMIT {{ offset }},{{ limit }}
            {% endif %}
            """

        return jinja2.Template(c_sql).render(options) if options else c_sql


if __name__ == '__main__':
    sql_loader = SqlLoader()
    ret = sql_loader.preload_sql("home_page.sensor.selectAll", options={"equipment_id": 1})
    print(ret)
