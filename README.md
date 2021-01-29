# Deceive with Attention-Based Explanations

This repository and paper have been conducted during the Fairness, Accountability, Confidentiality and Transparency (FACT) course at University of Amsterdam. 
Starting off with reproducing the original paper `Learning to Deceive with Attention-Based Explanations` we extend upon it with <TODO>.
  

# Organisation of the Repository

Following the author's repository, we divided the codebase into [```classification```](deceptive-attention/src/classification) and [```seq2seq```](deceptive-attention/src/seq2seq) subfolders. In ```classification```, you can find both code used for *reproducing* the results, and code for *replicating* the results (specifically, see the [```BERT_replication```](deceptive-attention/src/classification/BERT_replication) subfolder).

# Running the Experiments

## Environment Configuration

In order to run the code either create an Anaconda environment:

```
conda env create -f env.yml
```

Please note that for the *replication* code, [```a separate environment```](deceptive-attention/src/classification/BERT_replication/BERT_env.yml) should be installed as this part of the code employs more recent libraries.

## Datasets

We do provide the data for all classification experiments in this repository. See the [classification data folder](deceptive-attention/src/classification/data) to check it out.

For seq2seq tasks we have a compressed version of the data within this repo. In order to use it:

1. Browse to the [seq2seq data folder](deceptive-attention/src/seq2seq/).
2. Unzip the [data file](deceptive-attention/src/seq2seq/data.zip)

Now when running experiments this data can be used by our models.

## Classification Reproduction


## Classification BERT Replication

For the BERT replication, all 7 experiments for a specified task and seed can be produced by running:
```
python bert_main_pl_experiments.py
```

## Sequence To Sequence Reproduction

Sequence to sequence tasks can be run using the [main.py](deceptive-attention/src/seq2seq/author-based/main.py) script. It provides various arguments for running the experiments with different configurations.

```
python main.py [-h] [--task {copy, reverse-copy, binary-flip, en-de}]
               [--debug] [--loss-coef LOSS_COEFF] [--epochs EPOCHS]
               [--seed SEED] [--attention ATTENTION] [--batch-size BATCH_SIZE]
               [--num-train NUM_TRAIN] [--decode-with-no-attn]
               [--tensorboard_log]
```

# Authors

- Rahel Habacker
- Andrew Harrison
- Mathias Parisot
- Ard Snijders

# Acknowledgements

The original implementation and paper that we base on have been proposed by:

> Learning to Deceive with Attention-Based Explanations \
> Danish Pruthi, Mansi Gupta, Bhuwan Dhingra, Graham Neubig, Zachary C. Lipton \
> 2020 (https://arxiv.org/abs/1909.07913)

Full credits for proposed methods used from this paper belong to these authors. Huge parts of the code we provide in this repository are based on their Github repository: https://github.com/danishpruthi/deceptive-attention.

Furthermore, a part of the code-base relies on the transformers library - however, we had to make several changes to some of the functionalities in this library, and therefore a local copy of this library - [```transformers_editted```](FACT/tree/feature/MLRC-submission-code/deceptive-attention/src/classification/BERT_replication/transformers_editted) - is included in this repository. 

