"""
ad_grabber_webdriver 
Functionality : TODO write this up 
"""
from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from shutil import copy2, move
from time import sleep
from Queue import Empty
from multiprocessing import Process, Queue
from threading import Thread

import subprocess
import selenium.webdriver.support.ui as ui
import selenium.common.exceptions
import logging
import cPickle
import os
import urllib2
import shutil, re

LOG = logging.getLogger("logAdGrabber")

class WebdriverException(Exception):
  def __init__(self, value):
    self.msg = value
  def __str__(self):
    return repr(self.msg)

def preserve_cookies(profile_path):
  """
  Preserves DAA, NAI opt out cookies by replacing the cookie.sqlite file
  with a archived version.
  """
  cookie_path = os.path.join(profile_path, 'cookies.sqlite')
  saved_cookie = os.path.join(profile_path, 'cookies_saved.bak')
  if os.path.exists(saved_cookie):
    LOG.debug('Preserving cookies!\n')
    copy2(saved_cookie, cookie_path)
  else :
    LOG.info('No cookies_saved.bak file found. Cannot preserve cookies.')

def browser_cleanup(profile_path):
  """
  DEPRECATED !
  Function cleans up the cookies, cache? of the Firefox browser
  Input : profile_path - absolute location where the profile is stored for
  firefox
  """
  cookie_path = os.path.join(profile_path, 'cookies.sqlite')
  cookie_path_bak = os.path.join(profile_path, 'cookies.sqlite.bak')
  if os.path.exists(cookie_path):
    LOG.debug('Cleaning up Cookies\n')
    # backup old cookies
    copy2(cookie_path, cookie_path_bak) 
    # TODO is this sufficient enough ?
    os.remove(cookie_path)


# Selenium Master
def run_master(profile_path, bin_path, port=5000, to_val=8):
  """
  Spawns up a Firefox browser instance, with the specified FirefoxProfile
  optional params port and to_val will be passed to the FF addon in a get
  parameter. 
  
  Returns a handle to firefox webdriver if success
  """
  try:
    fp = webdriver.FirefoxProfile(profile_path)
  #  fp.set_preference("webdriver.log.file", log_path)
    fp.set_preference("adfinder.port", port)
    fp.set_preference("adfinder.timeout", to_val)
    ffbin = webdriver.firefox.firefox_binary.FirefoxBinary(bin_path)
    wd = webdriver.Firefox(firefox_profile=fp)
  except (urllib2.HTTPError, urllib2.URLError) as e:
    raise WebdriverException(e)
  return wd

def enqueueon(port):
  try:
    req = urllib2.Request(url='http://127.0.0.1:%d/enqueueon' % port)
    urllib2.urlopen(req)
  except (urllib2.HTTPError, urllib2.URLError) as e:
    raise WebdriverException(e)
  
def enqueueoff(port):
  try:
    req = urllib2.Request(url='http://127.0.0.1:%d/enqueueoff' % port)
    urllib2.urlopen(req)
  except (urllib2.HTTPError, urllib2.URLError) as e:
    raise WebdriverException(e)

def shutdown_flask(port):
  try:
    req = urllib2.Request(url='http://127.0.0.1:%d/shutdown' % port)
    urllib2.urlopen(req)
    LOG.debug('shutting down flask now...')
  except (urllib2.HTTPError, urllib2.URLError) as e:
    raise WebdriverException(e)

def fetch_website(wd, url, implicit_to=10, explicit_to=15, scroll=False):
  """
  Loads a website specified by a url

  url : url of website
  timeout, implicit timeout passed to selenium webdriver
  return Bool : True if fetch operation completed without error. 
  """
  res_queue = Queue()
  fproc = Process(target=fetch_website_process, args=(wd, url, res_queue,10))
  fproc.start()
  fproc.join(timeout=explicit_to)
  if fproc.is_alive():
    LOG.error('fetch_webdriver: for %s didnt quit' % url)
  fproc.terminate()

  try:
    status = res_queue.get(block=False)
  except Empty:
    status = False
  return status

def fetch_website_process(wd, url, res_queue, implicit_to=15, scroll=False):
  try:
    success = False
    wd.set_page_load_timeout(implicit_to)
    LOG.debug('Fetching website :' + str(url))
    wd.execute_script('window.onbeforeunload = function() {}')
    wd.execute_script('window.ShowModalDialog = function() {}')
    wd.execute_script('window.alert = function() {}')
    wd.execute_script('window.confirm = function() {}')
    wd.execute_script('window.prompt = function() {}')
    wd.execute_script('window.open = function() {}')
    wd.execute_script('window.openDialog = function() {}')
    if not url.startswith('http://'):
      wd.get('http://' + url)
    else :
      wd.get(url)
    if scroll:
      for i in range(30):
        wd.execute_script('window.scrollBy(0,200);')
        sleep(0.01)
    success = True
  except TimeoutException:
    LOG.info('Page Load time out for %s. We return success for now' % url)
    success = True
  except (urllib2.HTTPError, urllib2.URLError):
    LOG.error('HTTPError or URLError') 
  except Exception as e:
    LOG.error(e)
  res_queue.put(success)

def clean_plugtmp_dirs():
  for f in os.listdir('/tmp'):
    if re.search('plugtmp*', f) and not os.listdir(os.path.join('/tmp', f)):
      shutil.rmtree(os.path.join('/tmp', f), True)

def close_webdriver(wd, error=False):
  if not error:
    LOG.info('Closing webdriver: success')
  else:
    LOG.error('Closing webdriver: failure')
  fproc = Process(target=close_webdriver_process, args=(wd,))
  fproc.start()
  fproc.join(timeout=2)
  if fproc.is_alive():
    LOG.error('Wedriver didnt shutdown. Terminating. Profile=%s' %
              wd.firefox_profile.tempfolder)
  fproc.terminate()
  shutil.rmtree(wd.firefox_profile.tempfolder, True)
  clean_plugtmp_dirs()

def close_webdriver_process(wd):
  try:
    wd.quit()
  except Exception as e:
    LOG.error(e)

def stop_loading(wd):
  """
  Uses window.stop to stop the browser's main page from loading 
  """
  try:
    script = 'window.stop();'
    wd.execute_script(script)
  except Exception as e:
    LOG.error(e)
  return

def initialize_session(vmid, now):
  """
  Get a session name, Set up the session directory. 
  """
  return '%s_%s%s%s_%s-%s' % (
      vmid, now.year, now.month, now.day, now.hour, now.minute)


def load_testing_sites(test_sites):
  """
  Input : Text file containing 
  URL : category
  """
  count = 0
  testing_sites = []
  with open(test_sites, 'r') as frdr:
    for line in frdr:
      line = line.strip()
      if line.startswith('#') or line == '':
        continue
      
      tokens = line.split('#')
      site = tokens[0].strip()
      category = None
      if len(tokens) > 1:
        category = tokens[1].strip()
      count += 1
      testing_sites.append((count, site, category))
  return testing_sites

def load_alexa_sites(limit=None):
  """
  prereq : top-1m site file in INPUT
  TODO: ADD a range of sites to extract
  @param limit : limit how many sites to return
  @type limit : int
  
  @rtype : list
  @return : list of alexa top N sites
  """
  sites = [] 
  if limit:
    try: 
      limit = int(limit)
    except ValueError: 
      LOG.error('limit is non-integer')
      limit = None
  count = 0
  with open('Input/top-1m.csv', 'r') as frdr:
    for line in frdr:
      sites.append(line.split(',')[1])
      count += 1
      if limit and count >= limit :
        break
  return sites

def load_training_sites(train_sites):
  """
  Input : A pickle file containing a dict where the key is category and values
  are a list of websites to visit or a txt files to be parsed
  """
  if train_sites.endswith('.txt'):
    cat_dict = {}
    with open(train_sites,'r') as frdr:
      cur_cat = None
      for line in frdr:
        if line.startswith('$'):
          cur_cat = line.strip('$\n:').strip()
          try:
            cat_dict[cur_cat] = []
          except KeyError :
            LOG.exception('Duplicate categories detected...')
        elif line.startswith('@'):
          line = line.strip('@\n').strip()
          cat_dict[cur_cat].append(line)
    return cat_dict

  elif train_sites.endswith('.pkl'):
    # dictionary where key is category, and value is a list of websites to visit
    with open(train_sites, 'r') as frdr:
      training_sites_to_visit = cPickle.load(frdr)
    return training_sites_to_visit
      
def do_training_phase_sequential(wd, train_sites):
  for train_site in train_sites:
    LOG.info('Fetching training_site : %s ' % train_site) 
    pr = Process(target=fetch_website, args=(wd, train_site, 8))
    pr.start()
    pr.join(timeout=10)
    if pr.is_alive():
      pr.terminate()
