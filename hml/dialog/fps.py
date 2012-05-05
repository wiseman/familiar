import sys

from energid import stemmer
from energid import parser


def fp_stem_word(word, words = [], count = 0):
  new_word = p.stem(word)
  if new_word == word:
    return [words, count]
  else:
    return fp_stem_word(new_word, words + [new_word], count + 1)
  
p = stemmer.PorterStemmer()
while 1:
  line = sys.stdin.readline()
  if line == '':
    sys.exit(0)
  line = line[:-1]
  [steps, count] = fp_stem_word(line)
  print "%s %s %s" % (count, line, steps)
