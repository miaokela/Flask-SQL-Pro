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
    def filter_sql_injection(cls, input_string):
        for keyword in cls.sql_injection_keywords:
            if keyword in input_string.upper():
                raise ValueError('Keywords that may be at risk for SQL injection:' + keyword)
        return input_string

    @classmethod
    def handle_ops(cls, key, val, opt_type="where"):
        """
        包括的操作符包括: __in、__gt、__gte、__lt、__lte、__like、__isnull、__between
        Handle more types of operations.
        key: key for either "where" or "exclude"
        val: value for either "where" or "exclude"
        opt_type: "where" or "exclude"
        """
        phrase = f"{key} = :_where_{key} AND"

        filter_str = '_where_'
        if opt_type == 'exclude':
            filter_str = '_exclude_'

        if key.endswith('__gt'):
            phrase = f"{key} >= :{filter_str}{key} AND"
            if opt_type == 'exclude':
                phrase = f"{key} < :{filter_str}{key} AND"
        if key.endswith('__gte'):
            phrase = f"{key} >= :{filter_str}{key} AND"
            if opt_type == 'exclude':
                phrase = f"{key} < :{filter_str}{key} AND"
        if key.endswith('__lt'):
            phrase = f"{key} < :{filter_str}{key} AND"
            if opt_type == 'exclude':
                phrase = f"{key} >= :{filter_str}{key} AND"
        if key.endswith('__lte'):
            phrase = f"{key} <= :{filter_str}{key} AND"
            if opt_type == 'exclude':
                phrase = f"{key} > :{filter_str}{key} AND"
        if key.endswith('__like'):
            phrase = f"{key} LIKE :{filter_str}{key} AND"
            if opt_type == 'exclude':
                phrase = f"{key} NOT LIKE :{filter_str}{key} AND"
        if key.endswith('__in'):
            phrase = f"{key} IN :{filter_str}{key} AND"
            if opt_type == 'exclude':
                phrase = f"{key} NOT IN :{filter_str}{key} AND"
        if key.endswith('__isnull'):
            phrase = f"{key} IS NULL AND " if val else f"{key} IS NOT NULL AND "
            if opt_type == 'exclude':
                phrase = f"{key} IS NOT NULL AND " if val else f"{key} IS NULL AND "
        if key.endswith('__between'):
            phrase = f"{key} BETWEEN :{filter_str}_between_1_{key} AND :{filter_str}_between_2_{key} AND"

        return phrase

    @classmethod
    def set_where_phrase(cls, sql, where):
        """
        Generate where statement
        """
        if not where:
            return sql
        where_str = " WHERE "
        for key, val in where.items():
            where_str += cls.handle_ops(key, val, opt_type="where")

        where_str = where_str[0:-5]
        sql += where_str

        return sql
    
    @classmethod
    def set_exclude_phrase(cls, sql, exclude):
        """
        Generate exclude statement
        """
        if not exclude:
            return sql
        
        if "WHERE" not in sql.upper():
            sql += " WHERE "
        else:
            sql += " AND "
        for key in exclude.keys():
            sql += key + " != :" + "_exclude_%s" % key + " and "
        sql = sql[0:-5]

        return sql

    @classmethod
    def check_sql_injection(cls, k, v):
        """
        Avoid sql injection
        """
        if any(keyword in str(k).upper() for keyword in cls.sql_injection_keywords):
            raise ValueError('Keywords that may be at risk for SQL injection in key: ' + str(k))
        if any(keyword in str(v).upper() for keyword in cls.sql_injection_keywords):
            raise ValueError('Keywords that may be at risk for SQL injection in value: ' + str(v))

    @classmethod
    def handle_range_type(cls, k, v, is_where=True):
        # Check if it is a tuple or list
        # Check if it is __between
        data = None
        bt_str = '_where__between_'
        if not is_where:
            bt_str = '_exclude__between_'
        if isinstance(v, (tuple, list)):
            if len(v) == 2:
                if k.endswith("__between"):
                    data = {
                        f"{bt_str}1_{k}": v[0],
                        f"{bt_str}2_{k}": v[1],
                    }
        return data

    @classmethod
    def fullfilled_data(cls, data, where, exclude=None):
        """
        The delete/update operation adds a _where_${field} field to each field in the where condition of the incoming data,
        which is used for the assignment of the where condition
        """
        if not where:
            return data

        for k, v in where.items():
            cls.check_sql_injection(k, v)

            if k.startswith("_where_"):
                raise Exception("The where condition cannot contain a field starting with _where_")
            
            _d = cls.handle_range_type(k, v)
            if _d:
                data.update(**_d)
                continue

            data.update(**{
                "_where_%s" % k: v
            })

        # Exclude
        if exclude:
            for k, v in exclude.items():
                cls.check_sql_injection(k, v)

                if k.startswith("_exclude_"):
                    raise Exception("The exclude condition cannot contain a field starting with _exclude_")

                _d = cls.handle_range_type(k, v, is_where=False)
                if _d:
                    data.update(**_d)
                    continue

                data.update(**{
                    "_exclude_%s" % k: v
                })

        return data

    @classmethod
    def execute_update(cls, tb_name, data, where, app=None, bind=None, commit=False, exclude=None):
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
        :param commit: indicates whether to submit the transaction
        :return: update quantity
        """
        tb_name = cls.filter_sql_injection(tb_name)
        sql = "UPDATE " + tb_name + " SET "
        for key in data.keys():
            sql += "`%s`" % key + " = :" + key + ","
        sql = sql[0:-1]

        data = cls.fullfilled_data(data, where)
        sql = cls.set_where_phrase(sql, where)
        sql = cls.set_exclude_phrase(sql, exclude=exclude)
        try:
            if app and bind:
                bind = cls.db.get_engine(app, bind=bind)
                result = cls.db.session.execute(sql, data, bind=bind)
            else:
                result = cls.db.session.execute(sql, data)
            if commit:
                cls.db.session.commit()
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
    def execute_create(cls, tb_name, data, app=None, bind=None, commit=False):
        """
        Insert data
        :param bind:
        :param app:
        :param tb_name: indicates the table name
        :param data: indicates data
        :param commit: indicates whether to submit the transaction
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
            if commit:
                cls.db.session.commit()
            return result.lastrowid
        except Exception as e:
            cls.print("Failed to execute sql: < %s %s >! Cause: %s" % (sql, str(data), str(e)))
            return None

    @classmethod
    def execute_delete(cls, tb_name, where, logic=False, app=None, bind=None, commit=False):
        """
        Delete data
        :param bind:
        :param app:
        :param logic:
        :param tb_name: indicates the table name
        :param where: indicates the filter condition
        :param commit: indicates whether to submit the transaction
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
            if commit:
                cls.db.session.commit()
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
