import os
from contextlib import contextmanager

from flask_sqlalchemy import SQLAlchemy as _SQLAlchemy
from flask_sql_pro.db import DataBaseHelper
from flask_sql_pro.sql_loader import SqlLoader, Loader


class SQLAlchemy(_SQLAlchemy):
    """
    Transaction Context Manager
    """

    @contextmanager
    def trans(self):
        try:
            yield
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e


class FlaskSQLPro(object):
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app, *args, **kwargs):
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        _db = SQLAlchemy(app, *args, **kwargs)
        app.extensions['flask_sql_pro'] = self  # You can now access instances of the my_extension plugin in your Flask application
        DataBaseHelper.db = _db
        DataBaseHelper.logic_delete_flag = app.config.get('DB_HELPER_LOGIC_DELETE_FLAG', 'delete_flag')
        DataBaseHelper.page_param = app.config.get('DB_HELPER_PAGE_PARAM', 'page')
        DataBaseHelper.page_size_param = app.config.get('DB_HELPER_PAGE_SIZE_PARAM', 'page_size')
        DataBaseHelper.print_msg = app.config.get('DB_HELPER_PRINT_MSG', False)
        SqlLoader.page_param = app.config.get('DB_HELPER_PAGE_PARAM', 'page')
        SqlLoader.page_size_param = app.config.get('DB_HELPER_PAGE_SIZE_PARAM', 'page_size')

        default_sql_file_path = os.path.join(
            app.instance_path,  # {project_path}/instance/   :path_to flask instance_path
            'sql',
        )
        SqlLoader.SQL_FILE_PATH = app.config.get('DB_HELPER_SQL_FILE_PATH', default_sql_file_path)

        Loader.loader = SqlLoader()
        return _db


__all__ = [FlaskSQLPro, DataBaseHelper, SqlLoader]
