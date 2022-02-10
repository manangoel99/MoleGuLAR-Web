from typing import Optional

from enum import Enum
from pydantic import BaseModel
from db import JobStatus

class TrainParams(BaseModel):
    num_epochs: Optional[int] = 1
    logP: Optional[bool] = False
    QED: Optional[bool] = False
    switch: Optional[bool] = True
    predictor: Optional[str] = 'dock'
    logP_threshold: Optional[float] = 2.5
    QED_threshold: Optional[float] = 0.8
    switch_frequency: Optional[int] = 35

class TrainParamsWithUser(TrainParams):
    user_id: int
    

class TrainJob(BaseModel):
    pdb_path: str
    user_id: int
    params: dict
    status: Optional[JobStatus] = JobStatus.pending