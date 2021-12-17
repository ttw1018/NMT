import torch
from torch import nn
from model.embedding_model import EmbeddingModel
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
import torch.nn.functional as F


class NMT(nn.Module):
    def __init__(self, embed_size, hidden_size, vocab, dropout_rate=0.1):
        super(NMT, self).__init__()
        self.model_embedding = EmbeddingModel(embed_size, vocab)
        self.embed_size = embed_size
        self.hidden_size = hidden_size
        self.vocab = vocab
        self.encoder = nn.LSTM(embed_size, hidden_size, bidirectional=True)
        self.decoder = nn.LSTMCell(hidden_size + embed_size, hidden_size)
        self.h_projection = nn.Linear(2*self.hidden_size, self.hidden_size)
        self.c_projection = nn.Linear(2*self.hidden_size, hidden_size)
        self.att_projection = nn.Linear(2*self.hidden_size, self.hidden_size)
        self.combined_projection = nn.Linear(self.hidden_size, len(vocab.tgt))
        self.target_vocab_projection = nn.Linear(hidden_size, len(vocab.tgt))
        self.dropout = nn.Dropout(dropout_rate)

    def encode(self, source_padded, source_lengths):
        X = self.model_embedding.source(source_padded)
        packed_seq = pack_padded_sequence(X, source_lengths)
        enc_hidden, (last_hidden, last_cell) = self.encoder(packed_seq)
        enc_hidden = pad_packed_sequence(enc_hidden)
        init_decode_hidden = self.h_projection(
            torch.cat((last_hidden[0], last_hidden[1]), 1))
        init_decode_cell = self.c_projection(
            torch.cat((last_cell[0], last_cell[1]), 1))
        return enc_hidden, (init_decode_hidden, init_decode_cell)

    def decode(self, enc_hidden, enc_masks, dec_init_state, target_padded):
        target_padded = target_padded[:-1]
        batch_size = enc_hidden.shape[0]
        o_prev = torch.zeros(batch_size, self.hidden_size)
        combined_outputs = []
        enc_hidden_proj = self.att_projection(enc_hidden)
        Y = self.model_embedding(target_padded)
        Y_ts = torch.split(Y, 1, dim=0)
        for y_t in Y_ts:
            y_t = y_t.squeeze()
            ybar_t = torch.cat((y_t, o_prev), 1)
            dec_state, o_prev, _ = self.step(ybar_t, dec_state, enc_hidden, enc_hidden_proj, enc_masks)
            combined_outputs.append(o_prev)
        combined_outputs = torch.stack(combined_outputs)
        return combined_outputs

    def step(self, ybar_t, dec_state, enc_hidden, enc_hidden_proj, enc_masks):
        dec_state = self.decoder(ybar_t, dec_state)
        dec_hidden, dec_cell = dec_state
        e_t = torch.bmm(enc_hidden, dec_hidden.unqueeze(2))
        e_t = e_t.squeeze(2)
        if enc_masks is not None:
            e_t.data.masked_fill_(enc_masks.bool(), -float('inf'))
        alpha_t = torch.softmax(e_t, 1).unsqueeze(1)
        a_t = torch.bmm(alpha_t, enc_hidden).squeeze()
        U_t = torch.cat((dec_hidden, a_t), 1)
        V_t = self.combined_projection(U_t)
        O_t = self.dropout(torch.tanh(V_t))
        combined_output = O_t
        return dec_state, combined_output, e_t

    def forward(self, source, target):
        source_lengths = [len(s) for s in source]
        source_padded = self.vocab.src.to_input_tensor(source)
        target_padded = self.vocab.tgt.to_input_tensor(target)
        enc_hidden, dec_init_state = self.encode(source_padded, source_lengths)
        enc_masks = self.generate_sent_masks(enc_hidden, source_lengths)
        combined_outputs = self.decode(enc_hidden, enc_masks, dec_init_state, targed_padded)
        P = F.log_softmax(self.target_vocab_projection(combined_outputs), -1)
        target_masks = target_padded != self.vocab.tgt['<pad>'].float()
        i = target_padded[1:].unsqueeze(-1)
        j = torch.gather(P, index=i, dim=-1)
        target_gold_words_log_prob = j.squeeze(-1) * target_masks[1:]
        scores = target_gold_words_log_prob.sum(dim=0)
        print(scores.shape)
        return scores



    def generate_sent_masks(self, enc_hidden, source_lengths):
        enc_masks = torch.zeros(enc_hidden.size[:2], dtype=torch.float)
        for e_id, src_len in enumerate(source_lengths):
            enc_masks[e_id, src_len:] = 1
        return enc_masks


