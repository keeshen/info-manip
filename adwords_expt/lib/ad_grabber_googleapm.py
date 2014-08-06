import os
import uuid
import ast
import logging
from multiprocessing import Queue
from bs4 import BeautifulSoup as bs
from ad_grabber_webdriver import *
from selenium.webdriver.common.by import By

LOG = logging.getLogger("logAdGrabber")
def enable_google_apm(wd):
  url = 'www.google.com/ads/preferences/'
  enabled = False
  sq = fetch_website(wd, url, scroll=True)
  if not sq:
    LOG.error("Can't fetch google apm site")
    return enabled
     
  enable =  wd.find_elements(By.CLASS_NAME, 'ru') 
  if enable and len(enable) == 1:
    try:
      enable[0].submit()
      enabled = True
    except Exception as e:
      LOG.error("Can't click submit button!    %s" % e)
  else :
    LOG.error("Can't locate enable button!")
    return enabled
  return enabled

def parse_page_source(soup):
  preferences = {}
  script_tags = soup.find_all('script')
  target = False
  for script in script_tags:
    text = script.getText()
    if text.startswith("AF_initDataCallback({key: '89',"):
      # Check for interests based on websites
       prefs = extract_prefs(text.encode('UTF8'))
       preferences['web'] = prefs
       target = True
    elif text.startswith("AF_initDataCallback({key: '69',"):
      # Check for interests based on youtube activity
       prefs = extract_prefs(text.encode('UTF8'))
       preferences['youtube'] = prefs
       target = True
  return preferences


def query_google_apm(wd):
  LOG.debug('Begining to query google apm')
  url = 'google.com/ads/preferences/'
  fetch_status = fetch_website(wd, url, implicit_to=11, explicit_to=14,
                                scroll=True)
  if not fetch_status:
    raise Exception('Could not load %s' % url)
  page_source = wd.page_source
  if not page_source:
    raise Exception('Empty page source')
  soup = bs(page_source)
  preferences = parse_page_source(soup)

def extract_prefs(target):
  """ Strip the text to get prefs """
  target = target.strip(');').strip('AF_initDataCallback(')
  interm_data = target.split(',',2)[2].split(',', 1)[1]
  interm_data = extract_from_brackets(interm_data)
  preferences = ast.literal_eval(interm_data)
  return preferences

def extract_from_brackets(data_string):
  bracket_count = 0
  started = False
  start_index = 0
  index = 0
  while bracket_count > 0 or not started:
    if data_string[index] == '[' and not started:
      started = True
      bracket_count += 1
      start_index = index
    elif data_string[index] == '[' :
      bracket_count += 1
    elif data_string[index] == ']' :
      bracket_count -= 1
    index += 1
  return data_string[start_index:index]

