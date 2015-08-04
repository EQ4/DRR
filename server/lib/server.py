#!/usr/bin/python -O
import misc 
import cloud
import math
import lxml.etree as ET
from flask import Response

import socket

origGetAddrInfo = socket.getaddrinfo
getAddrInfoWrapper = misc.getAddrInfoWrapper
socket.getaddrinfo = getAddrInfoWrapper

import urllib2
import urllib

def do_error(errstr):
  """ Returns a server error as a JSON result. """
  return jsonify({'result': False, 'error':errstr}), 500
    
def generate_xml(showname, feed_list, duration_min, weekday_list, start, duration_string):
  """
  It obviously returns an xml file ... I mean duh.

  In the xml file we will lie about the duration to make life easier
  """
  day_map = {
    'sun': 'Sunday',
    'mon': 'Monday',
    'tue': 'Tuesday',
    'wed': 'Wednesday',
    'thu': 'Thursday',
    'fri': 'Friday',
    'sat': 'Saturday'
  }
  
  day_list = [ day_map[weekday] for weekday in weekday_list ]
  if len(day_list) == 1:
    week_string = day_list[0]

  else:
    # an oxford comma, how cute.
    week_string = "%s and %s" % (', '.join(day_list[:-1]), day_list[-1])

  base_url = 'http://%s.indycast.net:%d/' % (misc.config['callsign'], misc.config['port'])
  callsign = misc.config['callsign']

  nsmap = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'media': 'http://search.yahoo.com/mrss/', 
    'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
    'feedburner': 'http://rssnamespace.org/feedburner/ext/1.0'
  }

  root = ET.Element("rss", nsmap=nsmap)
  root.attrib['version'] = '2.0'

  channel = ET.SubElement(root, "channel")

  for k,v in {
    '{%s}summary' % nsmap['itunes']: showname,
    '{%s}subtitle' % nsmap['itunes']: showname,
    '{%s}category' % nsmap['itunes']: 'podcast',
    'title': showname,
    'link': base_url,
    'copyright': callsign,
    'description': "%s is a %s show recorded every %s on %s at %s. Saved and delivered when you want it, through a volunteer network at http://indycast.net." % (showname, duration_string, week_string, callsign.upper(), start),
    'language': 'en'
  }.items():
    ET.SubElement(channel, k).text = v

  itunes_image = ET.SubElement(channel, '{%s}image' % nsmap['itunes'])
  itunes_image.attrib['href'] = 'http://indycast.net/icon/%s_1400.png' % urllib.quote(showname)

  media_image = ET.SubElement(channel, '{%s}thumbnail' % nsmap['media'])
  media_image.attrib['url'] = 'http://indycast.net/icon/%s_1400.png' % urllib.quote(showname)

  image = ET.SubElement(channel, 'image')
  for k,v in {
    'url': 'http://indycast.net/icon/%s_200.png' % urllib.quote(showname),
    'title': showname,
    'link': 'http://indycast.net'
  }.items():
    ET.SubElement(image, k).text = v

  for feed in feed_list:
    file_name = feed['name']
    link = "%s%s" % (base_url, file_name)

    item = ET.SubElement(channel, 'item')

    itunes_duration = "%02d:00" % (duration_min % 60)
    if duration_min > 60:
      itunes_duration = "%d:%s" % (int(math.floor(duration_min / 60 )), itunes_duration)    

    for k,v in {
      'title': "%s - %s" % (showname, feed['start_date'].strftime("%Y.%m.%d")),
      'description': "%s recorded on %s" % (showname, feed['start_date'].strftime("%Y-%m-%d %H:%M:%S")),
      '{%s}explicit' % nsmap['itunes']: 'no', 
      '{%s}author' % nsmap['itunes']: callsign,
      '{%s}duration' % nsmap['itunes']: itunes_duration,
      '{%s}summary' % nsmap['itunes']: showname,
      '{%s}creator' % nsmap['dc']: callsign.upper(),
      '{%s}origEnclosureLink' % nsmap['feedburner']: link,
      '{%s}origLink' % nsmap['feedburner']: base_url,
      'pubDate': feed['start_date'].strftime("%Y-%m-%d %H:%M:%S"),
      'link': link,
      'copyright': callsign
    }.items():
      ET.SubElement(item, k).text = v

    ET.SubElement(item, 'guid', isPermaLink="false").text = file_name

    # fileSize and length will be guessed based on 209 bytes covering
    # frame_length seconds of audio (128k/44.1k no id3)
    content = ET.SubElement(item, '{%s}content' % nsmap['media'])
    content.attrib['url'] = link
    content.attrib['fileSize'] = str(cloud.get_size(file_name))
    content.attrib['type'] = 'audio/mpeg'

    # The length of the audio we will just take as the duration
    content = ET.SubElement(item, 'enclosure')
    content.attrib['url'] = link
    content.attrib['length'] = str(cloud.get_size(file_name))
    content.attrib['type'] = 'audio/mpeg'

  tree = ET.ElementTree(root)

  return Response(ET.tostring(tree, xml_declaration=True, encoding="UTF-8"), mimetype='text/xml')
