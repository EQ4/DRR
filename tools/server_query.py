#!/usr/bin/python -O
import argparse
import os
import re
import ConfigParser
import sys
import socket
import lib.misc as misc
import json

#
# This is needed to force ipv4 on ipv6 devices. It's sometimes needed
# if there isn't a clean ipv6 route to get to the big wild internet.
# In these cases, a pure ipv6 route simply will not work.  People aren't
# always in full control of every hop ... so it's much safer to force
# ipv4 then optimistically cross our fingers.
#
origGetAddrInfo = socket.getaddrinfo
getAddrInfoWrapper = misc.getAddrInfoWrapper
socket.getaddrinfo = getAddrInfoWrapper

import urllib2
import time
import random
import lib.db as DB
from glob import glob

fail_list = []

OFF = False
ON = True

def stderr(switch):
  if switch:
    sys.stderr.close()
    sys.stderr = globals()['old']

  else:
    globals()['old'] = sys.stderr
    sys.stderr = open('/dev/null', "w")
    
def find_misbehaving_servers(db, fail_list):
  max_values = {
    'disk': '3.8',
    'load': '0.9',
    'delta': '300',
    'plist': [ 4, 6 ]
  }

  report = []

  if len(fail_list):
    report.append("Failure: %s" % ' '.join(fail_list))

  misbehaving = db['c'].execute('select callsign, disk, load, last_record from stations where active = 1 and (disk > ? or last_record > ?)', (max_values['disk'], max_values['delta'])).fetchall()

  for row in misbehaving:
    report.append("  %s: disk:%s load:%s last:%s" % row)
 
  if len(misbehaving):
    report.append("Thresholds: %s" % json.dumps(max_values, indent=2))

  if len(report) and mail_config:
    # Don't want any scripts to read this and harvest my email.
    email_to_use = 'kri%s@%soo.com' % ("stopolous", "yah")

    misc.send_email(config=mail_config, who=email_to_use, subject="server issue", body='<br>'.join(report), sender='Indycast Admin <info@indycast.net>')
    print '\n'.join(report)
    print "Issues found. Sending email to %s." % email_to_use


CALLSIGN = 'callsign'
os.chdir(os.path.dirname(os.path.realpath(__file__)))

stderr(OFF)
try:
  db = DB.connect(db_file='../db/main.db')

except:
  db = None

parser = argparse.ArgumentParser()
parser.add_argument("-q", "--query", default=None, help="query to send to the servers (site-map gives all end points)")
parser.add_argument("-s", "--station", default="all", help="station to query (default all)")
parser.add_argument('-l', '--list', action='store_true', help='show stations')
parser.add_argument('-k', '--key', default=None, help='Get a specific key in a json formatted result')
parser.add_argument('-n', '--notrandom', action='store_true', help='do not reandomize order')

mail_config = misc.mail_config(parser)
stderr(ON)

args = parser.parse_args()

if args.config and not os.path.exists(args.config) and args.station == 'all':
  args.station = args.config

config_list = []

# This permits just an inquiry like server_query -c kcrw -k version
if not args.query:
  args.query = "stats" if args.key else "heartbeat"

for station_config in glob('../server/configs/*txt'):
  Config = ConfigParser.ConfigParser()
  Config.read(station_config)
  config = misc.config_section_map('Main', Config)
  config_list.append(config)

# retrieve a list of the active stations
if args.station == 'all':
  all_stations = config_list

else:
  all_stations = []
  station_list = args.station.split(',')

  for config in config_list:
    if config['callsign'] in station_list:
      all_stations.append(config)

if args.list:
  # Just list all the supported stations
  for station in all_stations:
    print station[CALLSIGN]

  sys.exit(0)

# From https://github.com/kristopolous/DRR/issues/19:
# shuffling can allow for more robust querying if something locks up - 
# although of course a lock up should never happen. ;-)
if not args.notrandom:
  random.shuffle(all_stations)

station_count = len(all_stations)
station_ix = 0

if args.key and station_count > 1:
  print '['

for station in all_stations:
  station_ix += 1
  url = "%s.indycast.net:%s" % (station[CALLSIGN], station['port'])

  hasFailure = False

  try:
    start = time.time()

    # If we are just looking at one station, then we may want to 
    # look at this data as JSON, so we suppress any superfluous output
    if len(all_stations) > 1 and not args.key:
      # Take out the \n (we'll be putting it in below)
      sys.stderr.write("%s " % url)

    stream = urllib2.urlopen("http://%s/%s" % (url, args.query), timeout=15)
    data = stream.read()
    stop = time.time()

    if args.query == 'heartbeat':
      document = json.loads(data)
      memory = 0
      for line in document['plist']:
        numbers = re.split('\s+', line)
        memory += float(numbers[5])
      
      document['memory'] = memory
      document['delta'] = document['now'] - float(document['last_recorded'])
      data = json.dumps(document, indent=2)

    if args.key:
      document = json.loads(data)
      result_map = {}

      full_key_list = args.key.split(',')

      for full_key in full_key_list:
        # This makes it so that things like key[1].hello become key.1].hello
        key_parts = re.sub('\[', '.', full_key).strip('.').split('.')

        my_node = document
        if len(key_parts) > 1 and key_parts[0] == 'kv':
          kv_key = key_parts[1]
          for row in document['kv']:
            if row[1] == kv_key:
              my_node = row[2]
              break

        else:
          for key in key_parts:
            try:
              # This takes care of the closing brace left above
              key_numeric = int(key.strip(']'))
              
            except:
              pass

            if key in my_node:
              my_node = my_node[key]

            elif type(my_node) is list and type(key_numeric) is int and key_numeric < len(my_node):
              my_node = my_node[key_numeric]

            else:
              my_node = '<Invalid key>'

        result_map[full_key] = my_node

      result_map['url'] = url
      result_map['latency'] = stop - start

      data = json.dumps(result_map, indent=2)

      if station_ix < station_count:
        data += ','

    if len(all_stations) == 1:
      sys.stdout.write(data)
       
    else:
      if not args.key:
        sys.stderr.write("[ %d ]\n" % (stop - start))

      print data

    if db and args.query == 'heartbeat':
      db['c'].execute('''
        update stations set 
          pings = pings + 1, 
          active = 1, 
          last_seen = current_timestamp,

          disk = ?,
          last_record = ?, 
          latency = latency + ?, 
          load = ?
        where callsign = ?''', ( 
          str(document['disk']), 
          str(document['delta']), 
          str(stop - start), 
          str(document['load'][1]), 
          str(station[CALLSIGN]) 
        )
      )

  except Exception as e:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    hasFailure = str(e)

  # If this wasn't hit that means that we weren't able to access the host for
  # one reason or another.
  if hasFailure:
    # Stop the timer and register it as a drop.
    stop = time.time()
    print "[ %d:%s ] Failure(@%d): %s\n" % (stop - start, url, exc_traceback.tb_lineno, hasFailure)
    fail_list.append(url.split('.')[0])

    if db:
      db['c'].execute('update stations set drops = drops + 1 where callsign = "%s"' % station[CALLSIGN] )

if args.query == 'heartbeat' and db:
  db['conn'].commit()
  find_misbehaving_servers(db, fail_list)

if args.key and station_count > 1:
  sys.stdout.write(']')

elif len(fail_list):
  os.popen('./restart_through_ssh.sh %s' % ' '.join(fail_list))
  print "Failure", fail_list
