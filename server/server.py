from typing import List

from fastapi import APIRouter, Header
from fastapi.exceptions import HTTPException
from models.movie import *
from models import movie_manager 

server = APIRouter()

@server.get('/', response_model=List[MovieIn])
async def index():
    return await movie_manager.get_all_movies()

@server.post('/', status_code=201)
async def add_movie(payload: MovieIn):
    id = await movie_manager.add_movie(payload)
    return {
        "id": id,
        **payload.dict()
    }

@server.put('/{id}')
async def update_movie(id: int, payload: MovieIn):
    movie = await movie_manager.get_movie(id)

    if not movie:
        raise HTTPException(status_code=404, detail="Movie does not exist")
    
    update_data = payload.dict(exclude_unset=True)
    movie_in_db = MovieIn(**movie)

    updated = movie_in_db.copy(update=update_data)

    return await movie_manager.update_movie(id, updated)

@server.delete('/{id}')
async def delete_movie(id: int):
    movie = await movie_manager.get_movie(id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return await movie_manager.delete_movie(id)