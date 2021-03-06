#!/usr/bin/python 
#import objgraph
import argparse, logging, os, pycurl, re
import re, signal, sys, time
import setproctitle as SP

import lib.db as DB
import lib.server as server
import lib.audio as audio
import lib.ts as TS
import lib.misc as misc
import lib.cloud as cloud

from logging.handlers import RotatingFileHandler
from datetime import timedelta, date
from glob import glob
from subprocess import Popen
from multiprocessing import Process, Queue

g_download_pid = 0

def stream_download(callsign, url, my_pid, file_name):
  # Curl interfacing which downloads the stream to disk. 
  # Follows redirects and parses out basic m3u.
  pid = misc.change_proc_name("%s-download" % callsign)

  nl = {'stream': None, 'curl_handle': None}

  def dl_stop(signal, frame):
    sys.exit(0)

  def cback(data): 

    if not misc.params['shutdown_time']:
      if not misc.download_ipc.empty():
        what, value = misc.download_ipc.get(False)
        if what == 'shutdown_time':
          misc.params['shutdown_time'] = value

    elif TS.unixtime('dl') > misc.params['shutdown_time']:
      sys.exit(0)

    if misc.params['isFirst'] == True:
      misc.params['isFirst'] = False

      if len(data) < 800:
        if re.match('https?://', data):
          # If we are getting a redirect then we don't mind, we
          # just put it in the stream and then we leave
          misc.queue.put(('stream', data.strip()))
          return True

        # A pls style playlist
        elif re.findall('File\d', data, re.M):
          logging.info('Found a pls, using the File1 parameter')
          matches = re.findall('File1=(.*)\n', data, re.M)
          misc.queue.put(('stream', matches[0].strip()))
          return True

    # This provides a reliable way to determine bitrate.  We look at how much 
    # data we've received between two time periods
    misc.queue.put(('heartbeat', (TS.unixtime('hb'), len(data))))

    if not nl['stream']:
      try:
        nl['stream'] = open(file_name, 'w')

      except Exception as exc:
        logging.critical("Unable to open %s. Can't record. Must exit." % file_name)
        sys.exit(-1)

    nl['stream'].write(data)

    if not misc.manager_is_running():
      misc.shutdown()

  # signal.signal(signal.SIGTERM, dl_stop)
  misc.params['isFirst'] = True
  curl_handle = pycurl.Curl()
  curl_handle.setopt(curl_handle.URL, url)
  curl_handle.setopt(pycurl.WRITEFUNCTION, cback)
  curl_handle.setopt(pycurl.FOLLOWLOCATION, True)
  nl['curl_handle'] = curl_handle

  try:
    curl_handle.perform()

  except TypeError as exc:
    logging.info('Properly shutting down.')

  except Exception as exc:
    logging.warning("Couldn't resolve or connect to %s." % url)

  curl_handle.close()

  if nl['stream'] and type(nl['stream']) != bool:
    nl['stream'].close()
    # This is where we are sure of the stats on this file, because
    # we just closed it ... so we can register it here.
    info = audio.stream_info(file_name)

    DB.register_stream(info)


def my_process_shutdown(process):
  # A small function to simplify the logic below. 
  if process and process.is_alive():
    logging.info("[%s:%d] Shutting down" % ('download', process.pid))
    process.terminate()

  return None


def stream_manager():
  import random

  # Manager process which makes sure that the
  # streams are running appropriately.
  callsign = misc.config['callsign']

  #
  # AAC bitrate is some non-trivial thing that even ffprobe doesn't
  # do a great job at. This solution looks at number of bits that
  # transit over the wire given a duration of time, and then uses
  # that to compute the bitrate, since in practice, that's what
  # bitrate effectively means, and why it's such an important metric.
  #
  # This is to compute a format agnostic bitrate
  # (see heartbeat for more information)
  #
  has_bitrate = DB.get('bitrate') 
  first_time = 0
  total_bytes = 0
  normalize_delay = 6

  cascade_time = misc.config['cascadetime']
  cascade_buffer = misc.config['cascadebuffer']
  cascade_margin = cascade_time - cascade_buffer

  last_prune = 0
  last_success = 0

  change_state = None
  SHUTDOWN = 1
  RESTART = 2
  shutdown_time = None
  misc.download_ipc = Queue()

  # Number of seconds to be cycling
  cycle_time = misc.config['cycletime']

  process = None
  process_next = None

  # The manager will be the one that starts this.
  misc.pid_map['webserver'] = Process(target=server.manager, args=(misc.config,))
  misc.pid_map['webserver'].start()

  file_name = None

  # A wrapper function to start a donwnload process
  def download_start(file_name):
    """ Starts a process that manages the downloading of a stream. """
    global g_download_pid

    g_download_pid += 1
    logging.info('Starting cascaded downloader #%d. Next up in %ds' % (g_download_pid, cascade_margin))

    #
    # There may be a multi-second lapse time from the naming of the file to
    # the actual start of the download so we should err on that side by putting it
    # in the future by some margin
    #
    file_name = '%s/%s-%s.mp3' % (misc.DIR_STREAMS, callsign, TS.ts_to_name(TS.now(offset_sec=misc.PROCESS_DELAY / 2)))
    process = Process(target=stream_download, args=(callsign, misc.config['stream'], g_download_pid, file_name))
    process.start()
    return [file_name, process]


  # see https://github.com/kristopolous/DRR/issues/91:
  # Randomize prune to offload disk peaks
  prune_duration = misc.config['pruneevery'] + (1 / 8.0 - random.random() / 4.0)

  while True:
    #
    # We cycle this to off for every run. By the time we go throug the queue so long 
    # as we aren't supposed to be shutting down, this should be toggled to true.
    #
    flag = False

    if last_prune < (TS.unixtime('prune') - TS.ONE_DAY_SECOND * prune_duration):
      prune_duration = misc.config['pruneevery'] + (1 / 8.0 - random.random() / 4.0)
      # We just assume it can do its business in under a day
      misc.pid_map['prune'] = cloud.prune()
      last_prune = TS.unixtime('prune')

    TS.get_offset()

    lr_set = False
    while not misc.queue.empty():
      flag = True
      what, value = misc.queue.get(False)

      # The curl proces discovered a new stream to be
      # used instead.
      if what == 'stream':
        misc.config['stream'] = value
        logging.info("Using %s as the stream now" % value)
        # We now don't toggle to flag in order to shutdown the
        # old process and start a new one

      elif what == 'db-debug':
        DB.debug()

      elif what == 'shutdown':
        change_state = SHUTDOWN

      elif what == 'restart':
        logging.info(DB.get('runcount', use_cache=False))
        cwd = os.getcwd()
        os.chdir(misc.PROCESS_PATH)
        Popen(sys.argv)
        os.chdir(cwd)

        change_state = RESTART

        # Try to record for another restart_overlap seconds - make sure that
        # we don't perpetually put this in the future due to some bug.
        if not shutdown_time:
          shutdown_time = TS.unixtime('dl') + misc.config['restart_overlap']
          logging.info("Restart requested ... shutting down downloader at %s" % TS.ts_to_name(shutdown_time, with_seconds=True))

          while True:
            time.sleep(20)
            #logging.info(DB.get('runcount', use_cache=False))
            logging.info(('ps axf | grep [%c]%s | grep python | wc -l' % (misc.config['callsign'][0], misc.config['callsign'][1:]) ).read().strip())
            ps_out = int(os.popen('ps axf | grep [%c]%s | grep python | wc -l' % (misc.config['callsign'][0], misc.config['callsign'][1:]) ).read().strip())

            if ps_out > 1: 
              logging.info("Found %d potential candidates (need at least 2)" % ps_out)
              # This makes it a restricted soft shutdown
              misc.shutdown_real(do_restart=True)
              misc.download_ipc.put(('shutdown_time', shutdown_time))
              break

            else:
              Popen(sys.argv)
              logging.warn("Couldn't find a replacement process ... not going anywhere.");

      elif what == 'heartbeat':
        if not lr_set and value[1] > 100:
          lr_set = True
          DB.set('last_recorded', time.time())

        if not has_bitrate: 

          # Keep track of the first time this stream started (this is where our total
          # byte count is derived from)
          if not first_time: 
            first_time = value[0]

          #
          # Otherwise we give a large (in computer time) margin of time to confidently
          # guess the bitrate.  I didn't do great at stats in college, but in my experiments,
          # the estimation falls within 98% of the destination.  I'm pretty sure it's really
          # unlikely this will come out erroneous, but I really can't do the math, it's probably
          # a T value, but I don't know. Anyway, whatevs.
          #
          # The normalize_delay here is for both he-aac+ streams which need to put in some frames
          # before the quantizing pushes itself up and for other stations which sometimes put a canned
          # message at the beginning of the stream, like "Live streaming supported by ..."
          #
          # Whe we discount the first half-dozen seconds as not being part of the total, we get a 
          # stabilizing convergence far quicker.
          #
          elif (value[0] - first_time > normalize_delay):
            # If we haven't determined this stream's bitrate (which we use to estimate 
            # the amount of content is in a given archived stream), then we compute it 
            # here instead of asking the parameters of a given block and then presuming.
            total_bytes += value[1]

            # We still give it a time period after the normalizing delay in order to build enough
            # samples to make a solid guess at what this number should be.
            if (value[0] - first_time > (normalize_delay + 60)):
              # We take the total bytes, calculate it over our time, in this case, 25 seconds.
              est = total_bytes / (value[0] - first_time - normalize_delay)

              # We find the nearest 8Kb increment this matches and then scale out.
              # Then we multiply out by 8 (for _K_ B) and 8 again for K _b_.
              bitrate = int( round (est / 1000) * 8 )
              DB.set('bitrate', bitrate)

    # Check for our management process
    if not misc.manager_is_running():
      logging.info("Manager isn't running");
      change_state = SHUTDOWN

    # The only way for the bool to be toggled off is if we are not in full-mode ... 
    # we get here if we should NOT be recording.  So we make sure we aren't.
    if change_state == SHUTDOWN or (change_state == RESTART and TS.unixtime('dl') > shutdown_time):
      process = my_process_shutdown(process)
      process_next = my_process_shutdown(process_next)
      misc.shutdown_real()

    else:
      # Didn't respond in cycle_time seconds so kill it
      if not flag:
        process = my_process_shutdown(process)

      if not process and not change_state:
        file_name, process = download_start(file_name)
        last_success = TS.unixtime('dl')

      # If we've hit the time when we ought to cascade
      elif TS.unixtime('dl') - last_success > cascade_margin:

        # And we haven't created the next process yet, then we start it now.
        if not process_next:
          file_name, process_next = download_start(file_name)

      # If our last_success stream was more than cascade_time - cascade_buffer
      # then we start our process_next
      
      # If there is still no process then we should definitely bail.
      if not process:
        misc.shutdown_real()

    #
    # This needs to be on the outside loop in case we are doing a cascade
    # outside of a full mode. In this case, we will need to shut things down
    #
    # If we are past the cascade_time and we have a process_next, then
    # we should shutdown our previous process and move the pointers around.
    #
    if not change_state and TS.unixtime('dl') - last_success > cascade_time and process:
      logging.info("Stopping cascaded downloader")
      process.terminate()

      # If the process_next is running then we move our last_success forward to the present
      last_success = TS.unixtime('dl')

      # we rename our process_next AS OUR process
      process = process_next

      # and then clear out the old process_next pointer
      process_next = None

    # Increment the amount of time this has been running
    DB.incr('uptime', cycle_time)

    time.sleep(cycle_time)

def read_config(config):
  import ConfigParser
  # Reads a configuration file. 
  # Currently documented at https://github.com/kristopolous/DRR/wiki/Join-the-Federation
  Config = ConfigParser.ConfigParser()
  Config.read(config)
  misc.config = misc.config_section_map('Main', Config)
  misc.PROCESS_PATH = os.path.dirname(os.path.realpath(__file__))
  
  defaults = {
    # The log level to be put into the indycast.log file.
    'loglevel': 'DEBUG',

    #
    # The relative, or absolute directory to put things in
    # The default goes into the home directory to try to avoid a situation
    # where we can't read or write something on default startup - also we keep
    # it out of a dot directory intentionally so that we don't fill up a home
    # directory in some hidden path - that's really dumb.
    #
    'storage': "%s/radio" % os.path.expanduser('~'),

    # The (day) time to expire an intent to record
    'expireafter': 45,

    # The time to prolong a download to make sure that 
    # a restart or upgrade is seamless, in seconds.
    'restart_overlap': 15,

    # The TCP port to run the server on
    'port': 5000,

    # The (day) duration we should be archiving things.
    'archivedays': 28,

    # The (second) time in looking to see if our stream is running
    'cycletime': 7,

    # The (second) time to start a stream BEFORE the lapse of the cascade-time
    'cascadebuffer': 15,

    # The (second) time between cascaded streams
    'cascadetime': 60 * 15,

    # Cloud credentials (ec2, azure etc)
    'cloud': None,

    #
    # When to get things off local disk and store to the cloud
    # This means that after this many days data is sent remote and then 
    # retained for `archivedays`.  This makes the entire user-experience
    # a bit slower of course, and has an incurred throughput cost - but
    # it does save price VPS disk space which seems to come at an unusual
    # premium.
    #
    'cloudarchive': 1.20,
    
    # Run the pruning every this many days (float)
    'pruneevery': 0.5
  }

  for k, v in defaults.items():
    if k not in misc.config:
      misc.config[k] = v
    else:
      if type(v) is int: misc.config[k] = int(misc.config[k])
      elif type(v) is long: misc.config[k] = long(misc.config[k])
      elif type(v) is float: misc.config[k] = float(misc.config[k])

  # In case someone is specifying ~/radio 
  misc.config['storage'] = os.path.expanduser(misc.config['storage'])
  misc.config['_private'] = {}

  if misc.config['cloud']:
    misc.config['cloud'] = os.path.expanduser(misc.config['cloud'])

    if os.path.exists(misc.config['cloud']):
      # If there's a cloud conifiguration file then we read that too
      cloud_config = ConfigParser.ConfigParser()
      cloud_config.read(misc.config['cloud'])

      # Things stored in the _private directory don't get reported back in a status
      # query.
      #
      # see https://github.com/kristopolous/DRR/issues/73 for what this is about.
      misc.config['_private']['azure'] = misc.config_section_map('Azure', cloud_config)

  if not os.path.isdir(misc.config['storage']):
    try:
      # If I can't do this, that's fine.
      os.mkdir(misc.config['storage'])

    except Exception as exc:
      # We make it from the current directory
      misc.config['storage'] = defaults['storage']

      if not os.path.isdir(misc.config['storage']):
        os.mkdir(misc.config['storage'])

  # Go to the callsign level in order to store multiple station feeds on a single
  # server in a single parent directory without forcing the user to decide what goes
  # where.
  misc.config['storage'] += '/%s/' % misc.config['callsign']
  misc.config['storage'] = re.sub('\/+', '/', misc.config['storage'])

  if not os.path.isdir(misc.config['storage']):
    os.mkdir(misc.config['storage'])

  # We have a few sub directories for storing things
  for subdir in [misc.DIR_STREAMS, misc.DIR_SLICES, misc.DIR_BACKUPS]:
    if not os.path.isdir(misc.config['storage'] + subdir):
      os.mkdir(misc.config['storage'] + subdir)

  # Now we try to do all this stuff again
  if os.path.isdir(misc.config['storage']):
    #
    # There's a bug after we chdir, where the multiprocessing is trying to grab the same 
    # invocation as the initial argv[0] ... so we need to make sure that if a user did 
    # ./blah this will be maintained.
    #
    if not os.path.isfile(misc.config['storage'] + __file__):
      os.symlink(os.path.abspath(__file__), misc.config['storage'] + __file__)

    os.chdir(misc.config['storage'])

  else:
    logging.warning("Can't find %s. Using current directory." % misc.config['storage'])

  misc.PIDFILE_MANAGER = '%s/%s' % (os.getcwd(), 'pid-manager')
  # If there is an existing pid-manager, that means that 
  # there is probably another version running.
  if os.path.isfile(misc.PIDFILE_MANAGER):
    with open(misc.PIDFILE_MANAGER, 'r') as f:
      oldserver = f.readline()

      try:  
        logging.info("Replacing our old image")
        os.kill(int(oldserver), signal.SIGUSR1)
        # We give it a few seconds to shut everything down
        # before trying to proceed
        time.sleep(misc.PROCESS_DELAY / 2)

      except:
        pass
   
  # From https://docs.python.org/2/howto/logging.html
  numeric_level = getattr(logging, misc.config['loglevel'].upper(), None)
  if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

  logger = logging.getLogger()
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y%m%d_%H%M_%S')
  handler = RotatingFileHandler('indycast.log', maxBytes=2000000, backupCount=5)
  handler.setFormatter(formatter)
  handler.setLevel(numeric_level)
  logger.setLevel(numeric_level)
  logger.addHandler(handler)

  # Increment the number of times this has been run so we can track the stability of remote 
  # servers and instances.
  DB.upgrade()
  del(DB.upgrade)
  DB.incr('runcount')

  # This is how we discover if we are the official server or not.
  # Look at the /uuid endpoint to see how this magic works.
  misc.config['uuid'] = os.popen('uuidgen').read().strip()

  signal.signal(signal.SIGINT, misc.shutdown_handler)
  signal.signal(signal.SIGUSR1, misc.shutdown_handler)
  signal.signal(signal.SIGHUP, misc.do_nothing)


if __name__ == "__main__":
  # From http://stackoverflow.com/questions/25504149/why-does-running-the-flask-dev-server-run-itself-twice

  if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    server_manager(misc.config)

  else: 
    # Ignore all test scaffolding
    misc.IS_TEST = False
    misc.start_time = TS.unixtime()

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", default="./indy_config.txt", help="Configuration file (default ./indy_config.txt)")
    parser.add_argument('--version', action='version', version='indycast %s :: Aug 2015' % misc.__version__)
    parser.add_argument("--daemon", action='store_true',  help="run as daemon")
    args = parser.parse_args()
    if args.daemon:
      Popen( filter(lambda x: x != '--daemon', sys.argv) )
      sys.exit(0)

    read_config(args.config)      
    del(read_config)

    pid = misc.change_proc_name("%s-manager" % misc.config['callsign'])

    # This is the pid that should be killed to shut the system
    # down.
    misc.manager_is_running(pid)
    with open(misc.PIDFILE_MANAGER, 'w+') as f:
      f.write(str(pid))

    stream_manager()
