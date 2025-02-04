# coding=utf-8
# Copyright 2020 The HuggingFace Datasets Authors and the current dataset script contributor.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# template from : https://github.com/huggingface/datasets/blob/master/templates/new_dataset_script.py

"""Loading script for the biolang dataset for language modeling in biology."""

from __future__ import absolute_import, division, print_function

import json
import datasets


class BioLang(datasets.GeneratorBasedBuilder):
    """BioLang: a dataset to train language models in biology."""

    _CITATION = """\
    @Unpublished{
        huggingface: dataset,
        title = {biolang},
        authors={Thomas Lemberger, EMBO},
        year={2021}
    }
    """

    _DESCRIPTION = """\
    This dataset is based on abstracts from the open access section of EuropePubMed Central to train language models in the domain of biology. 
    """

    _HOMEPAGE = "https://europepmc.org/downloads/openaccess"

    _LICENSE = "CC BY 4.0"

    _URLS = {
        "biolang": "https://huggingface.co/datasets/EMBO/biolang/resolve/main/oapmc_abstracts_figs.zip",
    }

    VERSION = datasets.Version("0.0.1")

    BUILDER_CONFIGS = [
        datasets.BuilderConfig(name="SEQ2SEQ", version="0.0.1", description="Control dataset with no masking for seq2seq task."),
        datasets.BuilderConfig(name="MLM", version="0.0.1", description="Dataset for general masked language model."),
        datasets.BuilderConfig(name="DET", version="0.0.1", description="Dataset for part-of-speech (determinant) masked language model."),
        datasets.BuilderConfig(name="VERB", version="0.0.1", description="Dataset for part-of-speech (verbs) masked language model."),
        datasets.BuilderConfig(name="SMALL", version="0.0.1", description="Dataset for part-of-speech (determinants, conjunctions, prepositions, pronouns) masked language model."),
        datasets.BuilderConfig(name="NOUN", version="0.0.1", description="Dataset for part-of-speech (nouns) masked language model."),
    ]

    DEFAULT_CONFIG_NAME = "MLM"  # It's not mandatory to have a default configuration. Just use one if it make sense.

    def _info(self):
        if self.config.name == "MLM":
            features = datasets.Features({
                "input_ids": datasets.Sequence(feature=datasets.Value("int32")),
                "special_tokens_mask": datasets.Sequence(feature=datasets.Value("int8")),
            })
        elif self.config.name in ["DET", "VERB", "SMALL", "NOUN", "NULL"]:
            features = datasets.Features({
                "input_ids": datasets.Sequence(feature=datasets.Value("int32")),
                "tag_mask": datasets.Sequence(feature=datasets.Value("int8")),
            })
        elif self.config.name == "SEQ2SEQ":
            features = datasets.Features({
                "input_ids": datasets.Sequence(feature=datasets.Value("int32")),
                "labels": datasets.Sequence(feature=datasets.Value("int32"))
            })

        return datasets.DatasetInfo(
            description=self._DESCRIPTION,
            features=features,  # Here we define them above because they are different between the two configurations
            supervised_keys=('input_ids', 'pos_mask'),
            homepage=self._HOMEPAGE,
            license=self._LICENSE,
            citation=self._CITATION,
        )

    def _split_generators(self, dl_manager):
        """Returns SplitGenerators."""
        if self.config.data_dir:
            data_dir = self.config.data_dir
        else:
            url = self._URLS["biolang"]
            data_dir = dl_manager.download_and_extract(url)
            data_dir += "/oapmc_abstracts_figs"
        return [
            datasets.SplitGenerator(
                name=datasets.Split.TRAIN,
                gen_kwargs={
                    "filepath": data_dir + "/train.jsonl",
                    "split": "train",
                },
            ),
            datasets.SplitGenerator(
                name=datasets.Split.TEST,
                gen_kwargs={
                    "filepath": data_dir + "/test.jsonl",
                    "split": "test"
                },
            ),
            datasets.SplitGenerator(
                name=datasets.Split.VALIDATION,
                gen_kwargs={
                    "filepath": data_dir + "/eval.jsonl",
                    "split": "eval",
                },
            ),
        ]

    def _generate_examples(self, filepath, split):
        """ Yields examples. """
        with open(filepath, encoding="utf-8") as f:
            for id_, row in enumerate(f):
                data = json.loads(row)
                if self.config.name == "MLM":
                    yield id_, {
                        "input_ids": data["input_ids"],
                        "special_tokens_mask": data['special_tokens_mask']
                    }
                # else Part of Speech tags based on 
                # Universal POS tags https://universaldependencies.org/u/pos/
                elif self.config.name == "DET":
                    pos_mask = [0] * len(data['input_ids'])
                    for idx, label in enumerate(data['label_ids']):
                        if label == 'DET':
                            pos_mask[idx] = 1
                    yield id_, {
                        "input_ids": data['input_ids'],
                        "tag_mask": pos_mask,
                    }
                elif self.config.name == "VERB":
                    pos_mask = [0] * len(data['input_ids'])
                    for idx, label in enumerate(data['label_ids']):
                        if label == 'VERB':
                            pos_mask[idx] = 1
                    yield id_, {
                        "input_ids": data['input_ids'],
                        "tag_mask": pos_mask,
                    }
                elif self.config.name == "SMALL":
                    pos_mask = [0] * len(data['input_ids'])
                    for idx, label in enumerate(data['label_ids']):
                        if label in ['DET', 'CCONJ', 'SCONJ', 'ADP', 'PRON']:
                            pos_mask[idx] = 1
                    yield id_, {
                        "input_ids": data['input_ids'],
                        "tag_mask": pos_mask,
                    }
                elif self.config.name == "NOUN":
                    pos_mask = [0] * len(data['input_ids'])
                    for idx, label in enumerate(data['label_ids']):
                        if label in ['NOUN']:
                            pos_mask[idx] = 1
                    yield id_, {
                        "input_ids": data['input_ids'],
                        "tag_mask": pos_mask,
                    }
                elif self.config.name == "SEQ2SEQ":
                    "Seq2seq training needs the input_ids as labels, no masking"
                    pos_mask = [0] * len(data['input_ids'])
                    yield id_, {
                        "input_ids": data['input_ids'],
                        "labels": data['input_ids']
                    }
