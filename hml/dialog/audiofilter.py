"""This module implements some simple audio filtering to simulate the
sound of a noisy, low bandwidth radio communications link.
"""

import array
import logging
import random
import sys
import StringIO

# We use our patched version of the standard wave module that lets us
# write wav data to a StringIO buffer.  Silly Python.
from hml.dialog import wave


def readfile(path):
  """Reads a .wav file, returns a list containing the raw audio data.
  Assumes 16 bit samples.
  """
  win = wave.open(path, "r")
  logging.info('Num channels: %s', win.getnchannels())
  logging.info('Sample width: %s', win.getsampwidth())
  logging.info('Rate        : %s', win.getframerate())
  logging.info('num frames  : %s', win.getnframes())
  audio = win.readframes(win.getnframes())
  samples = array.array('h', audio)
  return samples


def writefile(samples, path):
  """Writes a .wav file.  Hardcoded to handle mono, 16 bit, 16 kHz
  samples.
  """
  wout = wave.open(path, "w")
  wout.setnchannels(1)
  wout.setsampwidth(2)
  wout.setframerate(16000)
  wout.writeframes(samples.tostring())
  wout.close()


def writebuffer(samples):
  """Creates a string containing .wav data.  Hardcoded to handle mono,
  16 bit, 16 kHz samples.
  """
  buf = StringIO.StringIO()
  wout = wave.open(buf, "w")
  wout.setnchannels(1)
  wout.setsampwidth(2)
  wout.setframerate(16000)
  wout.writeframes(samples.tostring())
  wout.close()
  return array.array('h', buf.getvalue())


def noise(n, amplitude=32767):
  """Returns a list containing audio samples corresponding to white
  noise.  n is the number of samples to generate, amplitude is the
  maximum amplitude of the signal.
  """
  samples = [0] * n
  for i in xrange(0, n):
    samples[i] = random.randint(-amplitude, amplitude)
  return samples


def add_noise(samples, amplitude=32767, clip=32767):
  minusclip = -clip
  for i in xrange(0, len(samples)):
    a = samples[i] + random.randrange(-amplitude, amplitude, 1)
    if a > clip:
      a = clip
    elif a < minusclip:
      a = minusclip
    samples[i] = a
  return samples


def amplify(samples, gain, clipmax=32767):
  """Multiplies audio samples by a constant factor."""
  for i in xrange(0, len(samples)):
    samples[i] = clip(samples[i] * gain, clipmax)
  return samples


def addv(a, b, clipmax=32767):
  """Sums two audio samples."""
  c = array.array(a.typecode, a)
  for i in xrange(0, len(a)):
    c[i] = clip(a[i] + b[i], clipmax)
  return c


def clip(value, clipmax):
  value = int(value)
  if value > clipmax:
    return clipmax
  elif value < -clipmax:
    return -clipmax
  else:
    return value


"""
/* Digital filter designed by mkfilter/mkshape/gencode   A.J. Fisher
   Command line: /www/usr/fisher/helpers/mkfilter -Bu -Bp -o 3 -a 1.2500000000e-01 1.8750000000e-01 -l */

#define NZEROS 6
#define NPOLES 6
#define GAIN   1.886646501e+02

static float xv[NZEROS+1], yv[NPOLES+1];

static void filterloop()
  { for (;;)
      { xv[0] = xv[1]; xv[1] = xv[2]; xv[2] = xv[3]; xv[3] = xv[4]; xv[4] = xv[5]; xv[5] = xv[6]; 
        xv[6] = next input value / GAIN;
        yv[0] = yv[1]; yv[1] = yv[2]; yv[2] = yv[3]; yv[3] = yv[4]; yv[4] = yv[5]; yv[5] = yv[6]; 
        yv[6] =   (xv[6] - xv[0]) + 3 * (xv[2] - xv[4])
                     + ( -0.4535459334 * yv[0]) + (  1.7422756094 * yv[1])
                     + ( -3.9644349217 * yv[2]) + (  5.4364736436 * yv[3])
                     + ( -5.1562441307 * yv[4]) + (  2.9564215363 * yv[5]);
        next output value = yv[6];
      }
  }
"""

NZEROS = 6
NPOLES = 6
GAIN1 = 1.886646501e+02 / 256


def filter1(sample, clipmax):
  """Runs the sample through a 3rd order bandpass filter with a
  2000-3000 Hz window.
  """
  xv = [0] * (NZEROS + 1)
  yv = [0] * (NPOLES + 1)
  result = array.array(sample.typecode, sample)
  negclipmax = -clipmax
  
  for i in xrange(0, len(samples)):
    xv[0] = xv[1]
    xv[1] = xv[2]
    xv[2] = xv[3]
    xv[3] = xv[4]
    xv[4] = xv[5]
    xv[5] = xv[6]

    xv[6] = samples[i] * GAIN1

    yv[0] = yv[1]
    yv[1] = yv[2]
    yv[2] = yv[3]
    yv[3] = yv[4]
    yv[4] = yv[5]
    yv[5] = yv[6]
    yv[6] = (xv[6] - xv[0]) + 3 * (xv[2] - xv[4]) \
            + ( -0.4535459334 * yv[0]) + (  1.7422756094 * yv[1]) \
            + ( -3.9644349217 * yv[2]) + (  5.4364736436 * yv[3]) \
            + ( -5.1562441307 * yv[4]) + (  2.9564215363 * yv[5])
    result[i] = clip(yv[6], clipmax)
  return result

"""
/* Digital filter designed by mkfilter/mkshape/gencode   A.J. Fisher
   Command line: /www/usr/fisher/helpers/mkfilter -Bu -Bp -o 3 -a 9.3750000000e-02 2.1875000000e-01 -l */

#define NZEROS 6
#define NPOLES 6
#define GAIN   3.155626221e+01

static float xv[NZEROS+1], yv[NPOLES+1];

static void filterloop()
  { for (;;)
      { xv[0] = xv[1]; xv[1] = xv[2]; xv[2] = xv[3]; xv[3] = xv[4]; xv[4] = xv[5]; xv[5] = xv[6]; 
        xv[6] = next input value / GAIN;
        yv[0] = yv[1]; yv[1] = yv[2]; yv[2] = yv[3]; yv[3] = yv[4]; yv[4] = yv[5]; yv[5] = yv[6]; 
        yv[6] =   (xv[6] - xv[0]) + 3 * (xv[2] - xv[4])
                     + ( -0.1978251873 * yv[0]) + (  0.9043292381 * yv[1])
                     + ( -2.3109942388 * yv[2]) + (  3.6253639773 * yv[3])
                     + ( -3.9282953328 * yv[4]) + (  2.6814143273 * yv[5]);
        next output value = yv[6];
      }
  }
"""

GAIN2 = 1.886646501e+02 / 256


def filter2(samples, clipmax=32767):
  """Runs the sample through a 3rd order bandpass filter with a
  1500-3500 Hz window.
  """
  xv = [0] * (NZEROS + 1)
  yv = [0] * (NPOLES + 1)
  result = array.array(samples.typecode, samples)
  for i in xrange(0, len(samples)):
    xv[0] = xv[1]
    xv[1] = xv[2]
    xv[2] = xv[3]
    xv[3] = xv[4]
    xv[4] = xv[5]
    xv[5] = xv[6]

    xv[6] = samples[i] * GAIN2

    yv[0] = yv[1]
    yv[1] = yv[2]
    yv[2] = yv[3]
    yv[3] = yv[4]
    yv[4] = yv[5]
    yv[5] = yv[6]
    yv[6] = (xv[6] - xv[0]) + 3 * (xv[2] - xv[4]) \
            + (-0.1978251873 * yv[0]) + (0.9043292381 * yv[1]) \
            + (-2.3109942388 * yv[2]) + (3.6253639773 * yv[3]) \
            + (-3.9282953328 * yv[4]) + (2.6814143273 * yv[5])
    result[i] = clip(yv[6], clipmax)
  return result


def radioify(sample):
  """Runs the audio sample through some filters to make it sound like
  it's audio from a noisy, low-bandwidth radio link.
  """
  d = filter2(sample)
  d = amplify(d, 2)
  d = amplify(d, 0.5)
  d = add_noise(d, amplitude=2000)
#  n = noise(len(d), amplitude=2000)
#  d = addv(d, n)
  return d


# If invoked from the command line, read the wav file from the first
# argument and output the transformed audio to the wav file from the
# second argument.

def main():
  d = readfile(sys.argv[1])
  d = radioify(d)
  writebuffer(d)
  writefile(d, sys.argv[2])


if __name__ == '__main__':
  main()
