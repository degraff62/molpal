from typing import Iterable, Optional

import numpy as np
import torch
from torch import nn
from tqdm import tqdm

from ..chemprop.data import StandardScaler, MoleculeDataLoader, MoleculeDataset, MoleculeDatapoint

def predict(model, smis: Iterable[str], batch_size: int, ncpu: int, 
            uncertainty: bool, scaler, use_gpu: bool):
    if use_gpu:
        model = model.to(0)

    test_data = MoleculeDataset(
        [MoleculeDatapoint(smiles=[smi]) for smi in smis]
    )
    data_loader = MoleculeDataLoader(
        dataset=test_data, batch_size=batch_size, num_workers=ncpu
    )
    return _predict(
        model, data_loader, uncertainty,
        disable=True, scaler=scaler
    )

# @ray.remote(num_cpus=ncpu)
# def predict(model, smis, batch_size, ncpu, scaler, use_gpu: bool):
#     model.device = 'cpu'

#     test_data = MoleculeDataset(
#         [MoleculeDatapoint(smiles=[smi]) for smi in smis]
#     )
#     data_loader = MoleculeDataLoader(
#         dataset=test_data, batch_size=batch_size, num_workers=ncpu
#     )
#     return _predict(
#         model, data_loader, self.uncertainty,
#         disable=True, scaler=scaler
#     )

def _predict(model: nn.Module, data_loader: Iterable, uncertainty: bool,
            disable: bool = False,
            scaler: Optional[StandardScaler] = None) -> np.ndarray:
    """Predict the output values of a dataset

    Parameters
    ----------
    model : nn.Module
        the model to use
    data_loader : MoleculeDataLoader
        an iterable of MoleculeDatasets
    uncertainty : bool
        whether the model predicts its own uncertainty
    disable : bool (Default = False)
        whether to disable the progress bar
    scaler : Optional[StandardScaler] (Default = None)
        A StandardScaler object fit on the training targets

    Returns
    -------
    predictions : np.ndarray
        an NxM array where N is the number of inputs for which to produce 
        predictions and M is the number of prediction tasks
    """
    model.eval()

    pred_batches = []
    with torch.no_grad():
        for batch in tqdm(data_loader, desc='Inference', unit='batch',
                          leave=False, disable=disable):
            batch_graph = batch.batch_graph()
            pred_batch = model(batch_graph)
            pred_batches.append(pred_batch.data.cpu().numpy())
    preds = np.concatenate(pred_batches)

    if uncertainty:
        means = preds[:, 0::2]
        variances = preds[:, 1::2]

        if scaler:
            means = scaler.inverse_transform(means)
            variances = scaler.stds**2 * variances

        return means, variances

    # Inverse scale if regression
    if scaler:
        preds = scaler.inverse_transform(preds)

    return preds
    