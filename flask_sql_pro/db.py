import copy
import re
import typing

from sqlalchemy.sql import compiler
from sqlalchemy.sql.elements import TextClause

from flask_sql_pro.sql_loader import Loader


class DBData(dict):
    """
    Set data or get data with point and bracket.
    """

    def __getattr__(self, key):
        return self.get(key, None)

    def __setattr__(self, key, value):
        if key in self.__dict__:
            self.__dict__[key] = value
        else:
            self[key] = value


class DataBaseHelper(object):
    db = None
    page_param = None
    page_size_param = None
    logic_delete_flag = None
    print_msg = False
    sql_injection_keywords = ['DROP', 'SELECT', 'DELETE' 'UPDATE', 'INSERT', 'EXEC', '--', '/*', '*/', 'xp_', 'sp_']

    @classmethod
    def print(cls, msg):
        if cls.print_msg:
            print(msg)

    @classmethod
    def get_params_without_paginated(cls, params: typing.Dict):
        if not params:
            return {}
        params_cp = copy.deepcopy(params)
        if cls.page_param in params:
            del params_cp[cls.page_param]
        if cls.page_size_param in params:
            del params_cp[cls.page_size_param]
        return params_cp

    @classmethod
    def set_where_phrase(cls, sql, where):
        """
        Generate where statement
        """
        if not where:
            return sql
        where_str = " WHERE "
        for key in where.keys():
            where_str += key + " = :" + "_where_%s" % key + " and "
        where_str = where_str[0:-5]
        sql += where_str

        return sql

    @classmethod
    def filter_sql_injection(cls, input_string):
        for keyword in cls.sql_injection_keywords:
            if keyword in input_string.upper():
                raise ValueError('Keywords that may be at risk for SQL injection:' + keyword)
        return input_string 

    @classmethod
    def fullfilled_data(cls, data, where):
        """
        The delete/update operation adds a _where_${field} field to each field in the where condition of the incoming data,
        which is used for the assignment of the where condition
        """
        if not where:
            return data

        for k, v in where.items():
            # Avoid sql injection
            if any(keyword in str(k).upper() for keyword in cls.sql_injection_keywords):
                raise ValueError('Keywords that may be at risk for SQL injection in key: ' + str(k))
            if any(keyword in str(v).upper() for keyword in cls.sql_injection_keywords):
                raise ValueError('Keywords that may be at risk for SQL injection in value: ' + str(v))

            if k.startswith("_where_"):
                raise Exception("The where condition cannot contain a field starting with _where_")
            data.update(**{
                "_where_%s" % k: v
            })

        return data

    @classmethod
    def execute_update(cls, tb_name, data, where, app=None, bind=None):
        """
        Update data
        Possible problems with UPDATE :where and data fields have the same name, but different values
        Process:
        Delete/update operation, add a _where_${field} field to the incoming data in the where condition for the where condition assignment.
        The value of the where condition is converted in this way ::field => :_where_${field}

        Data. update(**where) When data is processed, the converted where is updated into data. Data. update(**where)
        :param bind:
        :param app:
        :param tb_name: indicates the table name
        :param data: indicates data
        :param where: indicates the filter condition
        :return: update quantity
        """
        tb_name = cls.filter_sql_injection(tb_name)
        sql = "UPDATE " + tb_name + " SET "
        for key in data.keys():
            sql += "`%s`" % key + " = :" + key + ","
        sql = sql[0:-1]

        data = cls.fullfilled_data(data, where)
        sql = cls.set_where_phrase(sql, where)
        try:
            if app and bind:
                bind = cls.db.get_engine(app, bind=bind)
                result = cls.db.session.execute(sql, data, bind=bind)
            else:
                result = cls.db.session.execute(sql, data)
            return result.rowcount
        except Exception as e:
            cls.print("Failed to execute sql: < %s %s >! Cause: %s" % (sql, str(data), str(e)))
            return None

    @classmethod
    def allow_sharp(cls):
        """
        Allow # to appear in field names
        """
        compiler.BIND_PARAMS = re.compile(r"(?<![:\w$\x5c]):([\w$#]+)(?![:\w$])", re.UNICODE)
        TextClause._bind_params_regex = re.compile(r'(?<![:\w\x5c]):([\w#]+)(?!:)', re.UNICODE)

    @classmethod
    def execute_create(cls, tb_name, data, app=None, bind=None):
        """
        Insert data
        :param bind:
        :param app:
        :param tb_name: indicates the table name
        :param data: indicates data
        :return: indicates the id of the inserted data
        """
        # cls.allow_sharp()
        tb_name = cls.filter_sql_injection(tb_name)
        sql = "INSERT INTO " + tb_name + " ("
        for key in data.keys():
            sql += "`%s`" % key + ","
        sql = sql[0:-1]
        sql += ") VALUES ("
        for key in data.keys():
            sql += ":" + key + ","
        sql = sql[0:-1]
        sql += ")"
        try:
            if app and bind:
                bind = cls.db.get_engine(app, bind=bind)
                result = cls.db.session.execute(sql, data, bind=bind)
            else:
                result = cls.db.session.execute(sql, data)
            return result.lastrowid
        except Exception as e:
            cls.print("Failed to execute sql: < %s %s >! Cause: %s" % (sql, str(data), str(e)))
            return None

    @classmethod
    def execute_delete(cls, tb_name, where, logic=False, app=None, bind=None):
        """
        Delete data
        :param bind:
        :param app:
        :param logic:
        :param tb_name: indicates the table name
        :param where: indicates the filter condition
        :return: indicates the number of deleted items
        """
        tb_name = cls.filter_sql_injection(tb_name)
        sql = "DELETE FROM " + tb_name
        if logic:
            sql = "UPDATE %s SET %s=1" % (tb_name, cls.logic_delete_flag)
        sql = cls.set_where_phrase(sql, where)
        where = cls.fullfilled_data({}, where)

        try:
            if app and bind:
                bind = cls.db.get_engine(app, bind=bind)
                result = cls.db.session.execute(sql, where, bind=bind)
            else:
                result = cls.db.session.execute(sql, where)
            return result.rowcount
        except Exception as e:
            cls.print("Failed to execute sql: < %s %s >! Cause: %s" % (sql, str(where), str(e)))
            return None

    @classmethod
    def execute_sql(cls, sql_id, params=None, options: typing.Dict[str, str] = None, app=None, bind=None, return_obj=True):
        """
        General methods of dynamic sql
        :param return_obj: Returns Dict or DBData
        :param bind:
        :param app:
        :param sql_id:
        :param params: Search criteria
        :param options: dynamic sql conditions
        :return:
        """
        preloaded_sql = Loader.loader.preload_sql(sql_id, options=options)
        try:
            # Multiple databases | specifies that the database executes sql
            if app and bind:
                bind = cls.db.get_engine(app, bind=bind)
                result = cls.db.session.execute(preloaded_sql, params, bind=bind).fetchall()
            else:
                cls.print('execute <%s>, params: %s' % (sql_id, str(params)))
                result = cls.db.session.execute(preloaded_sql, params).fetchall()
        except Exception as e:
            cls.print("Failed to execute sql: %s %s! Cause :%s" % (preloaded_sql, str(params), str(e)))
            return []
        else:
            cls.print("Current sql execution: %s %s" % (preloaded_sql, str(params)))
        if return_obj:
            return [DBData(zip(item.keys(), item)) for item in result]
        return [dict(zip(item.keys(), item)) for item in result]

    @classmethod
    def select_one(cls, sql_id, params=None, options: typing.Dict[str, str] = None, app=None, bind=None, return_obj=True):
        options = cls.get_params_without_paginated(options)  # No paging required
        result = cls.execute_sql(sql_id, params, options, app=app, bind=bind, return_obj=return_obj)
        return DBData(result[0] if result else {})

    @classmethod
    def select_all(cls, sql_id, params=None, options: typing.Dict[str, typing.Union[str, int, None]] = None, app=None, bind=None, return_obj=True):
        return cls.execute_sql(sql_id, params, options, app=app, bind=bind, return_obj=return_obj)

    @classmethod
    def flush(cls):
        cls.db.session.flush()

    @classmethod
    def commit(cls):
        cls.db.session.commit()

    @classmethod
    def rollback(cls):
        cls.db.session.rollback()

    @classmethod
    def close(cls):
        cls.db.session.close()
