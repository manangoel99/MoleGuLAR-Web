import os
import shutil
import sys
from pathlib import Path

from pydantic import BaseModel


import molegular.rewards as rwds
import ray
import torch
from molegular.Predictors.GINPredictor import Predictor as GINPredictor
from molegular.Predictors.RFRPredictor import RFRPredictor
from molegular.release.data import GeneratorData
from molegular.release.reinforcement import Reinforcement
from molegular.release.stackRNN import StackAugmentedRNN
from molegular.release.utils import canonical_smiles
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem, rdmolfiles
from rdkit.Chem.Crippen import MolLogP
from rdkit.Chem.QED import qed
from torch import nn

RDLogger.DisableLog('rdApp.info')

@ray.remote(num_gpus=1)
class TrainModel(object):
    def __init__(self, train_job: dict, job_id: int):
        self.user_id = train_job["user_id"]
        self.receptor = train_job["pdb_path"]
        self.gpf = train_job["gpf_path"]
        self.job_id = job_id
        gpu_ids = ray.get_gpu_ids()
        if len(gpu_ids) == 0:
            self.device = torch.device("cpu")
        else:
            self.device = torch.device(f"cuda:{gpu_ids[0]}")
        self.epochs = train_job["params"]["num_epochs"]
        self.logP = train_job["params"]["logP"]
        self.QED = train_job["params"]["QED"]
        self.switch = train_job["params"]["switch"]
        self.predictor = train_job["params"]["predictor"]
        self.logP_threshold = train_job["params"]["logP_threshold"]
        self.QED_threshold = train_job["params"]["QED_threshold"]
        self.switch_frequency = train_job["params"]["switch_frequency"]
        self.OVERALL_INDEX = 0

        self.thresholds = {
            'LogP': self.logP_threshold,
            'QED': self.QED_threshold
        }

        self.use_docking = True
        self.reward_function = 'exponential'

        self.get_reward = rwds.MultiReward(
            rwds.exponential,
            use_docking=True,
            use_logP=self.logP,
            use_qed=self.QED,
            use_tpsa=False,
            use_solvation=False,
            **self.thresholds
        )

        self.job_dir = Path(os.path.join(
            os.getenv("ROOT_DIR"),
            str(self.user_id),
            str(self.job_id),
        ))

        gen_data_path = "./random.smi"
        tokens = ['<', '>', '#', '%', ')', '(', '+', '-', '/', '.', '1', '0', '3', '2', '5', '4', '7',
          '6', '9', '8', '=', 'A', '@', 'C', 'B', 'F', 'I', 'H', 'O', 'N', 'P', 'S', '[', ']',
          '\\', 'c', 'e', 'i', 'l', 'o', 'n', 'p', 's', 'r', '\n']

        self.gen_data = GeneratorData(training_data_path=gen_data_path, delimiter='\t',
                         cols_to_read=[0], keep_header=True, tokens=tokens)
        
        self.create_dirs()

    def create_dir(self, type):
        root_dir = os.getenv("ROOT_DIR")
        path = Path(
            os.path.join(
                root_dir,
                str(self.user_id),
                str(self.job_id),
                type,
            )
        )

        if os.path.exists(path) == False:
            path.mkdir(exist_ok=True, parents=True)
        else:
            shutil.rmtree(path)
            path.mkdir(exist_ok=True, parents=True)
        return path

    
    def create_dirs(self):
        self.logs_dir_path = self.create_dir(f"logs_{self.reward_function}")
        self.molecules_dir_path = self.create_dir(f"molecules_{self.reward_function}")
        self.trajectories_path = self.create_dir("trajectories")
        self.rewards_path = self.create_dir("rewards")
        self.losses_path = self.create_dir("losses")
        self.models_path = self.create_dir("models")
        self.predictions_path = self.create_dir("predictions")

        self.MODEL_NAME = os.path.join(self.models_path, f"model_{self.reward_function}.pt")
        self.LOGS_DIR = self.logs_dir_path
        self.MOL_DIR = self.molecules_dir_path

        self.TRAJ_FILE = open(os.path.join(self.trajectories_path, f"trajectories_{self.reward_function}.txt"), "w")
        self.LOSS_FILE = os.path.join(self.losses_path, f"losses_{self.reward_function}.txt")
        self.REWARD_FILE = os.path.join(self.rewards_path, f"rewards_{self.reward_function}.txt")
    
    def dock_and_get_score(self, smile, test=False):
        mol_dir = self.MOL_DIR
        log_dir = self.LOGS_DIR

        try:
            path = os.getenv("AUTODOCK_PATH")
            mol = Chem.MolFromSmiles(smile)
            AllChem.EmbedMolecule(mol)

            if test == True:
                self.MOL_DIR = Path(
                    os.path.join(
                        self.MOL_DIR,
                        "validation"
                    )
                )
                self.LOGS_DIR = Path(
                    os.path.join(
                        self.LOGS_DIR,
                        "validation"
                    )
                )

                if os.path.exists(self.MOL_DIR):
                    shutil.rmtree(self.MOL_DIR)
                self.MOL_DIR.mkdir(exist_ok=True, parents=True)

                if os.path.exists(self.LOGS_DIR):
                    shutil.rmtree(self.LOGS_DIR)
                self.LOGS_DIR.mkdir(exist_ok=True, parents=True)
            rdmolfiles.MolToPDBFile(mol, os.path.join(self.MOL_DIR, f"{self.OVERALL_INDEX}.pdb"))

            os.system(f"{path}/prepare_ligand4.py -l {self.MOL_DIR}/{str(self.OVERALL_INDEX)}.pdb -o {self.MOL_DIR}/{str(self.OVERALL_INDEX)}.pdbqt") # > /dev/null 2>&1")
            os.system(f"{path}/prepare_receptor4.py -r {self.receptor} -o ./protein.pdbqt") # > /dev/null 2>&1")
            os.system(f"{path}/prepare_gpf4.py -i {self.gpf} -l {self.MOL_DIR}/{str(self.OVERALL_INDEX)}.pdbqt -r {self.job_dir}/protein.pdbqt -o {self.job_dir}/grid_params.gpf > /dev/null 2>&1")

            os.system(f"autogrid4 -p {self.job_dir}/grid_params.gpf > /dev/null 2>&1")
            os.system(f"~/AutoDock-GPU/bin/autodock_gpu_64wi -ffile protein.maps.fld -lfile {self.MOL_DIR}/{str(self.OVERALL_INDEX)}.pdbqt -resnam {self.LOGS_DIR}/{str(self.OVERALL_INDEX)} -nrun 10 -devnum 1 > /dev/null 2>&1")

            cmd = f"cat {self.LOGS_DIR}/{str(self.OVERALL_INDEX)}.dlg | grep -i ranking | tr -s '\t' ' ' | cut -d ' ' -f 5 | head -n1"
            stream = os.popen(cmd)
            output = float(stream.read().strip())
            self.OVERALL_INDEX += 1
            self.MOL_DIR = mol_dir
            self.LOGS_DIR = log_dir
            return output

        except Exception as e:
            self.MOL_DIR = mol_dir
            self.LOGS_DIR = log_dir
            self.OVERALL_INDEX += 1
            return 0

        
if __name__ == "__main__":
    os.environ["ROOT_DIR"] = "/home/manan/Desktop/MoleGuLAR-Web/MoleGuLAR-Web-app/data"
    os.environ["AUTODOCK_PATH"] = "/home/manan/MGLTools-1.5.6/MGLToolsPckgs/AutoDockTools/Utilities24"
    path = os.getenv("ROOT_DIR")

    print(path)
    job = {
        "pdb_path": f"{path}/1/4BTK.pdb", 
        "gpf_path": f"{path}/1/4BTK.gpf", 
        "user_id":1, 
        "params":{
            "num_epochs": 1,
            "logP": True,
            "QED": True,
            "switch": True,
            "predictor": "dock",
            "logP_threshold": 2.5,
            "QED_threshold": 0.8,
            "switch_frequency": 35
        }
    }
    obj = TrainModel.remote(job, 1)
    ans =  obj.dock_and_get_score.remote("CC(=O)O")

    print("Hven't started yet")

    print(ray.get(ans))

    print("Finished")
