# https://github.com/huggingface/blog/blob/master/notebooks/01_how_to_train.ipynb
# Just for reference... 
# Roberta:
# We consider five English-language corpora of varying sizes and domains, 
# totaling over 160GB of uncompressed text.
# The model was trained on 1024 V100 GPUs for 500K steps with a batch size of 8K 
# and a sequence length of 512. 
# The optimizer used is Adam with a learning rate of 6e-4, 
# \beta_{1} = 0.9  \beta_{2} = 0.98β and \epsilon = 1e-6
# a weight decay of 0.01, learning rate warmup for 24,000 steps 
# and linear decay of the learning rate after.

from typing import NamedTuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
import torch
from transformers import (
    Trainer,
    IntervalStrategy,
    RobertaForMaskedLM, RobertaConfig,
    AutoModelForMaskedLM, AutoTokenizer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    DataCollatorForSeq2Seq,
)
from transformers.integrations import TensorBoardCallback
from datasets import load_dataset, GenerateMode
from ..models.vae import BecauseForMaskedLM, BecauseConfig
from ..data_collator import DataCollatorForTargetedMasking

from ..trainer import MyTrainer
from ..show import ShowExampleLM
from ..metrics import compute_metrics_lm
from ..tb_callback import MyTensorBoardCallback

from ..config import config
from .. import LM_MODEL_PATH, CACHE, RUNS_DIR


# changing default values
@dataclass
class TrainingArgumentsLM(TrainingArguments):
    output_dir: str = field(default=LM_MODEL_PATH)
    overwrite_output_dir: bool = field(default=True)
    logging_steps: int = field(default=100)
    evaluation_strategy: str = IntervalStrategy.STEPS
    prediction_loss_only: bool = field(default=True)  # crucial to avoid OOM at evaluation stage!
    per_device_train_batch_size: int = field(default=16)
    per_device_eval_batch_size: int = field(default=16)
    learning_rate: float = field(default=5e-5)
    save_total_limit: int = field(default=5)
    num_train_epochs: int = field(default=10)
    # eval_accumulation_steps: int = field(default=2)  # to avoid out of memory at evaluation step that otherwise accumulates ALL the eval stesp on GPU


def train(
    training_args: TrainingArgumentsLM,
    loader_path: str,
    data_config_name: str,
    data_dir: str,
    no_cache: bool,
    tokenizer: AutoTokenizer = config.tokenizer,
    model_type: str = config.model_type,
    from_pretrained: str = config.from_pretrained
):

    training_args.logging_dir = f"{RUNS_DIR}/lm-{data_config_name}-{datetime.now().isoformat().replace(':','-')}"
    output_dir_path = Path(training_args.output_dir)
    if not output_dir_path.exists():
        output_dir_path.mkdir()
        print(f"Created {output_dir_path}.")

    print(f"tokenizer vocab size: {tokenizer.vocab_size}")

    print(f"\nLoading datasets found in {data_dir}.")
    print(f"using {loader_path} as dataset loader.")
    train_dataset, eval_dataset, test_dataset = load_dataset(
        path=loader_path,  # to the dataset loading script: a dataset repository on the HF hub with a dataset script (if the script has the same name as the directory) -> load the dataset builder from the dataset script in the dataset repository e.g. 'username/dataset_name', a dataset repository on the HF hub containing a dataset script ‘dataset_name.py
        name=data_config_name,  # the name of the dataset configuration name
        data_dir=data_dir,  # the data_dir owhere the files for the dataset configuration are found
        split=["train", "validation", "test"],
        download_mode=GenerateMode.FORCE_REDOWNLOAD if no_cache else GenerateMode.REUSE_DATASET_IF_EXISTS,
        cache_dir=CACHE
    )

    if data_config_name in ["DET", "NOUN", "VERB", "SMALL", "ROLES"]:
        if config.model_type == "Autoencoder":
            data_collator = DataCollatorForTargetedMasking(
                tokenizer=tokenizer,
                mlm_probability=1.0
            )
        elif config.model_type == "GraphRepresentation":
            data_collator = DataCollatorForTargetedMasking(
                tokenizer=tokenizer,
                mlm_probability=0.5,
                pad_to_multiple_of=config.max_length  
            )
        else:
            raise ValueError(f"unknown config.model_type: {model_type}")
    elif data_config_name == "MLM":
        if config.model_type == "Autoencoder":
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=True
            )
        elif config.model_type == "GraphRepresentation":
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=True,
                pad_to_multiple_of=config.max_length
            )
        else:
            raise ValueError(f"unknon config.model_type: {model_type}")
    elif data_config_name == "SEQ2SEQ":
        data_collator = DataCollatorForSeq2Seq(
            tokenizer=tokenizer,
            pad_to_multiple_of=config.max_length
        )
    else:
        raise NotImplementedError(f"{data_config_name} is not implemented")

    print(f"\nTraining with {len(train_dataset)} examples.")
    print(f"Evaluating on {len(eval_dataset)} examples.")

    if model_type == "Autoencoder":
        if config.from_pretrained:
            model = AutoModelForMaskedLM.from_pretrained(from_pretrained)
        else:
            model_config = RobertaConfig(
                vocab_size=tokenizer.vocab_size,
                max_position_embeddings=config.max_length + 2,  # max_length + 2 for start/end token
                num_attention_heads=12,
                num_hidden_layers=6,
                type_vocab_size=1,
            )
            model = RobertaForMaskedLM(config=model_config)
    elif model_type == "GraphRepresentation":
        if config.from_pretrained:
            seq2seq = AutoModelForMaskedLM.from_pretrained(from_pretrained)  # use AutoModel instead? since LM head is provided by BecauseLM
            model_config = BecauseConfig(
                freeze_pretrained='encoder',
                hidden_features=128,
                num_nodes=50,
                num_edge_features=6,
                num_node_features=100,
                sample_num_entities=20, #5,
                sample_num_interactions=20, #10,
                sample_num_interaction_types=3,
                sampling_iterations=1000,
                alpha=1E6,
                beta=1E7,
                seq_length=config.max_length,
                residuals=False,
            )
            model = BecauseForMaskedLM(
                pretrained=seq2seq,
                config=model_config
            )
        else:
            raise ValueError("Training GraphRepresentation from scratch is not implemented.")

    training_args.remove_unused_columns = False  # we need pos_mask and special_tokens_mask in collator

    print("\nTraining arguments:")
    print(training_args)
    if model_type == "GraphRepresentation":
        trainer = MyTrainer(
            model=model,
            args=training_args,
            data_collator=data_collator,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            compute_metrics=compute_metrics_lm,
            callbacks=[ShowExampleLM(tokenizer, detailed=True)],
        )
    else:
        trainer = Trainer(
            model=model,
            args=training_args,
            data_collator=data_collator,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            compute_metrics=compute_metrics_lm,
            callbacks=[ShowExampleLM(tokenizer, detailed=True)],
        )

    # switch the Tensorboard callback to plot losses on same plot
    trainer.remove_callback(TensorBoardCallback)  # remove default Tensorboard callback
    trainer.add_callback(MyTensorBoardCallback)  # replace with customized callback

    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print('Available devices ', torch.cuda.device_count())
        print('Current cuda device ', torch.cuda.current_device())

    trainer.train()
    trainer.save_model(training_args.output_dir)

    print(f"Testing on {len(test_dataset)}.")
    trainer.args.prediction_loss_only = False
    pred: NamedTuple = trainer.predict(test_dataset, metric_key_prefix="test")
    print(f"{pred.metrics}")
