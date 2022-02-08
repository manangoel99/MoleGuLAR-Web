from databases import Database
from sqlalchemy import (ARRAY, Column, Integer, MetaData, String, Table,
                        create_engine)

DATABASE_URL = 'postgresql://devuser:dev_password@localhost/movie_db'

engine = create_engine(DATABASE_URL)
metadata = MetaData()

movies = Table(
    'movies',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(50)),
    Column('plot', String(250)),
    Column('genres', ARRAY(String)),
    Column('casts', ARRAY(String))
)

users = Table(
    'users',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(50), nullable=False),
    Column('email', String(50), nullable=False),
    Column('password', String(100), nullable=False)
)

database = Database(DATABASE_URL)
