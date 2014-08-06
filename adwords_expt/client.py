#! /usr/bin/env python
# -*- coding: utf-8 -*-

###############################################################################
### FILENAME :
### AUTHOR   :
### CREATED  :
### PROJECT  :
### USED ON  :
### MODIFIED :
### REQUIRES :
### TODOs    :
###############################################################################
### IMPORTS
import os
import sys
import logging, logging.handlers
import cPickle
import ConfigParser
import subprocess
import json
import uuid
from multiprocessing import Process, Queue
from threading import Timer
#import argparse
sys.path.insert(0, 'lib')
from urllib2 import Request, urlopen
from collections import defaultdict
from time import sleep
from ad_grabber_logging import *
from ad_grabber_network import *
from ad_grabber_googleapm import *
from ad_grabber_bluekaiapm import parse_bluekai_apm
from bs4 import BeautifulSoup as bs
###############################################################################
# Configuration Parameters
# config manager
CONFIG = ConfigParser.ConfigParser()
CONFIG.optionxform = str
CONFIG.readfp(open('baseconfig.cfg'))
MACHINEID = CONFIG.get('machineinfo', 'MACHINEID')
SERVER = CONFIG.get('serverinfo', 'SERVER')
ERROR_SERVER = CONFIG.get('serverinfo', 'ERROR_SERVER')
NUMADGRABBERS = CONFIG.getint('clientinfo', 'NUMADGRABBERS')
HEARTBEAT_INTERVAL = CONFIG.getint('clientinfo', 'HEARTBEATINT')
HEADLESS = CONFIG.getboolean('machineinfo', 'XVFBENABLED')
ADSFOLDER = CONFIG.get('outputfolder', 'ADSFOLDER') 
OURADSFOLDER = CONFIG.get('adwords', 'OURADSFOLDER')
COMM = None # adgrabber networking object for communicating with adserver

BASEPORTVAL = 5000
TIMEOUTVAL = 1200
# checking if critical config params are set !
LOG = init_logger("logAdGrabber", error_server=ERROR_SERVER,
                  loglevel="INFO", machineID=MACHINEID)
###############################################################################
def get_diskusage(path):
  """ Hacky way of getting disk usage and returning du as %
  """
  st = os.statvfs(path)
  free = st.f_bavail * st.f_frsize
  total = st.f_blocks * st.f_frsize
  used = (st.f_blocks - st.f_bfree) * st.f_frsize
  return float(used)/total

def clean_tmpdirs():
  import re, shutil
  for f in os.listdir('/tmp'):
    if f.startswith('tmp'):
      shutil.rmtree(os.path.join('/tmp', f))

def timeout(p, id):
  if p.poll() == None:
    try:
      p.kill()
      LOG.info("Worker: %d. Process takes too long to complete. Timing-out and\
          kill" % id) 
    except :
      pass

def spawn_workers(worker_id, input_queue, comm):
  LOG.info("IN spawn worker process")
  # Workers will use img_<worker_id>.txt file as flag for task completion
  worker_result = 'phantomDir/img_%d.txt' % worker_id 
#  try:
  while True:
    job = input_queue.get()
    payload = { 'JOB_NAME' : job['JOB_NAME'],
                'TIMING' : None }
    start_time = datetime.datetime.now()
    if len(job['TEST_SITES']) > 1 :
        LOG.error('TEST_SITES shouldnot have more than 1 URL for this expt..')
        raise Exception
    url = job['TEST_SITES'][0]
    if not url.startswith('http://'):
      url = 'http://%s' % url
      LOG.info("Worker:%d. Fetching url %s and reloading for %d" % (worker_id,
                url, job['REFRESH_NUM']))
      with open(os.devnull, 'w') as fnull:
#            debugging casperjs, uncomment out the following 2 lines
        proc=subprocess.Popen(["casperjs", "--web-security=no",
            "casper_adgrabber_img.js", url, str(worker_id),
            str(job['REFRESH_NUM'])])
#            proc=subprocess.Popen(["casperjs", "casp_fetch_site.js", url,
#                str(worker_id)], stdout=fnull, stderr=fnull)
      try :   
        t = Timer(TIMEOUTVAL, timeout, [proc, worker_id])
        t.start()
      except Exception:
        payload['TIMEOUT'] = True
      proc.communicate()
    end_time = datetime.datetime.now()
    payload['TIMING'] = str(end_time - start_time)
    payload['DATE'] = str(end_time)
    payload['REFRESH_NUM'] = job['REFRESH_NUM']
    payload['TEST_SITES'] = job['TEST_SITES'][0]
    payload['IS_AD_SEEN'] = parse_casperjs_results(worker_result)
    sent = comm.send_request(payload, 'results')
    if not sent :
      LOG.error("UNSENT!")
 # except Exception as e:
 #   LOG.error(e) 
 #   raise Exception("%s" % e)

def parse_casperjs_results(worker_result_file):
  """ 
  Parses the json formatted output of casperjs. The data structure is lists
  within a list, where the inner lists is all the image URL seen in a reload
  """
  is_ad_seen = defaultdict(list) 
  with open(worker_result_file, 'r') as frdr:
    results = json.load(frdr)
  for visit_num, ad_url_list in enumerate(results):
    for ad_url in ad_url_list:
      if ad_url.startswith('http://pagead2.googlesyndication.com'):
        dl_path = ad_downloader(ad_url)
        if not dl_path :
          # not an ad based on our filter
          continue
        check = check_if_our_ad(dl_path)
        if check :
          is_ad_seen[visit_num].append(check_if_our_ad(dl_path))
  return is_ad_seen
        

def check_if_our_ad(dl_path):
  for our_ad in os.listdir(OURADSFOLDER):
    fpath = os.path.join(OURADSFOLDER, our_ad)
    try :
      subprocess.check_output(['diff', fpath, dl_path])
      return our_ad
    except subprocess.CalledProcessError:
      pass
  return None 


def ad_downloader(ad_url):
  sanitized_ad_url = ad_url.replace('/','')
  if filter_obvious_non_ads(sanitized_ad_url):
    return False
  dl_path = os.path.join(ADSFOLDER, sanitized_ad_url)
  subprocess.call(['wget', '-t', '1', '-q', '-T', '3',
      '-O', dl_path , ad_url])
  return dl_path
  

def filter_obvious_non_ads(ad_url):
  """returns True if ad_url is in filter list, meaning it is not an ad and
  should be filtered"""
  filter = [
   'http:pagead2.googlesyndication.compageadimagesgoogle-logo.png',
   'http:pagead2.googlesyndication.compageadimagesgreen-check.png',
   'http:pagead2.googlesyndication.compageadimagesnessie_icon_thin_chevron_white.png', 
   'http:pagead2.googlesyndication.compageadimagesnessie_icon_chevron_white.png',
   'http:pagead2.googlesyndication.compageadimagesnessie_icon_externallink_black.png',
   'http:pagead2.googlesyndication.compageadimagesx_button.png',
   'http:pagead2.googlesyndication.compageadimagesx_button_dark.png']
  if ad_url in filter:
    return True
  else :
    return False

def main():
  # Join hub.py 
  try:
    COMM = Communicator(MACHINEID, SERVER, "logAdGrabber")
    LOG.info('Joining hub as %s' % MACHINEID) 
    response = COMM.send_request({}, 'join')
  except Exception as e:
    LOG.error(e)
    return

  LOG.debug('Init data structs')
  pr = {}
  input_queue = Queue(maxsize=NUMADGRABBERS)

  # clean up adsFolder
  for f in os.listdir(ADSFOLDER):
    os.unlink(os.path.join(ADSFOLDER, f))

  for i in range(NUMADGRABBERS):
    if os.path.exists('%d.txt' % i):
      os.unlink('%d.txt' % i)
    LOG.info("Creating phantomjs process %d" % i)
    pr[i] = Process(target=spawn_workers, args=(i, input_queue, COMM))
    pr[i].start()
  
  while True :
    LOG.info('Telling hub I have %d idle slots' % (NUMADGRABBERS -
        input_queue.qsize()))
    job = COMM.send_request({}, 'idle')
    if not job:
      LOG.info("No jobs received") 
      sleep(5)
      continue
    else:
      input_queue.put(job)
  
def check_params_set():
  """ Makes sure that key parameters are set in the baseconfig file before
  proceeding.
  """
  critical = {'machineinfo' : MACHINEID, 
              'error_serverinfo' : ERROR_SERVER, 
              'serverinfo' : SERVER}
  for i, val in critical.iteritems():
    if not val:
      print "ERROR: Set value for \"%s\" in baseconfig.cfg file first\n" % i
      sys.exit(1)

if __name__ == "__main__":
  try:
    check_params_set()
    main()
  except KeyboardInterrupt:
    LOG.info('exiting...')
