#!/usr/bin/python

from glob import glob
import math
import os

# using http://wiki.multimedia.cx/index.php?title=ADTS
def aac_decode(fname):
  f = open(fname, 'rb')

  while True:
    if ord(f.read(1)) == 0xff:
      if ord(f.read(1)) & 0xf6 == 0xf0:
        f.seek(f.tell() - 2)
        break
    
  isValid = False
  frame_number = 0
  header_size = 6
  while True:

    block = f.read(header_size)

    if not block or len(block) < header_size:
        f.close()
        return frame_number

    b0, b1, b2, b3, b4, b5 = [ord(byte) for byte in block[:header_size]]

    # b0       b1       b2       b3       b4       b5       b6
    # AAAAAAAA AAAABCCD EEFFFFGH HHIJKLMM MMMMMMMM MMMOOOOO OOOOOOPP 
    # 84218421 84218421 84218421 84218421 84218421 84218421 84218421
    #                                                       IGNORED
    #
    # A     12  syncword 0xFFF, all bits must be 1 
    # B     1   MPEG Version: 0 for MPEG-4, 1 for MPEG-2
    # C     2   Layer: always 0
    # D     1   protection absent, Warning, set to 1 if there is no CRC and 0 if there is CRC
    # E     2   profile, the MPEG-4 Audio Object Type minus 1 
    # F     4   MPEG-4 Sampling Frequency Index (15 is forbidden) 
    # G     1   private bit, guaranteed never to be used by MPEG, set to 0 when encoding, ignore when decoding
    # H     3   MPEG-4 Channel Configuration (in the case of 0, the channel configuration is sent via an inband PCE) 
    # I     1   originality, set to 0 when encoding, ignore when decoding
    # J     1   home, set to 0 when encoding, ignore when decoding
    # K     1   copyrighted id bit, the next bit of a centrally registered copyright identifier, set to 0 when encoding, ignore when decoding
    # L     1   copyright id start, signals that this frame's copyright id bit is the first bit of the copyright id, 
    #           set to 0 when encoding, ignore when decoding
    # M     13  frame length, this value must include 7 or 9 bytes of header length: 
    #           FrameLength = (ProtectionAbsent == 1 ? 7 : 9) + size(AACFrame)
    # O     11  Buffer fullness
    # P     2   Number of AAC frames (RDBs) in ADTS frame minus 1, for maximum compatibility always use 1 AAC frame per ADTS frame
    # Q     16  CRC if protection absent is 0 
    

    # A and C (yes this is 0xf SIX and 0xf ZERO)
    if b0 != 0xff or (b1 & 0xf6 != 0xf0): 
      print "Broken at frame#%d" % frame_number
      break

    #
    # For all intents and purposes this doesn't seem to be a real
    # heavy indicator for our calculations ... since in practice 
    # the radio streams will be all stereo.
    #
    # freq = b2 >> 2 & 0xf
    # channels = (b2 & 1) << 2 | b3 >> 6
    protect_absent = b1 & 1
    frame_length = (b3 & 3) << 11 | b4 << 3 | b5 >> 5
    # frame_count = (b6 & 3) + 1

    frame_number += 1 
    f.read(frame_length - header_size)

  print frame_number
  return None

packed_data = '\xff\xf9\x5c\x40\x15\x21\x30'

for fname in glob('wzrd*mp3'):
    frame_count = aac_decode(fname)
    frame_length_estimate = 2048.00 / 44100
    size = os.path.getsize(fname)
    est = size / 4000.0 #frame_count * frame_length_estimate

    print "%d:%f" % (int(math.floor(est / 60)), est % 60), size / 4000, frame_count, fname, size

