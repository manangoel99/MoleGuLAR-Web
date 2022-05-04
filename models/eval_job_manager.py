import asyncio
import json
import os
import pickle as pkl
from collections import defaultdict
from pathlib import Path

import ray
from db import JobStatus, database, train_jobs
from fastapi import status
from fastapi.exceptions import HTTPException
from rdkit import Chem
from rdkit.Chem.Crippen import MolLogP
from rdkit.Chem.QED import qed
from trainer.train_model import TrainModel


async def get_molecules(job_id: int, user_id: int, num_molecules: int = 10):
    query = train_jobs.select().where(train_jobs.c.id == job_id)
    job = await database.fetch_one(query)

    pdb_path = job.pdb_path
    gpf_path = job.gpf_path
    params = json.loads(job.params)

    model = TrainModel.remote(
        {
            "pdb_path": pdb_path,
            "gpf_path": gpf_path,
            "user_id": user_id,
            "params": params,
        },
        job_id,
        eval=True,
    )

    id = model.load_generator.remote(
        f"{os.environ['ROOT_DIR']}/{user_id}/{job_id}" f"/models/model_exponential.pt"
    )

    ray.get(id)

    id = model.estimate_and_update.remote(n_to_generate=num_molecules)

    smiles_cur, prediction_cur = ray.get(id)

    logps = [MolLogP(Chem.MolFromSmiles(sm)) for sm in smiles_cur]

    final_rows = []

    for idx, sm in enumerate(smiles_cur):
        try:
            q = qed(Chem.MolFromSmiles(sm))
            final_rows.append((sm, prediction_cur[idx], logps[idx], q))
        except:
            pass

    return final_rows
