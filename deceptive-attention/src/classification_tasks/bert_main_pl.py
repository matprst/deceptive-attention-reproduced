# Global dependencies
import argparse
# 3rd party transformer code
import transformers
import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer, BertForSequenceClassification
# PyTorch Modules
from pytorch_lightning import Trainer
from pytorch_lightning.core.lightning import LightningModule
from pytorch_lightning import loggers as pl_loggers
from torch.optim import Adam
from torch.cuda import device_count

import sys
import time

# Local dependencies
from bert_attention import BertSelfAttention_Altered, BertModel_Altered, BertEncoder_Altered
from bert_util_pl import GenericDataModule

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

class BERTModel(LightningModule):

    def __init__(self, dropout, penalize, lambeda, penalty_fn):
        super().__init__()
        """
        Args:
            penalize: flag to toggle attention manipulation and information flow restriction
            tokenizer: transformers object used to convert raw text to tensors
        """
        self.dropout = dropout
        self.penalize = penalize
        self.lambeda = lambeda
        self.penalty_fn = penalty_fn
        self.tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased') #TODO: use a faster tokenizer?

        if self.penalize:
            # if we're penalizing the model's attending to impermissible tokens, we want to overwrite the original
            # self-attention class in the transformers library with a local class which has been adapted to ensure
            # # the restriction of information flow between permissible and impermissible tokens
            transformers.models.bert.modeling_bert.BertSelfAttention = BertSelfAttention_Altered

        # load pretrained, uncased model
        self.encoder = BertForSequenceClassification.from_pretrained('bert-base-uncased',
                                                                     num_labels=2,
                                                                     hidden_dropout_prob=self.dropout)

    def configure_optimizers(self):
        "This method handles optimization of params for PyTorch lightning"
        return Adam(self.parameters(), lr=config.lr)

    def forward(self, x, attention_mask, labels, mask_matrices):
        "This method defines how the data is passed through the net."
        output = self.encoder(x,
                              labels=labels,
                              attention_mask=attention_mask,
                              head_mask=mask_matrices,
                              output_attentions=True)

        return output

    def training_step(self, batch, batch_idx):
        """
        This method implements the training step in PyTorch Lightning
        """

        # extract labels, sentences and vector masks m
        labels = batch['labels']
        sentences = batch['sentences']
        attention_masks = batch['attention_masks']
        mask_vectors = batch['mask_vectors']
        mask_matrices = batch['mask_matrices'].unsqueeze(1) # add necessary implicit 1st dim

        # flag to toggle manipulation of attention maps
        if self.penalize:

            # Feed sentences through network
            outputs = self(x=sentences, attention_mask=attention_masks, mask_matrices=None, labels=labels)

            # Compute loss w.r.t. predictions and labels
            loss = outputs.loss

            # Compute R component and add to loss
            R = self.compute_R(outputs, mask_vectors, self.lambeda, self.penalty_fn).mean()
            loss += R

        # Log loss to Tensorboard
        self.log('training_loss', loss, on_step=True, prog_bar=True, logger=True)
        self.log('train_penalty_R', R, on_step=True, prog_bar=True, logger=True)
        return loss

    def validation_step(self, batch, batch_idx):
        """
        This method implements the training step in PyTorch Lightning
        """

        # extract labels, sentences and vector masks m
        labels = batch['labels']
        sentences = batch['sentences']
        mask_vectors = batch['mask_vectors']
        attention_masks = batch['attention_masks']
        mask_matrices = batch['mask_matrices'].unsqueeze(1)

        # flag to toggle manipulation of attention maps
        if self.penalize:

            # Feed sentences through network
            outputs = self(x=sentences, attention_mask=attention_masks, mask_matrices=None, labels=labels)

            # Compute loss w.r.t. predictions and labels
            loss = outputs.loss

            # Compute loss w.r.t. predictions and labels
            loss = outputs.loss

            # Compute R component and add to loss
            R = self.compute_R(outputs, mask_vectors, self.lambeda, self.penalty_fn).mean()
            loss += R

        # Log loss to Tensorboard
        self.log('dev_loss', loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        self.log('dev_penalty_R', R, on_step=True, prog_bar=True, logger=True)

        return None

    def test_step(self, batch, batch_idx):
        "This method handles the test logic in PyTorch Lightning"

        # extract label, sentence and set of impermissible words per sentence from batch
        labels = batch['label']
        sents = batch['sentence']
        impermissible = batch['impermissible']

        # # Tokenize batch of sentences
        tokenized_sents = self.tokenizer(sents, padding=True, truncation=False, return_tensors="pt")

        # Tokenize batch of impermissibles
        tokenized_impermissible = self.tokenizer(impermissible, padding=False, truncation=True, return_tensors="pt")

        # TODO: using sentence_ids and impermissible words, generate self-attention matrix per sentence
        if self.penalize:

            # Generate self attention mask based on permissible and impermissible token ids
            # self_attention_masks = self.generate_mask(tokenized_sents["input_ids"],
            #                                      tokenized_impermissible["input_ids"])

            outputs = self(x=tokenized_sents['input_ids'], labels=labels)
            # Compute loss w.r.t. predictions and labels
            loss = outputs.loss

            # Add penalty R to loss
            # TODO compute R component

        # Log loss to Tensorboard
        self.log('test_loss', loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)

        return None

    def convert2vectors(self, matrices):
        """
        This function takes as its input a tuple with self-attention matrices,
        of shape [batch_size, num_layers, num_heads, sequence_length, sequence_length],
        and returns a tensor with self-attention vectors, of shape
        [batch_size, num_layers, num_heads, sequence_length], by taking the max along the row-dimension.
        """

        # convert tuple of tensors to tensor of tensors (= a tensor)
        matrices = torch.stack(matrices)

        # for some reason, torch.stack switches the layer and batch dimension, which we do not want
        matrices = matrices.permute(1, 0, 2, 3, 4)

        # take max of n x n attention maps along row-dimension
        matrices, _ = torch.max(matrices, dim=3, out=None)

        # renormalize to 1?
        m = nn.Softmax(dim=3)
        matrices[matrices == 0.0] = -9999
        matrices = m(matrices)

        return matrices

    def compute_R(self, outputs, mask_vectors, lambeda, penalty_fn):
        """
        This function computes the R component, which serves as the penalizing mechanism as described in the paper
        """

        # extract self-attention maps of shape [batch_size, num_layers, num_heads, sequence_length, sequence_length]
        attention_matrices = outputs.attentions

        # convert attention matrices to vectors
        attention_vectors = self.convert2vectors(attention_matrices)

        sequence_length = attention_vectors.shape[-1]
        if penalty_fn == 'mean':

            # reshape tensor of shape batch_size * 12 x 12 x seq_length to
            # shape batch_size, 144, seq_length
            attention_vectors = attention_vectors.reshape(config.batch_size, 12**2, sequence_length)

            # add implicit dimension to mask_vectors such that it becomes a rank-4 tensor
            mask_vectors = mask_vectors.unsqueeze(1)

            # compute impermissible attention tensor of shape (batch_size, ||Heads H||, seq_length)
            impermissible_attention = attention_vectors * mask_vectors

            # Sum over last dim to get impermissible attention per head
            impermissible_attention = torch.sum(impermissible_attention, dim=2)

            # Compute the complement of impermissible attention, or permissible attention
            permissible_attention = 1 - impermissible_attention

            # log permissible attention per head
            log_permissible_attention = torch.log(permissible_attention)

            # Compute R value using 'mean' method by summing over H dimension and dividing by 144
            R = (-lambeda/144)*(torch.sum(log_permissible_attention, dim=1))

            return R


def main(args):

    print('\n -------------- Classification with BERT -------------- \n')
    # print CLI args
    print('Arguments: ')
    for arg in vars(args):
        print(str(arg) + ': ' + str(getattr(args, arg)))
    print('no of devices found: {}'.format(device_count()))

    # Logic to define model with specified R calculation, specified self attn mask
    model = BERTModel(dropout=config.dropout, penalize=config.penalize, lambeda=config.lambeda, penalty_fn=config.penalty_fn)


    # Main Lightning code
    tb_logger = pl_loggers.TensorBoardLogger('logs/')
    trainer = Trainer(gpus=config.gpus, logger=tb_logger)
    dm = GenericDataModule(task=config.task,
                           anonymization=config.anon,
                           max_length=config.max_length,
                           batch_size=config.batch_size)
    # dm.setup()
    trainer.fit(model, dm)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    # Learning specific args
    parser.add_argument('--gpus', default=None)

    parser.add_argument('--batch_size', default=16, type=int,
                        help='no. of sentences sampled per pass')
    parser.add_argument('--lr', default=5e-5, type=float,
                        help='learning rate')
    parser.add_argument('--dropout', default=0.3, type=float,
                        help='hidden layer dropout prob')
    parser.add_argument('--max_length', default=180, type=int,
                        help='max no of tokens for tokenizer (default is enough for all tasks')

    # Task specific args
    parser.add_argument('--task', default='occupation', type=str,
                        help='arg to specify task to train on')
    parser.add_argument('--anon', default=False, type=bool,
                        help='arg to toggle anonymized tokens')
    parser.add_argument('--penalize', default=True, type=bool,
                        help='flag to toggle penalisation of attn to impermissible words')
    parser.add_argument('--lambeda', default=1, type=float,
                        help='penalty coefficient')
    parser.add_argument('--penalty_fn', default='mean', type=str,
                        help='penalty fn [options: mean or max')

    config = parser.parse_args()

    main(config)