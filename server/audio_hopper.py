#!/usr/bin/python -O
import binascii
import struct
import math
import base64

def mp3_crc(fname, blockcount = -1, skipcrc = False):
  frame_sig = []
  start_byte = []

  freqTable = [ 44100, 48000, 32000, 0 ]

  brTable = [
    0,   32,  40,  48, 
    56,  64,  80,  96, 
    112, 128, 160, 192, 
    224, 256, 320, 0
  ]

  f = open(fname, 'rb')
  while blockcount != 0:
    blockcount -= 1

    frame_start = f.tell()
    header = f.read(2)
    if header:

      if header == '\xff\xfb' or header == '\xff\xfa':
        b = ord(f.read(1))

        samp_rate = freqTable[(b & 0x0f) >> 2]
        bit_rate = brTable[b >> 4]
        pad_bit = (b & 0x3) >> 1

        # from http://id3.org/mp3Frame
        frame_size = (144000 * bit_rate / samp_rate) + pad_bit

        # Rest of the header
        throw_away = f.read(1)

        # Get the signature
        crc = binascii.crc32(f.read(32))

        frame_sig.append(crc)

        start_byte.append(frame_start)

        # Move forward the frame f.read size + 4 byte header
        throw_away = f.read(frame_size - 36)

      #ID3 tag for some reason
      elif header == '\x49\x44':
        # Rest of the header
        throw_away = f.read(4)

        # Quoting http://id3.org/d3v2.3.0
        #
        # The ID3v2 tag size is encoded with four bytes where the most
        # significant bit (bit 7) is set to zero in every byte, making a total
        # of 28 bits. The zeroed bits are ignored, so a 257 bytes long tag is
        # represented as $00 00 02 01.
        #
        candidate = struct.unpack('>I', f.read(4))[0]
        size = ((candidate & 0x007f0000) >> 2 ) | ((candidate & 0x00007f00) >> 1 ) | (candidate & 0x0000007f)
        
        f.read(size)

      # ID3 TAG -- 128 bytes long
      elif header == '\x54\x41':
        # We've already read 2 so we can go 126 forward
        f.read(126)

      else:
        print "%s:%s:%s:%s %s" % (binascii.b2a_hex(header), header, f.read(5), fname, hex(f.tell()))
        break

    else:
      break

  f.close()
  return [frame_sig, start_byte]

# serialize takes a list of ordinal tuples and makes
# one larger mp3 out of it. The tuple format is
# (fila_name, byte_start, byte_end) where byte_end == -1 
# means "the whole file" 
def serialize(file_list):
  out = open('/tmp/attempt.mp3', 'rb+')

  for name, start, end in file_list:
    f = open(name, 'rb')

    f.seek(start)
    
    if end == -1:
      out.write(f.read())
    else:
      out.write(f.read(end))

    f.close()

  out.close()

  return True

def slice_audio(fname, start, end):
  # Most common frame-length ... in practice, I haven't 
  # seen other values in the real world
  frame_length = (1152.0 / 44100)
  crc32, offset = mp3_crc(fname, skipcrc = True)

  frame_start = int(math.floor(start / frame_length))
  frame_end = int(math.ceil(end / frame_length))

  out = open('/tmp/attempt.mp3', 'wb+')
  f = open(fname, 'rb')

  f.seek(offset[frame_start])
  print offset[frame_end] - offset[frame_start], offset[frame_start]
  out.write(f.read(offset[frame_end] - offset[frame_start]))
  f.close()
  out.close()

  return True

# stitcth
def stitch_attempt(first, second):
  crc32_first, offset_first = mp3_crc(first)
  crc32_second, offset_second = mp3_crc(second, 2000)

  last = 0
  isFound = True

  try:
    pos = crc32_second.index(crc32_first[-1])

    for i in xrange(4, 0, -1):
      if crc32_second[pos - i + 1] != crc32_first[-i]:
        isFound = False
        break

  except: 
    isFound = False
    print "Failure"

  # Since we end at the last block, we can safely pass in a file1_stop of 0
  if isFound:
    # And then we take the offset in the crc32_second where things began, + 1
    serialize([(first, 0, offset_first[-1]), (second, offset_second[pos], -1)])

  return isFound

p =  mp3_crc('test.mp3')
print len(p[0])

#for f in glob.glob("*.mp3"):
#    p =  mp3_crc(f)
    #print len(p[0])

#p =  mp3_crc('/home/chris/Downloads/Avenue-Red-Podcast-041-Verdant-Recordings.mp3')
#print len(p[0])
#print mp3_crc('/tmp/attempt.mp3')

# success case
stitch_attempt('/var/radio/kpcc-1435669435.mp3', '/var/radio/kpcc-1435670339.mp3')

# failure case
#stitch_attempt('/var/radio/kpcc-1435670339.mp3', '/var/radio/kpcc-1435669435.mp3')

#slice_audio('/var/radio/kpcc-1435669435.mp3', 300, 360)
