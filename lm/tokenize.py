from argparse import ArgumentParser
from tokenizers.implementations import ByteLevelBPETokenizer
from tokenizers.processors import BertProcessing

from . import DATASET, TOKENIZER_PATH


def main():
    parser = ArgumentParser(description="Try the tokenizer.")
    parser.add_argument("text", help="Text to tokenize.")
    args = parser.parse_args()
    text = args.text

    tokenizer = ByteLevelBPETokenizer(
        f"{TOKENIZER_PATH}/vocab.json",
        f"{TOKENIZER_PATH}/merges.txt",
    )
    tokenizer._tokenizer.post_processor = BertProcessing(
        ("</s>", tokenizer.token_to_id("</s>")),
        ("<s>", tokenizer.token_to_id("<s>")),
    )
    tokenizer.enable_truncation(max_length=512)
    tokenized = tokenizer.encode(text)
    print(tokenized.tokens)
    print()
    print(tokenized.ids)
    print()
    print(tokenized.offsets)


if __name__ == '__main__':
    main()