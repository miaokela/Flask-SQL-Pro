## Flask-SQL-Pro 插件的编写与发布，及其使用

> 注意点(没遇到问题可以忽略)：如果自定义的相关组件，在创建Flask应用时导入，而且这些组件使用了Flask-SQLAlchemy的实例，不要在文件头import
```py
# __init__.py
def create_app():
    # ... 包括创建应用实例

    # These modules use Flask-SQLAlchemy instantiated objects that do not exist if db objects are
    # introduced before registration
    from app.plugins.jwt import jwt
    from app.plugins.mqtt import mqtt
    from app.plugins.redis import rs

    # Register jwt instance
    jwt.init_app(app)

    # Register redis instance
    rs.init_app(app)

    # Register mqtt instance
    mqtt.init_app(app)

    # ...

    return app
```

#### 1.注册pypi账户
> https://pypi.org/

#### 2.编写Flask应用及注册使用
- Flask应用配置
    > Flask中可以配置插件所需参数，参考: DataBaseHelper.page_param = app.config.get('DB_HELPER_PAGE_PARAM', 'page')
    ```python
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
    ```

- 注册使用
    > FlaskSQLPro(app) 或者 FlaskSQLPro的实例.init_app()
    ```python
    from flask_sql_pro import FlaskSQLPro


    # The Flask-SQL-Pro object is registered, and Flask-SQLAlchemy is registered
    sqlpro = FlaskSQLPro()
    db = sqlpro.init_app(app)
    ```

- 打包
    + 文件结构
    ```text
    Workspace
        - flask_sql_pro  模块名称
            - __init__.py
            - db.py
            - sql_loader.py
        - setup.py
    ```
    > setup.py
    ```python
    # 简单的示例
    from setuptools import setup, find_packages

    setup(
        name='Flask-SQL-Pro',
        version='2.1',
        packages=find_packages(),
        include_package_data=True,
        install_requires=[
            'flask',
            'flask_sqlalchemy',
            'pyyaml',
        ],
    )
    ```

    + 执行打包
    > python setup.py sdist
    
    + 上传pypi
    > pip install twine
    > twine upload dist/*

















#### 3.Flask-SQL-Pro的使用
> pip install flask-sql-pro
- 注册
    > 在create_app中注册
    ```py
    def create_app():
        # The Flask-SQL-Pro object is registered, and Flask-SQLAlchemy is registered
        sqlpro = FlaskSQLPro()
        db = sqlpro.init_app(app)
    ```
    > 为什么要在init_app()中返回一个db呢? Flask-Migrate等插件数据库操作可能用到SQLAlchemy实例对象
    ```py
    from flask_migrate import Migrate


    Migrate(app, db)
    ```

- 在models.py中引入
    ```py
    from flask_sql_pro import DataBaseHelper
    from sqlalchemy import text
    from sqlalchemy.dialects.mysql import TINYINT, BIGINT, VARCHAR, DATETIME, DOUBLE, INTEGER


    # 其他文件中如果要使用db对象: from project_path.models import db
    db = DataBaseHelper.db


    class BaseModel(db.Model):
        __abstract__ = True
        created_at = db.Column(DATETIME, comment='创建时间', server_default=text('Now()'))
        updated_at = db.Column(DATETIME, comment='更新时间', server_default=text('Now()'), onupdate=datetime.now())
        is_deleted = db.Column(TINYINT, comment='是否逻辑删除', server_default=text('0'), index=True)

        @classmethod
        def queryset(cls):
            """
            Data that is not logically deleted
            """
            return cls.query.filter(cls.is_deleted == 0)
    ```

- CRUD示例
    + 增
        ```py
        from flask_sql_pro import DataBaseHelper  # 主工具类
        from app.models import db # SQLAlchemy实例对象


        with db.trans():
            _id = DataBaseHelper.execute_create(
                'transit_record',  # 数据库名称
                data=data,
            )

            if not _id:
                raise AddRecordException()
        ```

    + 删
        ```py
        with db.trans():
            rows = DataBaseHelper.execute_delete(
                'transit_record',
                where={
                    'id': _id,
                },
                logic=True
            )
            if not rows:
                raise DelRecordException()
        ```

    + 改
        ```py
        with db.trans():
            rows = DataBaseHelper.execute_update(
                'transit_record',
                data=data,
                where={
                    'id': _id
                }
            )
            if not rows:
                raise ModifyRecordException()
        ```

    + 改/删 新增 exclude __gt __gte __lt __like __in __isnull __between
        > 示例
        ```py
        with db.trans():
            rows = DataBaseHelper.execute_update(
                'transit_record',
                data=data,
                where={
                    'id__in': [1,2,3],
                    'sort__gt': 5,
                },
                exclude={
                    'start_time__between': ['2023-12-30 10:10:10', '2023-12-30 12:10:10'],
                }
            )
            if not rows:
                raise ModifyRecordException()
        ```

    + 查
        + 创建存放SQL语句的文件夹
            > 默认是Flask的instance_path路径，即: project_path/instance/
            > 则默认的SQL文件夹应该创建在: project_path/instance/sql
            > !允许自定义路径，配置参数 DB_HELPER_SQL_FILE_PATH
            ```py
            import os


            class BaseConfig:
                BASE_DIR = os.path.dirname(os.path.realpath(__file__))
                APP_DIR = os.path.join(BASE_DIR, 'app')
                DB_HELPER_SQL_FILE_PATH = os.path.join(
                    APP_DIR,
                    'sql'
                )

            # 在创建Flask应用时，注册配置
            # __init__.py
            def create_app():
                # ...
                app.config.from_object(BaseConfig())
                # ...
            ```

        + 其他Flask-SQL-Pro的配置
            ```py
            DB_HELPER_PAGE_PARAM = 'page'  # 默认分页第几页
            DB_HELPER_PAGE_SIZE_PARAM = 'page_size'  # 默认分页每页数量
            DB_HELPER_PRINT_MSG = True  # 是否在终端打印SQL执行的语句
            ```
        + 查询示例
            > sql/transit/index.yml
            ```yaml
            query_map: |
            SELECT
                TRG.latitude,
                TRG.longitude,
                TRG.location,
                TRG.location_type
            FROM
                transit_record_gps AS TRG
            LEFT JOIN
                transit_record AS TR
            ON
                TRG.transit_record_id = TR.id
            WHERE
                TRG.is_deleted = 0
            AND
                TR.is_deleted = 0
            AND
                TR.id = :transit_record_id
            ```
            > app/api/transit.py
            ```py
            transit_record_gps = DataBaseHelper.select_all(
                'transit.index.query_map',
                params={
                    'transit_record_id': transit_record_id
                },
                return_obj=False,  # return_obj默认为True，即返回的是对象可以通过 transit_record_gps[0].transit_record_id 点的方式获取数据，如果为False，返回的是字典
            )
            ```
        + 分页
            > 默认需要传递的参数是 page/page_size，两个参数都传递才会分页
            > sql/history/index.yml
            ```yaml
            select_user_experiments: |
            SELECT
                experiment_id,
                experiment_name,
                date_format(update_datetime,"%Y-%m-%d") update_time
            FROM 
                data_experiment_record
            WHERE 
                delete_flag = 0
            ```

            ```py
            experiments = DataBaseHelper.select_all(
                'history.index.select_user_experiments',
                params={
                    'account_id': account_id,
                },
                options={
                    'page': 1,
                    'page_size': 20,
                }
            )
            ```

        + 动态SQL
            > 配合jinja2，实现条件语句，动态生成SQL
            > sql/experiment/index.yml
            ```yaml
            select_history_data_by_id_and_time: |
            SELECT
                daedd.daq_data_id daqDataId,
                daedd.vel_rms_value rmsVelocityValue,
                daedd.peak_value peakValue,
                daedd.peak_to_peak_value peaToPeakValue,
                daedd.skewness_value skewnessValue,
                daedd.mean_value meanValue,
                daedd.kurtosis_value kurtosisValue,
                daedd.rms_value rmsRawValue,
                daedd.rpm_value rpmValue,
                DATE_FORMAT(daedd.collection_datetime, '%Y-%m-%d %H:%i:%S') collectionDatetime
            FROM
                data_acquisition_equipment_daq_data daedd
            LEFT JOIN
                data_acquisition_equipment_daq_data_config daeddc
            ON
                daedd.data_config_id = daeddc.config_id
            WHERE
                daedd.sensor_id = :sensor_id
            {% if query_start_time and query_end_time %}
            AND 
                daedd.collection_datetime BETWEEN :query_start_time AND :query_end_time
            {% endif %}
            {% if experiment_id %}
            AND 
                daedd.experiment_id = :experiment_id
            {% endif %}
            ORDER BY daedd.collection_datetime ASC
            ```

            > app/api/experiment.py
            ```py
            daq_data_list = DataBaseHelper.select_all(
                "experiment.index.select_history_data_by_id_and_time",
                params={
                    "sensor_id": query.sensorId,
                    "query_start_time": query.queryStartTime,
                    "query_end_time": query.queryEndTime,
                    "experiment_id": experiment_id,
                },
                options={
                    "query_start_time": query.queryStartTime,
                    "query_end_time": query.queryEndTime,
                    "experiment_id": experiment_id,
                },
            )
            ```

        + 多数据库操作
            > 除了系统当前配置的 SQLALCHEMY_DATABASE_URI 对应的数据库之外，想操作其他数据库
            > 配置参数
            ```py
            class BaseConfig:
                SQLALCHEMY_BINDS = {
                    'cloud': 'mysql+pymysql://root:123456@127.0.0.1:3306/cloud_db?charset=utf8'
                }
            ```

            > 示例
            ```py
            add = DataBaseHelper.execute_create(
                'daq_data',
                data=online_data,
                app=cp,  # from flask import current_app as cp
                bind='cloud'  # 指定Bind的数据库
            )
            if not add:
                raise Exception('推送线上数据失败')
            
            DataBaseHelper.commit()
            ```

        + 事务
            > 默认不提交，使用DataBaseHelper.commit()来提交，或者 通过db.trans()上下文事务
            ```py
            from app.models import db


            with db.trans():
                add = DataBaseHelper.execute_create(
                    'daq_data',
                    data=online_data,
                    app=cp,  # from flask import current_app as cp
                    bind='cloud'  # 指定Bind的数据库
                )
                if not add:
                    raise Exception('推送线上数据失败')  
            ```
