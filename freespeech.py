#!/usr/bin/env python

"""

get wordlists from:

https://github.com/bitcoin/bips/blob/master/bip-0039/bip-0039-wordlists.md
http://wordnetcode.princeton.edu/3.0/WNdb-3.0.tar.gz

extract useable nouns from wordnetcode:
$ cut -d' ' -f 5 data.noun | grep -v _ | grep -v '/' | tr '[A-Z]' '[a-z]' | sort | uniq | wc -l
40980

"""

import sys, argparse
import math
from bitstring import ReadError, BitStream, pack
from collections import deque

class FreeSpeech:
    def __init__(self, dict_filename, max_words_per_line=10, byte_buffer=65536):
        self.verbose = True
        (self.word_list, self.word_dict) = self.read_dict(dict_filename)
        #print 'word_list:', self.word_list
        #print 'word_dict:', self.word_dict
        self.num_bits = self.min_even_bits(len(self.word_dict))
        #print 'num_bits:', self.num_bits
        self.int_type = 'uint:' + str(self.num_bits)
        #print >> sys.stderr, 'int_type:', self.int_type
        self.max_words_on_line = max_words_per_line
        self.byte_buffer = byte_buffer
        self.bit_buffer = self.byte_buffer * 8
        self.word_count = 0

    def max_int(self, min_bits):
        return math.pow(2, min_bits)

    def min_bits(self, max_int):
        return math.log(max_int) / math.log(2)

    def min_even_bits(self, max_int):
        exact = self.min_bits(max_int)
        #print >> sys.stderr, 'exact:', exact
        floor = int(math.floor(exact))
        if self.verbose and exact != floor:
            print >> sys.stderr, 'There is no exact integer for min_bits, not all words will be used!'
        return floor

    def bits_to_unsigned_int(self, bits):
        num = 0
        index = 0
        for bit in bits:
            if bit == '1':
                num += math.pow(2, index)
            index += 1
        return num

    def file_to_in_stream(self, in_filename):
        return sys.stdin if in_filename == '-' else open(in_filename, 'rb')

    def file_to_out_stream(self, out_filename):
        return sys.stdout if out_filename == '-' else open(out_filename, 'wb')

    def decodeFiles(self, in_filename, out_filename):
        with self.file_to_in_stream(in_filename) as in_stream, self.file_to_out_stream(out_filename) as out_stream:
            self.decode(in_stream, out_stream)

    def encodeFiles(self, in_filename, out_filename):
        with self.file_to_in_stream(in_filename) as in_stream, self.file_to_out_stream(out_filename) as out_stream:
            self.encode(in_stream, out_stream)

    def decode(self, in_stream, out_stream):
        bs = BitStream()
        dq = deque()
        at_least_three = False
        for word in self.words_from_file(in_stream):
            if not word or word not in self.word_dict:
                continue
            #print >> sys.stderr, 'word:"', word, '"'
            dq.append(self.word_dict[word])
            if at_least_three or len(dq) == 3:
                bs.append(pack(self.int_type, dq.popleft()))
                at_least_three = True
                if bs.len > self.bit_buffer:
                    cut = 0
                    for byte in bs.cut(self.bit_buffer):
                        cut += 1
                        byte.tofile(out_stream)
                    del bs[:cut * self.bit_buffer]

        # dq has to have exactly 2 elements here, the last is the bit length of the first, unless it's 0
        #print >> sys.stderr, 'dq:', dq
        extra_bits = dq.pop()
        bs.append(pack('uint:' + str(extra_bits), dq.popleft()))

        bs.tofile(out_stream)

    def print_index(self, index, out_stream):
        #print self.word_list[index],
        out_stream.write(self.word_list[index])
        self.word_count += 1
        if self.word_count > self.max_words_on_line:
            out_stream.write('\n')
            self.word_count = 0
        else:
            out_stream.write(' ')

    def encode(self, in_stream, out_stream):
        extra_bits = self.num_bits
        bs = BitStream()
        try:
            while True:
                chunk = in_stream.read(self.byte_buffer)
                #print >> sys.stderr, 'chunk:', chunk
                if(chunk):
                    bs.append(BitStream(bytes=chunk))
                else:
                    while True:
                        self.print_index(bs.read(self.int_type), out_stream)
                try:
                    while True:
                        self.print_index(bs.read(self.int_type), out_stream)
                except ReadError, e:
                    #print >> sys.stderr, 'inner:', e
                    pass
        except ReadError, e:
            #print >> sys.stderr, 'outer:', e
            extra_bits = bs.len - bs.bitpos
            if extra_bits > 0:
                #print >> sys.stderr, 'extra_bits:', extra_bits
                self.print_index(bs.read('uint:' + str(extra_bits)), out_stream)
            else:
                extra_bits = self.num_bits
        # write extra_bits
        self.print_index(extra_bits, out_stream)

    def words_from_file(self, in_file):
        for line in in_file:
            #print 'line:', line
            words = line.split(' ')
            for word in words:
                word = word.translate(None, '`~!@#$%^&*()-_=+[{]}\|\'";:/?.>,<\t\n\v\f\r').strip()
                if word:
                    yield word

    def remove_duplicates(self, values):
        output = []
        seen = set()
        for value in values:
            if value not in seen:
                output.append(value)
                seen.add(value)
        return output

    def read_dict(self, filename):
        ret = []
        with open(filename, 'r') as dict_file:
            for word in self.words_from_file(dict_file):
                ret.append(word.strip())
        ret = self.remove_duplicates(ret)
        index = 0
        ret_dict = {}
        for word in ret:
            ret_dict[word] = index
            index += 1
        return (ret, ret_dict)

def main(argv=None):
    parser = argparse.ArgumentParser(description='FreeSpeech encode or decode IN_FILE, or standard input, to OUT_FILE or standard output.')
    parser.add_argument('-d', '--decode', dest='decode', action='store_true', help='decode data (default: encode data)')
    parser.add_argument('-i', '--in', dest='in_file', default='-', help='input file (default: - (stdin))')
    parser.add_argument('-o', '--out', dest='out_file', default='-', help='output file (default: - (stdout))')
    parser.add_argument('-m', '--max-words-per-line', dest='max_words_per_line', type=int, default=10, help='maximum words to put on one line (default: 10)')
    parser.add_argument('-b', '--byte-buffer', dest='byte_buffer', type=int, default=65536, help='size of byte buffer used when reading/writing files (default: 65536 (64MB))')
    parser.add_argument('word_list', nargs=1, help='word list file to use, must use the same one for encoding/decoding')

    args = parser.parse_args()
    #print args

    try:
        fs = FreeSpeech(args.word_list[0], args.max_words_per_line, args.byte_buffer)
        if args.decode:
            fs.decodeFiles(args.in_file, args.out_file)
        else:
            fs.encodeFiles(args.in_file, args.out_file)
        return 0
    except:
        return 1

if __name__ == '__main__':
    sys.exit(main(sys.argv))
