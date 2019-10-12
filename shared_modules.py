import pyodbc
import logging
import pandas as pd
import logging
import requests


def sql_server_connection(config, database):
    config['database'] = database
    try:
        conn = pyodbc.connect(
            'DRIVER={driver};SERVER={server},{port};DATABASE={database};UID={username};PWD={password}'.format(**config)
        )
        cursor = conn.cursor()
    except Exception as e:
        logging.info(e)

    return conn, cursor


def get_data(base_url):
    try:
        rqst = requests.request('GET', base_url)
        return rqst.json()
    except ValueError as e:
        logging.info(e)


def load_data(query, sql_config, database):
    sql_data = []
    conn, cursor = sql_server_connection(sql_config, database)

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        pass
    except Exception as e:
        print(e)
        rows = pd.read_sql(query, conn)

    for row in rows:
        sql_data.append(list(row))

    df = pd.DataFrame(sql_data)

    return df


def create_logger(file_name):
    logging.basicConfig(filename=file_name,
                        filemode='a',
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.DEBUG)


def remove_duplicates(lst):
    return [dict(t) for t in {tuple(d.items()) for d in lst}]


def values_statement(lst):
    if lst:
        _ = [tuple([str(l).replace("'", "") for l in ls.values()])
             for ls in lst]
        return ','.join([str(i) for i in _])


def columns_statement(lst):
    if lst:
        return ', '.join([['[' + i + ']' for i in l.keys()] for l in lst][0])


def source_columns_statement(lst):
    if lst:
        return ', '.join([['Source.[' + i + ']' for i in l.keys()] for l in lst][0])


def update_statement(lst):
    if lst:
        return ', '.join([['[' + i + ']=Source.[' + i + ']' for i in l.keys()] for l in lst][0])


def on_statement(lst, key_columns):
    if 'LastUpdated' not in key_columns[0] and lst:
        return 'ON ' + ' AND '.join(
            [['Target.[' + i + ']=Source.[' + i + ']' for i in l.keys() if i in key_columns] for l in lst][0])
    else:
        return ''


def set_statement(lst, key_columns):
    return ', '.join([['[' + i + ']=Source.[' + i + ']' for i in l.keys() if i not in key_columns] for l in lst][0])


def execute_sql(table_name, data, key_columns, sql_cursor):
    query = 'SELECT * INTO #temp FROM ( VALUES {0} ) AS s ( {1} ) ' \
            'MERGE INTO {2} as Target ' \
            'USING #temp AS Source ' \
            '{3} ' \
            'WHEN NOT MATCHED THEN INSERT ( {1} ) VALUES ( {4} ) ' \
            'WHEN MATCHED THEN UPDATE SET {5}; ' \
            'DROP TABLE #temp; '.format(values_statement(data),
                                        columns_statement(data),
                                        table_name,
                                        on_statement(data, key_columns),
                                        source_columns_statement(data),
                                        set_statement(data, key_columns))

    sql_cursor.execute(query)
    logging.info('Table {0} updated: {1} records'.format(table_name, len(data)))
    print('Table {0} updated: {1} records'.format(table_name, len(data)))
