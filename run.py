import sys
from model.nmt_model import NMT
import torch
from model.vocab import read_corpus
import time
from utils import batch_iter
from model.vocab import Vocab
from torch import nn


def parser():
    argv = dict()
    for i in sys.argv[1:]:
        if i[:2] != '--':
            raise "command samples: [test|train] --command=type"
        else:
            lst = i[2:].split('=')
            argv[lst[0]] = 'None' if len(lst) <= 1 else lst[1]
    return argv


def test(argv):
    pass


def train(argv):
    train_data = read_corpus(argv['data-path'])
    batch_size = int(argv['batch-size'])
    valid_iter = int(argv['valid-iter'])

    print("loading vocab")
    vocab = Vocab.load("vocab.json")
    print("load vocab success")
    model = NMT(int(argv["embed-size"]), int(argv["hidden-size"]), vocab, float(argv["dropout-rate"]))
    model.train()

    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    print("device: ", device)

    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    model = model.to(device)

    epoches = int(argv['epoches'])
    epoch = 0
    while epoch < epoches:
        epoch = epoch + 1
        cnt = 0
        for src_sents, tgt_sents in batch_iter(train_data, batch_size):
            loss = model(src_sents, tgt_sents)
            loss.backward()
            optimizer.zero_grad()
            optimizer.step()

            if cnt % 20 == 0:
                print("epoch: {} cnt: {}, loss: {}".format(epoch, cnt, loss.mean()))
            cnt = cnt + 1
    model.save("model.bin")

def main():
    argv = parser()
    if 'train' in argv:
        train(argv)
    elif 'test' in argv:
        test(argv)
    else:
        raise "wrong command"


if __name__ == "__main__":
    main()
