import os
import uuid
import logging
import subprocess
import shutil
from time import sleep
from ad_grabber_webdriver import *
from selenium.webdriver.common.by import By

LOG = logging.getLogger("logAdGrabber")

def query_bluekai_apm(wd):
  uid = uuid.uuid1()
  output_tmp = '%s.png' % uid
  output_txt = 'uid'
  url = 'bluekai.com/registry'
  filtered = 'http://bluekai.com/registry/assets'
  fetch_status = fetch_website(wd, url, implicit_to=5, explicit_to=8, scroll=True)
  items = []
  if not fetch_status:
    return items
  elements = wd.find_elements(By.TAG_NAME, 'img')
  for e in elements:
     target = e.get_attribute("src")
     if target.endswith('.png') and not target.startswith(filtered):
       LOG.info(target)
       ret = subprocess.call(
           ['wget','-t', '3', '-T', '3', '-q', target, '-O', output_tmp])
       if ret > 0:
         raise Exception("Can't issue an external GET to retrieve png resource")
       ret = subprocess.call(
           ['convert', '-resize', '2500', output_tmp, output_tmp])
       if ret > 0:
         raise Exception("Can't resize png resource for OCR")
        
       ret = subprocess.call(
           ['tesseract', output_tmp, output_txt,'-psm', '7'])

       if ret > 0:
         raise Exception("Can't OCR this png")

       with open('%s.txt' % output_txt,'r') as frdr:
         for i in frdr:
           i = i.strip()
           if i not in items:
             items.append(i.strip())
   
       os.unlink('%s.txt' % output_txt)
       os.unlink(output_tmp)
  return items     

def parse_bluekai_apm(soup, dirname):
  # this function is used by casper js's bluekai apm scrapper
  interests = []
  os.makedirs(dirname)
  try:
    imgs = soup.findAll('img')
    for img in imgs:
      src = img.get(key='src')
      if src and src.startswith('assets'):
        continue
      elif src and src.endswith('.png'):
        uid = uuid.uuid1()
        output_tmp = os.path.join('%s.png' % uid)
        output_path = os.path.join(dirname, output_tmp)
        LOG.info(src)
        ret = subprocess.call(
            ['wget','-t', '3', '-T', '3', '-q', src, '-O', output_path])
        if ret > 0 :
          LOG.error("Can't issue external GET to retrieve resource")
          continue
        interests.append(output_tmp)
    LOG.info(interests)
  except Exception as e:
    LOG.error(e)
  return interests 
