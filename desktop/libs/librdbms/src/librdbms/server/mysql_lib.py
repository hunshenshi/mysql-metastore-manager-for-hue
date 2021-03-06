#!/usr/bin/env python
# Licensed to Cloudera, Inc. under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  Cloudera, Inc. licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

try:
    import MySQLdb as Database
except ImportError, e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Error loading MySQLdb module: %s" % e)

# We want version (1, 2, 1, 'final', 2) or later. We can't just use
# lexicographic ordering in this check because then (1, 2, 1, 'gamma')
# inadvertently passes the version test.
version = Database.version_info
if (version < (1,2,1) or (version[:3] == (1, 2, 1) and
        (len(version) < 5 or version[3] != 'final' or version[4] < 2))):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("MySQLdb-1.2.1p2 or newer is required; you have %s" % Database.__version__)

from django.utils.translation import ugettext as _

from librdbms.server.rdbms_base_lib import BaseRDBMSDataTable, BaseRDBMSResult, BaseRDMSClient


LOG = logging.getLogger(__name__)


class DataTable(BaseRDBMSDataTable): pass


class Result(BaseRDBMSResult): pass


class MySQLClient(BaseRDMSClient):
  """Same API as Beeswax"""

  data_table_cls = DataTable
  result_cls = Result

  def __init__(self, *args, **kwargs):
    super(MySQLClient, self).__init__(*args, **kwargs)
    self.connection = Database.connect(**self._conn_params)


  @property
  def _conn_params(self):
    params = {
      'user': self.query_server['username'],
      'passwd': self.query_server['password'] or '',  # MySQL can accept an empty password
      'host': self.query_server['server_host'],
      'port': self.query_server['server_port']
    }

    if self.query_server['options']:
      params.update(self.query_server['options'])

    if 'name' in self.query_server:
      params['db'] = self.query_server['name']

    return params


  def use(self, database):
    if 'db' in self._conn_params and self._conn_params['db'] != database:
      raise RuntimeError(_("Database '%s' is not allowed. Please use database '%s'.") % (database, self._conn_params['db']))
    else:
      cursor = self.connection.cursor()
      cursor.execute("USE `%s`" % database)
      self.connection.commit()


  def execute_statement(self, statement):
    cursor = self.connection.cursor()
    cursor.execute(statement)
    self.connection.commit()
    if cursor.description:
      columns = [column[0] for column in cursor.description]
    else:
      columns = []
    return self.data_table_cls(cursor, columns)


  def get_databases(self):
    cursor = self.connection.cursor()
    cursor.execute("SHOW DATABASES")
    self.connection.commit()
    databases = [row[0] for row in cursor.fetchall()]
    if 'db' in self._conn_params:
      if self._conn_params['db'] in databases:
        return [self._conn_params['db']]
      else:
        raise RuntimeError(_("Cannot locate the %s database. Are you sure your configuration is correct?") % self._conn_params['db'])
    else:
      return databases

  # add by szw for comment start
  def get_comment(self, database, table=None, column=None):
    cursor = self.connection.cursor()
    if table and column:
      query = '''select COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT 
                    from information_schema.COLUMNS 
                    where TABLE_SCHEMA='%s' and TABLE_NAME='%s' and COLUMN_NAME = '%s';''' % (database, table, column)
    elif table is not None:
      query = '''select COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT 
                    from information_schema.COLUMNS 
                    where TABLE_SCHEMA='%s' and TABLE_NAME='%s';''' % (database, table) 
    else:
      query = '''select TABLE_NAME, TABLE_TYPE, TABLE_COMMENT 
                   from information_schema.TABLES 
                   WHERE TABLE_SCHEMA = '%s';''' %(database)  
    print "get_comment " + query
    # hanzi luanma
    cursor.execute("set NAMES utf8")
    cursor.execute(query)
    self.connection.commit()
    return [dict(name=row[0], type=row[1], comment=row[2]) for row in cursor.fetchall()]

  def alter_table_comment(self, database, table_name, comment):
    cursor = self.connection.cursor()
    alter_sql = "alter table `%s`.`%s` comment = '%s'" % (database, table_name, comment)
    print "alter_sql " + alter_sql
    cursor.execute("set NAMES utf8")
    cursor.execute(alter_sql)
    self.connection.commit()
    return self.get_comment(database, table_name)

  def alter_column_comment(self, database, table_name, column_name, column_type, comment):
    cursor = self.connection.cursor()
    alter_sql = '''alter table `%(database)s`.`%(table)s` 
                modify column %(column_name)s %(column_type)s 
                comment "%(comment)s"''' % {'database':database, 'table':table_name,
                 'column_name':column_name, 'column_type':column_type,'comment':comment}
    print alter_sql
    cursor.execute("set NAMES utf8")
    cursor.execute(alter_sql)
    self.connection.commit()
    return self.get_comment(database, table_name, column_name)[0]                        
  # add by szw for comment end  
    
  def get_tables(self, database, table_names=[]):
    cursor = self.connection.cursor()
    query = 'SHOW TABLES'
    if table_names:
      clause = ' OR '.join(["`Tables_in_%(database)s` LIKE '%%%(table)s%%'" % {'database': database, 'table': table} for table in table_names])
      query += ' FROM `%(database)s` WHERE (%(clause)s)' % {'database': database, 'clause': clause}
    cursor.execute(query)
    self.connection.commit()
    return [row[0] for row in cursor.fetchall()]


  def get_columns(self, database, table, names_only=True):
    cursor = self.connection.cursor()
    cursor.execute("SHOW COLUMNS FROM %s.%s" % (database, table))
    self.connection.commit()
    if names_only:
      columns = [row[0] for row in cursor.fetchall()]
    else:
      columns = [dict(name=row[0], type=row[1], comment='') for row in cursor.fetchall()]
    return columns


  def get_sample_data(self, database, table, column=None, limit=100):
    column = '`%s`' % column if column else '*'
    statement = "SELECT %s FROM `%s`.`%s` LIMIT %d" % (column, database, table, limit)
    return self.execute_statement(statement)
