import reprlib
from collections import Iterable

import pandas as pd
from sangreal_db.orm import SangrealSession
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import reflection
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.attributes import InstrumentedAttribute


class DataBase:
    """class for easy to use orm of your database/

    Raises:
        ValueError -- [bind must be sth like sqlalchemy's engine]

    Returns:
        [instance of DataBase] -- []
    """

    def __init__(self, bind, schema=None):
        if bind is None:
            return
        if schema == 'None':
            schema = None
        if isinstance(bind, str):
            bind = create_engine(bind)
        self._bind = bind
        self._schema = schema
        self._metadata = MetaData(bind=self._bind, schema=schema)
        self.Base = declarative_base(metadata=self._metadata)
        self._session = SangrealSession(self._bind)
        self.tables = self._get_tables(self._bind, schema)
        for table in self.tables:
            setattr(self, table, 'None')
            # 可能有大小写问题
            setattr(self, table.lower(), 'None')
            setattr(self, table.upper(), 'None')

    def inject(self, bind, schema=None):
        self.__init__(bind, schema)
        return

    def __getattribute__(self, table_name):
        if object.__getattribute__(self, table_name) == 'None':
            try:
                setattr(self, table_name, self._reflect_table(table_name))
            except InvalidRequestError:
                try:
                    setattr(self, table_name,
                            self._reflect_table(table_name.lower()))
                except InvalidRequestError:
                    setattr(self, table_name,
                            self._reflect_table(table_name.upper()))
        return object.__getattribute__(self, table_name)

    def __getattr__(self, name):
        raise AttributeError(
            f'<{name}> is not the right table name, such as {reprlib.repr(self.tables)}.'
        )

    def __repr__(self):
        return str(self._bind).replace(
            type(self._bind).__name__,
            type(self).__name__)

    @property
    def bind(self):
        return self._bind

    @property
    def schema(self):
        return self._schema

    def _reflect_table(self, table_name):
        self._metadata.reflect(only=[table_name])
        Base = automap_base(metadata=self._metadata)
        Base.prepare()
        try:
            table = Base.classes[table_name]
            column_list = tuple(table.__dict__.keys())
            # 对列名大小写进行处理
            for column in column_list:
                c = getattr(table, column)
                if isinstance(c, InstrumentedAttribute):
                    setattr(table, column.upper(), c)
                    setattr(table, column.lower(), c)
            return table
        except KeyError:
            raise ValueError(f"There must be a primary key in {table_name}! \
or <{table_name}> is not the right table name, such as {reprlib.repr(self.tables)}."
                             )

    def reflect(self):
        self._metadata.reflect()
        Base = automap_base(metadata=self._metadata)
        Base.prepare()
        for k, v in Base.classes.items():
            setattr(self, k, v)
            setattr(self, k.lower(), v)
            setattr(self, k.upper(), v)

    @staticmethod
    def _get_tables(bind, schema):
        insp = reflection.Inspector.from_engine(bind=bind)
        tables = insp.get_table_names(schema=schema)
        return tables

    def query(self, *columns):
        """[session.query]

        Returns:
            [Query] -- [sqlalchemy Query cls]
        """

        return self._session.query(*columns)

    def update(self, t_obj):
        """[update table]

        Arguments:
            t_obj {[objs of DeclarativeMeta]} -- [update the table]
        """

        if isinstance(t_obj, Iterable):
            self._session.add_all(t_obj)
        else:
            self._session.add(t_obj)

    def insert(self, table, insert_obj, ignore=True, index=None):
        """[insert bulk data]

        Arguments:
            table {[DeclarativeMeta cls]} -- [reflection of table]
            insert_obj {[pd.DataFrame or list of dicts]} -- [insert_obj]
            ignore {[bool]} -- [whether or not ignore duplicate insert]
            index {[str]} -- [the index you want to ignore]

        Keyword Arguments:
            ignore {bool} -- [wether ignore exception or not] (default: {True})

        Raises:
            ValueError -- [f"The {reprlib.repr(insert_obj)} must be list of dicts type!"]

        Returns:
            [type] -- [description]
        """

        if isinstance(insert_obj, pd.DataFrame):
            if insert_obj.empty:
                raise ValueError('The input DataFrame is empty, please check!')
            insert_obj = insert_obj.to_dict('records')
        elif not isinstance(insert_obj, list):
            raise ValueError(
                f"The {reprlib.repr(insert_obj)} must be list of dicts type!")
        if self._bind.dialect.name == 'mysql':
            ignore_str = 'IGNORE' if ignore else ''
        elif self._bind.dialect.name == 'sqlite':
            ignore_str = 'OR REPLACE' if ignore else ''
        elif self._bind.dialect.name == 'oracle':
            if ignore and index is None:
                for i in table.__table__.indexes:
                    if i.unique:
                        index = i.name
                        break
                if index is None:
                    index = list(table.__table__.constraints)[0].name
            ignore_str = f'/*+ IGNORE_ROW_ON_DUPKEY_INDEX ({table.__table__.name}, {index}) */' if ignore else ''
        elif self._bind.dialect.name == 'mssql':
            ignore_str = ""
            if ignore:
                raise ValueError(
                    "You can set 'IGNORE_DUP_KEY = ON' while create the table and set the paramenter 'ignore=False'.")
        return self._session.execute(
            table.__table__.insert().prefix_with(ignore_str).values(insert_obj))


    def delete(self, t_obj):
        return self._session.delete(t_obj)

    def close(self):
        return self._session.close()

    def merge(self, t_obj):
        """[replace]

        Arguments:
            t_obj {[objs of DeclarativeMeta]} -- [replace the table]
        """

        if isinstance(t_obj, Iterable):
            for t in t_obj:
                self._session.merge(t)
            return
        else:
            return self._session.merge(t_obj)


    def commit(self):
        return self._session.commit()

    def flush(self, objects=None):
        return self._session.flush(objects=objects)

    def rollback(self):
        return self._session.rollback()

    def refresh(self):
        return self.__init__(self._bind, self._schema)

    def create_all(self, tables=None, checkfirst=True):
        self._metadata.create_all(
            tables=tables, checkfirst=checkfirst)
        self.refresh()
        return


if __name__ == '__main__':
    pass
