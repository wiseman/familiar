import struct
import random
import sys

from hml.dialog import wave


def readfile(path):
  win = wave.open(path, "r")
  print "num channels: %s" % (win.getnchannels(),)
  print "sample width: %s" % (win.getsampwidth(),)
  print "rate        : %s" % (win.getframerate(),)
  print "num frames  : %s" % (win.getnframes(),)
  audio = win.readframes(win.getnframes())
  words = []
  fmt = "%sh" % (len(audio) / 2,)
  words = struct.unpack(fmt, audio)
  return words


def noise(length, amplitude=32767):
  words = []
  for unused_i in range(0, length):
    words.append(random.randint(-amplitude, amplitude))
  return words


def writefile(words, path):
  wout = wave.open(path, "w")
  wout.setnchannels(1)
  wout.setsampwidth(2)
  wout.setframerate(16000)
  fmt = "%sh" % (len(words),)
  string = apply(struct.pack, [fmt] + words)
  wout.writeframes(string)
  wout.close()


def amplify(words, gain, clip=32767):
  result = []
  for word in words:
    prod = word * gain
    result.append(prod)
  return result


def sumv(a, b, clip=32767):
  c = []
  for i in range(0, len(a)):
    sum_i = a[i] + b[i]
    c.append(sum_i)
  return c


def clean(words, clip):
  result = []
  for word in words:
    word = int(word)
    if word < -clip:
      word = -clip
    elif word > clip:
      word = clip
    result.append(word)
  return result


# Digital filter designed by mkfilter/mkshape/gencode   A.J. Fisher
# Command line: /www/usr/fisher/helpers/mkfilter -Bu -Bp -o 3 -a \
#               1.2500000000e-01 1.8750000000e-01 -l */

# #define NZEROS 6
# #define NPOLES 6
# #define GAIN   1.886646501e+02

# static float xv[NZEROS+1], yv[NPOLES+1];

# static void filterloop()
#   { for (;;)
#       { xv[0] = xv[1]; xv[1] = xv[2];
#         xv[2] = xv[3]; xv[3] = xv[4];
#         xv[4] = xv[5]; xv[5] = xv[6];
#         xv[6] = next input value / GAIN;
#         yv[0] = yv[1]; yv[1] = yv[2];
#         yv[2] = yv[3]; yv[3] = yv[4];
#         yv[4] = yv[5]; yv[5] = yv[6];
#         yv[6] =   (xv[6] - xv[0]) + 3 * (xv[2] - xv[4])
#                      + ( -0.4535459334 * yv[0]) + (  1.7422756094 * yv[1])
#                      + ( -3.9644349217 * yv[2]) + (  5.4364736436 * yv[3])
#                      + ( -5.1562441307 * yv[4]) + (  2.9564215363 * yv[5]);
#         next output value = yv[6];
#       }
#   }

NZEROS = 6
NPOLES = 6
GAIN = 1.886646501e+02 / 256


def filter(data):
  xv = [0] * (NZEROS + 1)
  yv = [0] * (NPOLES + 1)
  result = []
  for word in data:
    xv[0] = xv[1]
    xv[1] = xv[2]
    xv[2] = xv[3]
    xv[3] = xv[4]
    xv[4] = xv[5]
    xv[5] = xv[6]

    xv[6] = word * GAIN

    yv[0] = yv[1]
    yv[1] = yv[2]
    yv[2] = yv[3]
    yv[3] = yv[4]
    yv[4] = yv[5]
    yv[5] = yv[6]
    yv[6] = (xv[6] - xv[0]) + 3 * (xv[2] - xv[4]) \
            + (-0.4535459334 * yv[0]) + (1.7422756094 * yv[1]) \
            + (-3.9644349217 * yv[2]) + (5.4364736436 * yv[3]) \
            + (-5.1562441307 * yv[4]) + (2.9564215363 * yv[5])
    result.append(yv[6])
  return result


def radioify(data):
  d = filter(data)
  d = amplify(d, 2)
  d = clean(d, 32767)
  d = amplify(d, 1.0 / 2)
  n = noise(len(d), amplitude=2000)
  d = sumv(d, n)
  d = clean(d, 32767)
  return d


def main():
  d = readfile(sys.argv[1])
  d = radioify(d)
  writefile(d, sys.argv[2])


if __name__ == '__main__':
  main()
