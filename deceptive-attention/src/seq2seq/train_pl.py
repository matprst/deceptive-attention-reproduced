import argparse
import os

import pytorch_lightning as pl
import torch
from pytorch_lightning import Trainer
from pytorch_lightning import loggers as pl_loggers
from pytorch_lightning.callbacks import ModelCheckpoint

import utils
from batch_utils import SentenceDataModule
from model import BiGRU

LOG_PATH = "logs/"
DATA_PATH = "data/"
DATA_VOCAB_PATH = "data/vocab/"
DATA_MODELS_PATH = "data/models/"

ENC_EMB_DIM = 256
DEC_EMB_DIM = 256
ENC_HID_DIM = 512
DEC_HID_DIM = 512
ENC_DROPOUT = 0.5
DEC_DROPOUT = 0.5
PAD_IDX = utils.PAD_token
SOS_IDX = utils.SOS_token
EOS_IDX = utils.EOS_token


def train_gru(parameters):
    """
    Function for training and testing a bidirectional GRU model.
    Inputs:
        args - Namespace object from the argument parser
    """

    os.makedirs(LOG_PATH, exist_ok=True)
    os.makedirs(DATA_PATH, exist_ok=True)
    os.makedirs(DATA_MODELS_PATH, exist_ok=True)
    os.makedirs(DATA_VOCAB_PATH, exist_ok=True)

    data_module = SentenceDataModule(task=parameters.task,
                                     batch_size=parameters.batch_size,
                                     num_train=parameters.num_train,
                                     debug=parameters.debug)

    # Create a PyTorch Lightning trainer with the generation callback

    # translation_callback = TranslationCallback(save_to_disk=True)
    # inter_callback = InterpolationCallback(save_to_disk=True)
    # callbacks = [translation_callback]
    callbacks = []

    tb_logger = pl_loggers.TensorBoardLogger('logs/')
    trainer = Trainer(default_root_dir=LOG_PATH,
                      logger=tb_logger,
                      checkpoint_callback=ModelCheckpoint(save_weights_only=True),
                      gpus=1 if torch.cuda.is_available() else 0,
                      max_epochs=parameters.epochs,
                      callbacks=callbacks,
                      progress_bar_refresh_rate=1)

    # Optional logging argument that we don't need
    trainer.logger._default_hp_metric = None

    # Create model
    pl.seed_everything(parameters.seed)

    model = BiGRU(input_dim=1000,
                  output_dim=1000,
                  encoder_hid_dim=ENC_HID_DIM,
                  decoder_hid_dim=DEC_HID_DIM,
                  encoder_emb_dim=ENC_EMB_DIM,
                  decoder_emb_dim=DEC_EMB_DIM,
                  encoder_dropout=ENC_DROPOUT,
                  decoder_dropout=DEC_DROPOUT,
                  attention_type=parameters.attention,
                  pad_idx=PAD_IDX,
                  sos_idx=SOS_IDX,
                  eos_idx=EOS_IDX,
                  coeff=parameters.loss_coeff,
                  decode_with_no_attention=parameters.no_attn_inference)

    # Training
    # gen_callback.sample_and_save(trainer, model, epoch=0)  # Initial sample
    trainer.fit(model, data_module)

    # inter_callback.sample_and_save(trainer, model, epoch=0)

    return model


if __name__ == '__main__':
    # Feel free to add more argument parameters
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # Model hyperparameters
    parser.add_argument('--loss-coef', dest='loss_coeff', type=float, default=0.0)

    parser.add_argument('--attention', dest='attention', type=str, default='dot-product')

    # Optimizer hyperparameters
    parser.add_argument('--batch-size', dest='batch_size', type=int, default=128)

    # Other hyperparameters
    parser.add_argument('--task', dest='task', default='en-de',
                        choices=('copy', 'reverse-copy', 'binary-flip', 'en-hi', 'en-de'),
                        help='select the task you want to run on')

    parser.add_argument('--debug', dest='debug', action='store_true')

    parser.add_argument('--epochs', dest='epochs', type=int, default=5)

    parser.add_argument('--seed', dest='seed', type=int, default=1234)

    parser.add_argument('--num-train', dest='num_train', type=int, default=1000000)

    parser.add_argument('--decode-with-no-attn', dest='no_attn_inference', action='store_true')

    parser.add_argument('--tensorboard_log', dest='tensorboard_log', action='store_true')

    params = parser.parse_args()

    train_gru(params)
