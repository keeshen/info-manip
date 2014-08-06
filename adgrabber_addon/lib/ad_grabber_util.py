from time import sleep
from uuid import uuid1
from pprint import pprint
from shutil import copy2
from multiprocessing import Process, Queue, Pool, Manager
from ad_grabber_classes import *
from adregex import *
from pygraph.classes.digraph import digraph

import os
import json
import jsonpickle
import subprocess
import cPickle
import logging
LOG = logging.getLogger("logAdGrabber")
ADREGEX = AdRegEx()

def check_duplicate(fp1, fp2):
  """takes two files, does a diff on them, returns True if same"""
  try:
    subprocess.check_output(['diff', fp1, fp2])
    return True
  except subprocess.CalledProcessError:
    return False

def identify_uniq_ads(session_results):
  """
  i) Identify duplicate ads
  ii) bin the ads by their dimensions
  iii) Keep track of the test sites and have many times they have displayed this
  ad
  """
  # bin by dimensions
  ads = {}
  notads = {}
  swf_bin = {}
  img_bin = {}
  error_bugs = []
  for train_category, cat_dict in session_results.items():
    for test_site, bug_dict_list in cat_dict.items():
      for index_count in range(len(bug_dict_list)):
        bug_dict = bug_dict_list[index_count] 
        for bug, bug_count in bug_dict.items():
          bug_filetype = bug.get_filetype()
          bug_filepath = bug.get_filepath()
          if bug_filepath == '':
            #LOG.debug('did not manage to curl the scripts for bug:%s' % bug)
            error_bugs.append(bug)
            continue

          if bug.is_ad(): # give zerofucks to non-ads
            height = '999'
            width = '999'
            if bug_filetype == 'swf':
              # choose from the swf media bin
              target_bin = swf_bin
              try:
                width = subprocess.check_output(['swfdump', '-X',
                  bug_filepath]).split(' ')[-1].strip()
                height = subprocess.check_output(['swfdump', '-Y',
                  bug_filepath]).split(' ')[-1].strip()
              except subprocess.CalledProcessError :
                LOG.exception("swfdump error on file %s" % bug_filepath)
            else:
              # choose from the img media bin
              target_bin = img_bin
              LOG.debug(bug_filepath)
              try:
                height = subprocess.check_output(['identify', '-format', '"%h"',\
                    bug_filepath]).strip()
                width = subprocess.check_output(['identify', '-format','"%w"',\
                    bug_filepath]).strip()
              except subprocess.CalledProcessError:
                LOG.exception("identify error on file %s" % bug_filepath)

            try:
              bug.set_dimension(height, width)
              dimension = '%s-%s' % (height, width)
              # check all the images in the bin with the dimensions
              m_list = target_bin[dimension]
              dup = None
              for m in m_list:
                if check_duplicate(bug_filepath, m.get_filepath()): 
                  dup = m
                  break
              if dup:
                # check if the duplicate ad came from a different test site
                if test_site in ads[dup]:
                  ads[dup][test_site] += bug_count
                else :
                  ads[dup] = {test_site : bug_count}
                # delete old bug reference, add new one and point to duplicated
                # bug
                del bug_dict[bug]
                bug_dict[dup] = bug_count

              else: 
                target_bin[dimension].append(bug)
                ads[bug] = {test_site : bug_count}
              # tally up the results
            except KeyError: # The bin hasn't been created
              target_bin[dimension] = [bug]
              ads[bug] = {test_site : bug_count}
        #  else:
            # notads

  return ads,error_bugs


def export_uniq_ads(ads, out_folder, rel_folder):
  """
  Takes all the uniq ads seen in this session and writes its metadata
  information to a csv file
  """
  try :
    os.makedirs(out_folder)
    os.makedirs(os.path.join(out_folder, rel_folder))
  except OSError:
    LOG.debug('Creating output folder')

  fwtr = open(os.path.join(out_folder, 'uniq_ads.csv'), 'w')
  # Relative location = Location of the ad within this current session
  # Global location, added when an ad is matched with existing ads in DB
  fwtr.write('#UID, Ad-Company, Ad-Filetype, Height, Width, Rel-Location, src\n')
  
  for bug in ads.keys():
    height, width = bug.get_dimension()
    filepath = bug.get_filepath()
    name = bug.get_name()
    src = bug.get_src()
    filetype = bug.get_filetype()
    new_uuidname = '%s.%s' % (uuid1(), filetype)
    bug.set_uuid(new_uuidname)
    new_filepath = os.path.join(out_folder, new_uuidname)
    rel_filepath = os.path.join(rel_folder, new_uuidname)
    copy2(filepath, new_filepath)
    fwtr.write('{0}, {1}, {2}, {3}, {4}, {5}, {6}\n'.format(new_uuidname,
      name, filetype, height, width, rel_filepath, src))
  fwtr.close()
  return ads

def write_run_info(RUNINFO_DIR, session_date):
  # write to a file in runinfo_dir to tell automation script this run is done
  fp =  os.path.join(RUNINFO_DIR, '%s.info' % session_date)
  with open(fp, 'w') as fwtr:
    fwtr.write('OK')

def write_session_info(vmid, machineid, profile, session_date, train_mode, training_sites,
    test_sites, num_of_refresh, export_folder):
  train_category = training_sites.keys()[0]
  train_sites_to_visit = training_sites[train_category]
  with open(os.path.join(export_folder, 'session_info.csv'), 'w') as fwtr:
    fwtr.write('session_str : %s\n' % session_date) 
    fwtr.write('machine_info : %s\n' % machineid)
    fwtr.write('vmid : %s\n' % vmid)
    fwtr.write('profile : %s\n' % profile)
    fwtr.write('train_mode : %s\n' % train_mode)
    fwtr.write('num_of_refresh : %d\n' % num_of_refresh)
    fwtr.write('training_topic : %s\n' % train_category)
    fwtr.write('training_sites : ')
    for site in train_sites_to_visit:
      fwtr.write('%s, ' % site)
    fwtr.write('\nnum_of_train_sites : %d\n' % len(train_sites_to_visit))
    fwtr.write('test_sites : ')
    for site in test_sites:  
      fwtr.write('%s, ' % site[1])
    fwtr.write('\nnum_of_test_sites : %d\n' % len(test_sites))


def generate_stats(results, ads, vmid, session_date, export_folder, process_ex_time):
  """
  Generates stats on
  - uniq ads seen on the test sites
  - total number of ads seen on the test sites
  - total number of ads seen on all test sites
  - total number of uniq ads seen on all test sites
  """
  try:
    os.makedirs(export_folder)
  except OSError:
    pass

  # to be read and inserted into db
  totalads = 0  # total number of ads seen during this session
  totaluniqads = len(ads) # does not support multicategories at this point

  # for each category, for each test site, count total number of ads seen
  totalad_category = {} 
  # for each category, for each test site, count total number of uniq ads seen
  uniqad_category = {}
  
  with open(os.path.join(export_folder, 'session_bugs.csv'), 'w') as bugs_wtr:
    bugs_wtr.write('#Ad-UID, Website-URL, Refresh-Num, Training-Topic,\
        Site-Context, BugCount, BugSrc\n')
    for train_category, cat_dict in results.items():
      totalad_category[train_category] = {}
      uniqad_category[train_category] = {}
      for test_site, bug_dict_list in cat_dict.items():
        total_ads = 0 # for each site
        uniq_ads = [] # for each site
        for refresh_num in range(len(bug_dict_list)):
          bug_dict = bug_dict_list[refresh_num]
          for bug, bugcount in bug_dict.items():
            if bug.is_ad():
              uuid = bug.get_uuid()
              bugs_wtr.write('{0}, {1}, {2}, {3}, {4}, {5}, {6}\n'.format(uuid, test_site,
                refresh_num, train_category, 'N/A', bugcount, bug.get_src()))
              total_ads += bugcount
              if bug not in uniq_ads:
                uniq_ads.append(bug)
        totalad_category[train_category][test_site] = total_ads
        uniqad_category[train_category][test_site] = len(uniq_ads)
        totalads += total_ads # global count for total ads

  with open(os.path.join(export_folder, 'session_stats.csv'), 'w') as ses_wtr:
    # write some metadata information about this session
    ses_wtr.write('#VMID: %s\n' % vmid)
    ses_wtr.write('#Session-Date: %s\n' % session_date)
    ses_wtr.write('#Time to complete: %s\n' % process_ex_time)
    ses_wtr.write('#Training Categories: %s\n' % str(results.keys()))
    ses_wtr.write('#Total Number of ads: %d\n' % totalads)
    ses_wtr.write('#Total Uniq ads: %d\n\n' % totaluniqads)
    ses_wtr.write('#TrainingTopic, Test-Site, NumberOfVisit, TotalAds, UniqAds\n')

    for train_category, cat_dict in results.items(): 
      for test_site, bug_dict_list in cat_dict.items():
        num_of_visit = len(bug_dict_list)
        ses_wtr.write('{0}, {1}, {2}, {3}, {4}\n'.format(train_category,
          test_site, num_of_visit, totalad_category[train_category][test_site],
          uniqad_category[train_category][test_site]))



def export_ads(results,out_folder):
  """
  This function creates a csv file which contains all the unique ads seen in
  each test site (including all the refreshes)

  TODO update the doc
  results is a dictionary of the following
  results = { Category : Value, ... }
  value =  { test_site_url : [ result1, result2, ... resultN], ... }
  resultN : { WebBug : count, ... }
  """
  try:
    os.makedirs(out_folder)
  except OSError:
    LOG.debug('Creating output file folder ...')
  
  export_ad_counter = 1 # assign unique number to ads for export to mturk
  #short_listed_companies = ['google adsense', 'doubleclick']
  with open(os.path.join(out_folder,'ad_labelling.csv'), 'w') as fwtr:
    # write the titles
    fwtr.write('#{0}, {1}, {2}, {3}, {4}, {5}, {6}, {7}, {8}, {9}\n'.format(\
        'Ad#', 'Company', 'FileType', 'Ad-Category', 'Website-URL',\
        'Refresh-Num','Training-Topic', 'Context-of-site', 'Total', 'Ad-src'))
    # make sure we only add one ad
    for train_category, cat_dict in results.items():
      for test_site, bug_dict_list in cat_dict.items():
        for refresh_num in range(len(bug_dict_list)):
          bug_dict = bug_dict_list[refresh_num]
          for bug, bugcount in bug_dict.items():
            if not bug.is_ad():
              #TODO check bug_type in ffext
              continue
            if bug.get_filetype() in ['swf', 'png', 'gif', 'jpg']:
              file_name = '%d.%s' % (export_ad_counter, bug.get_filetype())
              new_location = os.path.join(out_folder, file_name)
              copy2(bug.get_filepath(), new_location)
              fwtr.write('{0}, {1}, {2}, {3}, {4}, {5}, {6}, {7} , {8}, {9},\
                  \n'.format(file_name, bug.get_name(), bug.get_filetype(),
                  '' ,test_site, refresh_num, train_category, 'N/A', bugcount,
                  bug.get_src()))
              export_ad_counter += 1


def get_bug_type(file_type):
  is_ad = False
  bug_type = 'text'
  if file_type.startswith('HTML') or \
      file_type.startswith('ASCII') or \
      file_type.startswith('UTF-8 Unicode English') or \
      file_type.startswith('very short') :
    bug_type = 'text'
  elif (file_type.endswith('1 x 1') and file_type.startswith('GIF')): 
    bug_type = 'gif'
  elif file_type.startswith('PNG'):
    bug_type = 'png'
    is_ad = True
  elif file_type.startswith('GIF'):
    bug_type = 'gif'
    is_ad = True
  elif file_type.startswith('Macromedia Flash'):
    bug_type = 'swf'
    is_ad = True
  elif file_type.startswith('JPEG'):
    bug_type = 'jpg'
    is_ad = True
  return bug_type, is_ad


def parse_buginfo(entry):
  """
  Takes the json decoded bug information and inserts it into a WebBug instance
  """
  bugname = entry['bug']['name'].replace(' ','').replace('/','_')
  bugsrc = entry['ent']['policyContentLocation']
  bugpattern = entry['bug']['pattern']
  try :
    bugaffiliation = entry['bug']['affiliation']
  except KeyError:
    bugaffiliation = ""
  bugtype = entry['bug']['type']
  bugpathname = entry['ent']['pathname']
  return WebBug(name=bugname, src=bugsrc, affiliation=bugaffiliation,
      bug_type=bugtype, matched_pattern=bugpattern, pathname=bugpathname)

def curl_worker_legacy(args):
  output_dir = args[0]
  saved_file_name = args[1]
  path = args[2]
  bug = args[3]
  curl_result_queue = args[4]

 # subprocess.call(['curl', '-o', path , bug.get_src() ])
  subprocess.call(['wget', '-t', '1', '-q', '-T', '3', '-O', path , bug.get_src()])
  # Use the unix tool 'file' to check filetype
  subpr_out = subprocess.check_output(['file', '-b', path]).strip()
  filetype, is_ad = get_bug_type(subpr_out)

  if is_ad:
    new_path = os.path.join(output_dir, '%s.%s' % (saved_file_name, filetype))
  else:
    new_path = os.path.join(output_dir, 'notad', '%s.%s' % (saved_file_name,\
      filetype))
  os.rename(path, new_path)

  bug.set_is_ad(is_ad)
  bug.set_filetype(filetype)
  bug.set_filepath(new_path)
  curl_result_queue.put(bug)

def process_results_legacy(refresh_count, output_dir, ext_queue, result_queue,\
    num_of_workers=8):
  """
  This function goes through all the bugs identified by the firefox plugin and
  aggregates each bug's occurence in a given page. The aggregation is necessary
  for duplicate ads on the same page
  """
  bug_dict = {} # dict to keep track of how many duplicates of each bug, if
                # exists
  try:
    # separate the non-ads from the ads for ease of handchecking
    os.makedirs(output_dir)
    os.makedirs(os.path.join(output_dir, 'notad'))
  except OSError:
    pass

  # uses a pool of 'curl' workers
  curl_worker_pool = Pool(processes=num_of_workers)
  manager = Manager()
  curl_result_queue = manager.Queue()
  
  dl_counter = 0 # keep track of how many bugs downloaded
  while True:
    try:
      found_bugs = json.loads(ext_queue.get(block=True, timeout=2))
    except Exception:
      LOG.debug('Timing out on get from queue...')
      break
    for entry in found_bugs:
      bugname = entry['bug']['name'].replace(' ','').replace('/','_')
      bugsrc = entry['ent']['policyContentLocation']
      bugpattern = entry['bug']['pattern']
      try :
        bugaffiliation = entry['bug']['affiliation']
      except KeyError:
        bugaffiliation = ""
      bugtype = entry['bug']['type']
      bugpathname = entry['ent']['pathname']
      bug = WebBug(name=bugname, src=bugsrc, affiliation=bugaffiliation,
          bug_type=bugtype, matched_pattern=bugpattern, pathname=bugpathname)
      try:
        # matched an entry in the bugdict, incr count and continue
        bug_dict[bug] += 1
        continue
      except KeyError:
        bug_dict[bug] = 1 

      saved_location ='Visit%d_%s%d' % (refresh_count, bugname,\
          dl_counter)
      dl_counter += 1
      save_to_path = os.path.join( output_dir, '%s' % saved_location)
      obj = curl_worker_pool.apply_async(curl_worker_legacy, \
          ((output_dir, saved_location, save_to_path, bug, curl_result_queue),))
  try:
    sleep(0.5)
    curl_worker_pool.join()
    curl_worker_pool.close()
    curl_worker_pool.terminate()
  except Exception:
    LOG.debug('Closing pool')

  while not curl_result_queue.empty():
    cbug = curl_result_queue.get()
    # ugly code here
    bugcount = bug_dict[cbug]
    del bug_dict[cbug]
    bug_dict[cbug] = bugcount
  with open( os.path.join(output_dir, 'bug_dict%d.pkl' % refresh_count), 'w') as fwtr:
    cPickle.dump(bug_dict, fwtr)
  result_queue.put(bug_dict)


def curl_worker(output_dir, input_queue, worker_output_queue, worker_id,\
    ack_queue):
  while True:
    try:   
      task = input_queue.get()
      if len(task) == 1 and task[0] == "STOP":
        LOG.debug('curl_worker %d received stop' % worker_id)
        break
    except Exception:
      LOG.error('Error:')
    #LOG.debug(task)

    saved_file_name = task[0]
    path = task[1]
    bug = task[2]
    
    try:
    #  subprocess.call(['curl',  '-o', path , bug.get_src()])
      subprocess.call(['wget', '-t', '1', '-q', '-T', '3', '-O', path , bug.get_src()])
      subpr_out = subprocess.check_output(['file', '-b', path]).strip()
    except Exception as e : 
      LOG.debug('Exception captured %s\n\n' % e)

    filetype, is_ad = get_bug_type(subpr_out)
    if is_ad:
      new_path = os.path.join(output_dir, '%s.%s' % (saved_file_name, filetype))
    else:
      new_path = os.path.join(output_dir, 'notad', '%s.%s' % (saved_file_name,\
          filetype))
    os.rename(path, new_path)
    bug.set_is_ad(is_ad)
    bug.set_filetype(filetype)
    bug.set_filepath(new_path)
    worker_output_queue.put(bug)
  ack_queue.put(worker_id)
  return  


def build_nodes(jsonData):
  """
  This function takes a JSON encoded output of the firefox addon and builds a
  call graph for the javascript/HTML redirections

  @rtype nodes: dict
  @return: A graph of redirection chains
  """
  nodes = {}

  def _process_cookiestr(cookieStr):
    """
    parses a dictionary of req/resp calls to extract the cookie information
    returns a list of cookies set on this domain
    """
    cookie_list = []
    # parses cookie str if a cookie has been set
    for cookie in cookieStr.split('\n'):
      c = {}
      for cook in cookie.split(';'):
        token = cook.split('=', 1)
        if len(token) < 2: 
          # usually this is just a flag e.g HTTPOnly, HTTPSOnly
          continue
        c[token[0]] = token[1]
      cookie_list.append(c)
    return cookie_list 
  
  def _check_node(d):
    try:
      domain_node = nodes[d]
    except KeyError:
      isBug, bug_name, bug_type = ADREGEX.search(domain)
      domain_node = WebNode(domain, isBug, bug_name, bug_type)
      nodes[d] = domain_node
    return domain_node 
  
  #jsonData contains all the domains and all the req/resp pairs made to them
  #iterating over the domains first
  for domain, dval in jsonData.items():
    # but first check if a node for this domain has been created or not
    domain_node = _check_node(domain)
    cookie_list = []
    # iterating thru all the req/resp pairs on a domain
    for info in dval:
      domainPath = info['domainPath']
      referrerPath = info['referrerPath']
      referrer = info['referrer']
      cookieBool = info['cookie']  
      
      parsed_cookie = None 
      if cookieBool:
        cookieStr = info['cookiestr']
        parsed_cookie = _process_cookiestr(cookieStr)
        cookie_list.append(parsed_cookie)
      domain_node.add_reqresp({'domainPath' : domainPath,
                               'referrer' : referrer,
                               'referrerPath' : referrerPath,
                               'cookieList' : parsed_cookie
                              })
      # making sure that we also create the node for the referrer
      referrer_node = _check_node(referrer)
      referrer_node.add_child(domain_node)
      domain_node.add_parent(referrer_node)
    domain_node.set_cookies(cookie_list)
  return nodes


def filter_results(extQueue, timeout_value, url):
  """
  This function takes the JSON output of the firefox addon, and matches the
  request URL against a list of known tracker/ads regexes. 

  Returns data structure containing request/resp info
  Returns None if did not receive results from FF addon
  """
  from Queue import Empty
  try:
    LOG.debug('Timeout value in filter_result :%d' % timeout_value)
    nodes = extQueue.get(True, timeout=timeout_value)
    
  except Empty as e:
    LOG.info('Did not receive any results from FF plugin for %s' % url)
    nodes = None
  finally:
    while not extQueue.empty():
      extQueue.get()
  return nodes

def process_results(refresh_count, output_dir, ext_queue, result_queue,
    num_of_workers=8):
  """
  This function goes through all the bugs identified by the firefox plugin and
  aggregates each bug's occurence in a given page. The aggregation is necessary
  for duplicate ads on the same page
  """
  workers_dict = {} # keep track of worker processes
  input_queue = Queue() # asynchronously feed workers task to do 
  worker_output_queue = Queue() # output queue from workers
  ack_queue = Queue()
  bug_dict = {} # dict to keep track of how many duplicates of each bug, if
                # exists
  try:
    # separate the non-ads from the ads for ease of handchecking
    os.makedirs(output_dir)
    os.makedirs(os.path.join(output_dir, 'notad'))
  except OSError:
    # Directory is created, Okay to pass
    pass

  for i in range(num_of_workers):
    p = Process(target=curl_worker, args=(output_dir, input_queue,\
        worker_output_queue, i, ack_queue))
    p.start()
    workers_dict[i] = p
  # uses a pool nodesurl' workers
 # curl_worker_pool = Pool(processes=8)
 # manager = Manager()
 # curl_result_queue = manager.Queue()
  
  dl_counter = 0 # keep track of how many bugs downloaded
  while True:
    try:
      found_bugs = json.loads(ext_queue.get(block=True, timeout=2))
    except Exception:
      LOG.debug('No more bugs found, break out of queue')
      break

    for entry in found_bugs:
      bug = parse_buginfo(entry)
      try:
        # matched an entry in the bugdict, incr count and continue
        bug_dict[bug] += 1
        continue
      except KeyError:
        bug_dict[bug] = 1 

      try:
        saved_location ='Visit%d_%s%d' % (refresh_count, bug.get_name(), dl_counter)
        dl_counter += 1
        save_to_path = os.path.join( output_dir, '%s' % saved_location)
        input_queue.put((saved_location, save_to_path, bug))
      except Exception as e:
        LOG.exception('%s' % e)

  for i in range(num_of_workers):
    # send stop signal
    input_queue.put(("STOP",))
  
  stopped = 0
  while stopped < len(workers_dict):
    ack = ack_queue.get()
    p = workers_dict[ack]
    p.join(timeout=1)
    if p.is_alive():
      p.terminate()
      LOG.debug('terminating process %d' % ack)
    stopped += 1
    
  while not worker_output_queue.empty():
    # receive results from the worker
    cbug = worker_output_queue.get()
    # ugly code here
    bugcount = bug_dict[cbug]
    del bug_dict[cbug]
    bug_dict[cbug] = bugcount

  with open( os.path.join(output_dir, 'bug_dict%d.pkl' % refresh_count), 'w') as fwtr:
    cPickle.dump(bug_dict, fwtr)
  result_queue.put(bug_dict)
  return


    

