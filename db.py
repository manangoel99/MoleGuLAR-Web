import enum

from databases import Database
from sqlalchemy import (ARRAY, JSON, Column, Enum, ForeignKey, Integer,
                        MetaData, String, Table, create_engine)


class JobStatus(enum.Enum):
    pending = 0
    running = 1
    finished = 2
    failed = 3


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

train_jobs = Table(
    'train_jobs',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('pdb_path', String(500), nullable=False),
    Column('gpf_path', String(500), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False,),
    Column('params', JSON, nullable=False),
    Column('status', Enum(JobStatus), nullable=False),
)

database = Database(DATABASE_URL)
