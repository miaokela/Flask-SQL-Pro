
Changelog
=============

v4.6 (2023-12-30)

- Added exclude
- Added __gt __gte __lt __lte __like __in __isnull __between

----------------------

v4.1 (2023-07-24)
----------------------

- Added security check
- Fixed bug default delete flag


Use of Flask-SQL-Pro
==========================

Example: https://www.cnblogs.com/miaokela/articles/17571427.html


.. pull-quote:: 
  pip install flask-sql-pro

Register
----------

.. pull-quote:: 
  Register in create_app

.. code-block:: python

  def create_app():
      # Register Flask-SQL-Pro objects, and register Flask-SQLAlchemy
      sqlpro = FlaskSQLPro()
      db = sqlpro.init_app(app)

.. pull-quote:: 
  Why return a db in init_app()? 
  SQLAlchemy instance objects may be used for plug-in database operations such as Flask-Migrate

.. code-block:: python

  from flask_migrate import Migrate


  Migrate(app, db)


Import in models.py
-----------------------

.. code-block:: python

  from flask_sql_pro import DataBaseHelper
  from sqlalchemy import text
  from sqlalchemy.dialects.mysql import TINYINT, BIGINT, VARCHAR, DATETIME, DOUBLE, INTEGER

  # If you want to use db objects in other files: from project_path.models import db
  db = DataBaseHelper.db

  class BaseModel(db.Model):
      __abstract__ = True
      created_at = db.Column(DATETIME, comment='Create Time', server_default=text('Now()'))
      updated_at = db.Column(DATETIME, comment='Update Time', server_default=text('Now()'), onupdate=datetime.now())
      is_deleted = db.Column(TINYINT, comment='Logical delete or not', server_default=text('0'), index=True)

      @classmethod
      def queryset(cls):
          """
          Data that is not logically deleted
          """
          return cls.query.filter(cls.is_deleted == 0)

CRUD example
--------------

- Add

.. code-block:: python

  from flask_sql_pro import DataBaseHelper  # Master tool class
  from app.models import db # SQLAlchemy Instance object

  with db.trans():
      _id = DataBaseHelper.execute_create(
          'transit_record',  # Table name
          data=data,
      )

      if not _id:
          raise AddRecordException()

- Delete
  
.. code-block:: python

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

- Modify

.. code-block:: python

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

- Select

.. pull-quote:: 
  Create a folder to store SQL statements
  The default is Flask's instance_path path, which is project_path/instance/
  The default SQL folder should be created in project_path/instance/sql
  To allow custom paths, configure the DB_HELPER_SQL_FILE_PATH parameter

.. code-block:: python

  import os


  class BaseConfig:
      BASE_DIR = os.path.dirname(os.path.realpath(__file__))
      APP_DIR = os.path.join(BASE_DIR, 'app')
      DB_HELPER_SQL_FILE_PATH = os.path.join(
          APP_DIR,
          'sql'
      )

  # Register the configuration when creating a Flask application
  # __init__.py
  def create_app():
      # ...
      app.config.from_object(BaseConfig())
      # ...

.. pull-quote:: 
  Other Flask-SQL-Pro configurations

.. code-block:: python

  DB_HELPER_LOGIC_DELETE_FLAG = 'delete_flag'  # The default logic delete flag name, The value of the flag for logical deletion is 1 and cannot be modified
  DB_HELPER_PAGE_PARAM = 'page'  # The default page number
  DB_HELPER_PAGE_SIZE_PARAM = 'page_size'  # Default number of pages per page
  DB_HELPER_PRINT_MSG = True  # Whether to print SQL execution statements on the terminal

.. pull-quote:: 
  Query example

Files: sql/transit/index.yml

.. code-block:: yaml

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

Files: app/api/transit.py

.. code-block:: python

  transit_record_gps = DataBaseHelper.select_all(
      'transit.index.query_map',
      params={
          'transit_record_id': transit_record_id
      },
      return_obj=False,  # The default value of return_obj is True, which means that the object can obtain data from the transit_record_gps[0].transit_record_id point. If False, the dictionary is returned
  )



- Pagination

.. pull-quote:: 
  The default parameter that needs to be passed is page/page_size, and paging occurs when both parameters are passeds

Files: sql/history/index.yml

.. code-block:: yaml

  select_user_experiments: |
      SELECT
          experiment_id,
          experiment_name,
          date_format(update_datetime,"%Y-%m-%d") update_time
      FROM 
          data_experiment_record
      WHERE 
          delete_flag = 0

.. code-block:: python

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

- Dynamic SQL

.. pull-quote:: 
  With jinja2, conditional statement is realized and SQL is generated dynamically

Files: sql/experiment/index.yml

.. code-block:: yaml

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

Files: app/api/experiment.py

.. code-block:: python

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

- Multi-database operation

.. pull-quote:: 
  You want to operate other databases other than the database corresponding to the SQLALCHEMY_DATABASE_URI configured in the system

.. pull-quote:: 
  Configuration parameter

.. code-block:: python

  class BaseConfig:
      SQLALCHEMY_BINDS = {
          'cloud': 'mysql+pymysql://root:123456@127.0.0.1:3306/cloud_db?charset=utf8'
      }

.. pull-quote:: 
  Give an example

.. code-block:: python

  add = DataBaseHelper.execute_create(
      'daq_data',
      data=online_data,
      app=cp,  # from flask import current_app as cp
      bind='cloud'  # Specifies the database for Bind
  )
  if not add:
      raise Exception('Description Failed to push online data')

  DataBaseHelper.commit()

- Transaction

.. pull-quote:: 
  No commit by default, commit using databaseHelper.mit (), or through the db.trans() context transaction

.. code-block:: python

  from app.models import db

  with db.trans():
      add = DataBaseHelper.execute_create(
          'daq_data',
          data=online_data,
          app=cp,  # from flask import current_app as cp
          bind='cloud'  # Specifies the database for Bind
      )
      if not add:
          raise Exception('Description Failed to push online data')
