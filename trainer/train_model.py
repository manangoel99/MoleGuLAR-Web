import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import ray
import torch
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem, rdmolfiles
from rdkit.Chem.Crippen import MolLogP
from rdkit.Chem.QED import qed
from torch import nn
from tqdm import tqdm, trange

import trainer.molegular.rewards as rwds
from trainer.molegular.Predictors.GINPredictor import Predictor as GINPredictor
from trainer.molegular.release.data import GeneratorData
from trainer.molegular.release.reinforcement import Reinforcement
from trainer.molegular.release.stackRNN import StackAugmentedRNN
from trainer.molegular.release.utils import canonical_smiles

RDLogger.DisableLog('rdApp.info')

@ray.remote(num_gpus=1)
class TrainModel(object):
    def __init__(self, train_job: dict, job_id: int, eval: bool = False):
        self.user_id = train_job["user_id"]
        self.receptor = train_job["pdb_path"]
        self.gpf = train_job["gpf_path"]
        self.job_id = job_id
        gpu_ids = ray.get_gpu_ids()
        self.device = gpu_ids[0]
        if len(gpu_ids) == 0:
            self.device = torch.device("cpu")
        else:
            self.device = torch.device(f"cuda:{gpu_ids[0]}")
        self.devnum = gpu_ids[0] + 1
        self.epochs = train_job["params"]["num_epochs"]
        self.logP = train_job["params"]["logP"]
        self.QED = train_job["params"]["QED"]
        self.switch = train_job["params"]["switch"]
        self._predictor = train_job["params"]["predictor"]
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

        gen_data_path = os.path.join(os.getcwd(), "trainer", "random.smi")
        tokens = ['<', '>', '#', '%', ')', '(', '+', '-', '/', '.', '1', '0', '3', '2', '5', '4', '7',
          '6', '9', '8', '=', 'A', '@', 'C', 'B', 'F', 'I', 'H', 'O', 'N', 'P', 'S', '[', ']',
          '\\', 'c', 'e', 'i', 'l', 'o', 'n', 'p', 's', 'r', '\n']

        self.gen_data = GeneratorData(training_data_path=gen_data_path, delimiter='\t',
                         cols_to_read=[0], keep_header=True, tokens=tokens)
        
        self.create_dirs(eval=eval)

        self.LOGS_DIR = self.logs_dir_path
        self.MOL_DIR = self.molecules_dir_path

        if self._predictor == "dock":
            self.predictor = self.Predictor("", self)
        if self._predictor != "dock":
            if self._predictor != "gin":
                raise ValueError("Only gin predictor is supported for now")
            model_path = os.path.join(os.getenv("ROOT"), "trainer", "molegular", "Predictors", "GINPredictor.tar")
            self.predictor = GINPredictor(model_path)
        
        hidden_size = 1500
        stack_width = 1500
        stack_depth = 200
        layer_type = 'GRU'
        lr = 0.001
        optimizer_instance = torch.optim.Adadelta
        self.n_to_generate = 100
        self.n_policy_replay = 10
        self.n_policy = train_job["params"]["n_policy"]

        self.generator = StackAugmentedRNN(input_size=self.gen_data.n_characters,
                                     hidden_size=hidden_size,
                                     output_size=self.gen_data.n_characters,
                                     layer_type=layer_type,
                                     n_layers=1, is_bidirectional=False, has_stack=True,
                                     stack_width=stack_width, stack_depth=stack_depth,
                                     use_cuda=True,
                                     optimizer_instance=optimizer_instance, lr=lr)
        
        checkpoint_path = os.path.join(os.getenv("ROOT"), "trainer", "molegular", "checkpoints", "generator", "checkpoint_biggest_rnn")
        self.generator.load_model(checkpoint_path)

        self.RL = Reinforcement(self.generator, self.predictor, self.get_reward)
        self.rewards = []
        self.rl_losses = []
        self.preds = []
        self.logp_iter = []
        self.qed_iter = []
        self.metrics_df = {
            "BA": [], 
            "LogP": [], 
            "QED": []
        }

    def create_dir(self, type, eval=False):
        root_dir = os.getenv("ROOT_DIR")
        path = Path(
            os.path.join(
                root_dir,
                str(self.user_id),
                str(self.job_id),
                type,
            )
        )

        if eval:
            return path

        if os.path.exists(path) == False:
            path.mkdir(exist_ok=True, parents=True)
        else:
            shutil.rmtree(path)
            path.mkdir(exist_ok=True, parents=True)
        return path
    
    def load_generator(self, path):
        self.generator.load_model(path)
 
    def create_dirs(self, eval=False):
        self.logs_dir_path = self.create_dir(f"logs_{self.reward_function}", eval=eval)
        self.molecules_dir_path = self.create_dir(f"molecules_{self.reward_function}", eval=eval)
        self.trajectories_path = self.create_dir("trajectories", eval=eval)
        self.rewards_path = self.create_dir("rewards", eval=eval)
        self.losses_path = self.create_dir("losses", eval=eval)
        self.models_path = self.create_dir("models", eval=eval)
        self.predictions_path = self.create_dir("predictions", eval=eval)

        self.MODEL_NAME = os.path.join(self.models_path, f"model_{self.reward_function}.pt")
        self.LOGS_DIR = self.logs_dir_path
        self.MOL_DIR = self.molecules_dir_path

        self.TRAJ_FILE = open(os.path.join(self.trajectories_path, f"trajectories_{self.reward_function}.txt"), "w")
        self.LOSS_FILE = os.path.join(self.losses_path, f"losses_{self.reward_function}.txt")
        self.REWARD_FILE = os.path.join(self.rewards_path, f"rewards_{self.reward_function}.txt")
        self.DF_FILE = os.path.join(self.predictions_path, f"predictions_{self.reward_function}.txt")
    
    def dock_and_get_score(self, smile, test=False):
        mol_dir = self.MOL_DIR
        log_dir = self.LOGS_DIR
        curr_dir = os.getcwd()

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
            
            os.chdir(self.MOL_DIR)
            rdmolfiles.MolToPDBFile(mol, os.path.join(self.MOL_DIR, f"{self.OVERALL_INDEX}.pdb"))
            os.system(f"{path}/prepare_ligand4.py -l {self.OVERALL_INDEX}.pdb -o {self.MOL_DIR}/{str(self.OVERALL_INDEX)}.pdbqt") # > /dev/null 2>&1")
            os.system(f"{path}/prepare_receptor4.py -r {self.receptor} -o ./protein.pdbqt") # > /dev/null 2>&1")
            os.system(f"{path}/prepare_gpf4.py -i {self.gpf} -l {self.MOL_DIR}/{str(self.OVERALL_INDEX)}.pdbqt -r {self.MOL_DIR}/protein.pdbqt -o {self.MOL_DIR}/grid_params.gpf")# > /dev/null 2>&1")
            os.system(f"autogrid4 -p {self.MOL_DIR}/grid_params.gpf > /dev/null 2>&1")
            os.system(f"/app/AutoDock-GPU/bin/autodock_gpu_64wi -ffile protein.maps.fld -lfile {self.MOL_DIR}/{str(self.OVERALL_INDEX)}.pdbqt -resnam {self.LOGS_DIR}/{str(self.OVERALL_INDEX)} -nrun 10 -devnum {self.devnum} > /dev/null 2>&1")

            cmd = f"cat {self.LOGS_DIR}/{str(self.OVERALL_INDEX)}.dlg | grep -i ranking | tr -s '\t' ' ' | cut -d ' ' -f 5 | head -n1"
            stream = os.popen(cmd)
            output = float(stream.read().strip())
            self.OVERALL_INDEX += 1
            self.MOL_DIR = mol_dir
            self.LOGS_DIR = log_dir
            os.chdir(curr_dir)
            return output

        except Exception as e:
            self.MOL_DIR = mol_dir
            self.LOGS_DIR = log_dir
            os.chdir(curr_dir)
            self.OVERALL_INDEX += 1
            return 0
    
    def estimate_and_update(self, generator=None, predictor=None, n_to_generate=10):
        if generator is None:
            generator = self.generator
        
        if predictor is None:
            predictor = self.predictor

        generated = []
        pbar = tqdm(range(n_to_generate))
        for i in pbar:
            pbar.set_description("Generating molecules...")
            generated.append(generator.evaluate(self.gen_data, predict_len=120)[1:-1])

        sanitized = canonical_smiles(generated, sanitize=False, throw_warning=False)[:-1]
        unique_smiles = list(np.unique(sanitized))[1:]
        smiles, prediction, nan_smiles = predictor.predict(unique_smiles, test=True, use_tqdm=True)

        return smiles, prediction

    def simple_moving_average(self, previous_values, new_value, ma_window_size=10):
        value_ma = np.sum(previous_values[-(ma_window_size-1):]) + new_value
        value_ma = value_ma/(len(previous_values[-(ma_window_size-1):]) + 1)
        return value_ma

    def train(self, go=True):
        use_docking = False
        use_logP = True
        use_qed = False

        use_arr = np.array([False, False, True])

        for i in range(self.epochs):
            if self.switch == True:
                if self.logP == True and self.QED == True:
                    if i % self.switch_frequency == 0:
                        use_arr = np.roll(use_arr, 1)
                        use_docking, use_logP, use_qed = use_arr
                    self.get_reward = rwds.MultiReward(rwds.exponential, use_docking, use_logP, use_qed, False, False, **self.thresholds)
                if self.logP == True and self.QED == False:
                    if i % self.switch_frequency == 0:
                        use_logP = not use_logP
                        use_docking = not use_docking
                    self.get_reward = rwds.MultiReward(rwds.exponential, use_docking, use_logP, False, False, False, **self.thresholds)
            
            for j in range(self.n_policy):
                cur_reward, cur_loss = self.RL.policy_gradient(self.gen_data, self.get_reward)

                self.rewards.append(self.simple_moving_average(self.rewards, cur_reward))
                self.rl_losses.append(self.simple_moving_average(self.rl_losses, cur_loss))

            # smiles_cur, prediction_cur = self.estimate_and_update(self.RL.generator, self.predictor, self.n_to_generate)
            # logps = [MolLogP(Chem.MolFromSmiles(sm)) for sm in smiles_cur]
            # qeds = []

            # for sm in smiles_cur:
            #     try:
            #         qeds.append(qed(Chem.MolFromSmiles(sm)))
            #     except:
            #         pass

            # self.preds.append(sum(prediction_cur)/len(prediction_cur))
            # self.logp_iter.append(np.mean(logps))
            # self.qed_iter.append(np.mean(qeds))

            # self.metrics_df["BA"].append(self.preds[-1])
            # self.metrics_df["LogP"].append(self.logp_iter[-1])
            # self.metrics_df["QED"].append(self.qed_iter[-1])

            # print(f"BA: {self.preds[-1]}")
            # print(f"LogP {self.logp_iter[-1]}")
            # print(f"QED {self.qed_iter[-1]}")

            # df = pd.DataFrame(self.metrics_df)
            # df.to_csv(self.DF_FILE)

            self.RL.generator.save_model(self.MODEL_NAME)
            np.savetxt(self.LOSS_FILE, self.rl_losses)
            np.savetxt(self.REWARD_FILE, self.rewards)
        
        self.TRAJ_FILE.close()
        return True

    class Predictor(object):
        def __init__(self, path, trainer):
            self.path = path
            self.trainer = trainer
        
        def predict(self, smiles, test=False, use_tqdm=False):
            canonical_indices = []
            invalid_indices = []
            if use_tqdm:
                pbar = tqdm(range(len(smiles)))
            else:
                pbar = range(len(smiles))
            for i in pbar:
                sm = smiles[i]
                if use_tqdm:
                    pbar.set_description("Calculating predictions...")
                try:
                    sm = Chem.MolToSmiles(Chem.MolFromSmiles(sm))
                    if len(sm) == 0:
                        invalid_indices.append(i)
                    else:
                        canonical_indices.append(i)
                except:
                    invalid_indices.append(i)
            canonical_smiles = [smiles[i] for i in canonical_indices]
            invalid_smiles = [smiles[i] for i in invalid_indices]
            if len(canonical_indices) == 0:
                return canonical_smiles, [], invalid_smiles
            prediction = [self.trainer.dock_and_get_score(smiles[index], test) for index in canonical_indices]
            return canonical_smiles, prediction, invalid_smiles

if __name__ == "__main__":
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
    print(job)
    obj = TrainModel.remote(job, 1)
    ans = obj.train.remote(False)

    print(ray.wait([ans]))
    print(ray.get(ans))

    print("Finished")
