#bke! /usr/bin/env python
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
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(),'lib'))
import logging, logging.handlers
import ConfigParser
import random
import cPickle
import addon_flask 
#import argparse
import socket

from datetime import datetime
from time import sleep
from flask import Flask, request
from multiprocessing import Process, Queue
from Queue import Empty

from adregex import *
from ad_grabber_webdriver import *
from ad_grabber_util import *
import ad_grabber_logging 
from ad_grabber_bluekaiapm import *
from ad_grabber_googleapm import *
from ad_grabber_network import *
###############################################################################
#### Configuration Parameters
""" 
There are two different config files
baseconfig.cfg provides default configuration settings for adgrabber
expconfig.cfg is related to experiments and generated for each job
"""

# global, immutable dict for config params
COPT = {
  'MACHINEID' : None,   # UID of this particular VM
  'XVFBENABLED' : None, # headless webdriver?
  'SESSION_FOLDER' : None,
  'STATS_FOLDER' : None, 
  'EXPORT_FOLDER' : None, 
  'BIN_PATH' : None,
  'PROFILE_PATH' : None,
  # Experiment Related configs
  'TEST_SITES' : None,
  'TRAIN_SITES' : None, 
  'TRAIN_MODE' : None,
  'REFRESH_NUM' : None, 
  'PROFILE' : None,
  'PRESERVE_COOKIES' : None,
  'USE_TOR' : None,
  'NUM_OF_TRAIN_WORKERS' : None, 
  'JOB_NAME' : None, 
  'GOOG_APM' : None, 
  'BLUEKAI_APM' : None, 
  'SERVER' : None, 
  'ERROR_SERVER' : None
} 
COMM = None # communicator to talk to hub.py
LOG = None  # global     
MAX_TESTSITE_TIMEOUT = 17
###############################################################################
def ad_grabber_main(port = 5000, ret_queue=None, flask_ext_queue=None):
  """ 
  Parameters
  ----------
  port : which port will be used for communication between local flask server
         and FF plugin
  ret_queue : queue for indicating that this method is returning
  flask_ext_queue : queue between ad_grabber and local flask server
  """
  global COPT, LOG
  load_config(port)
  LOG = ad_grabber_logging.init_logger("logAdGrabber", COPT['LOGLEVEL'], port,
      COPT['ERROR_SERVER'], COPT['MACHINEID'])
  try:
    ###########################################################################
    #
    # We first define the keywords used in this experiment
    # 1) profile - Our heuristical estimate of the knowledge ad-companies have
    # of us based on the keywords we used when quering websites, sites visited,
    # links clicked, ads clicked etc. Currently we are only building profiles 
    #  by visiting sites.
    # 2) Tracking mechanisms - A large list of possible ways where ad networks
    # can fingerprint or identify users. Right now we are only considering
    # client side cookies. By eliminating tracking mechanisms, our hypothesis is
    # that ad-trackers are not able to identify users, and hence corelate a user
    # with a profile they have previously created. If this were true, it allows
    # us to create different profiles easily.
    # 3) Training phase - Stage in our experiment where we induce
    # particular behaviors or interests in our profile. We achieve this by
    # performing a set of actions (i.e visiting certain sites pertaining to
    # dogs, if we want to induce the interest of dogs).   
    # induced. 
    # TODO more documentation

    # We first define a 'run' as a sequential execution of the following:
    # 0) Start off with a clean browser profile
    # i) visit each site in a list of URLs we picked for training
    # ii) Visit one test site and download all the ads displayed on a test site.
    # A test site may be chosen as a site whose context is different from the
    #topic that we are trying to induce in the training stage

    # Finally we define a session as a sequence of runs, on the same set of
    # training sites, and test sites

    # TODO rollback if quit unexpectedly
    
#    LOG.debug('Loading Training sites')
#    training_sites = load_training_sites(TRAIN_SITES)
#    LOG.debug('Loading Test sites')
#    test_sites = load_alexa_sites(1000)
#    test_sites = load_testing_sites(TEST_SITES)
#    random.shuffle(test_sites)

    start_time = datetime.datetime.now()
    # Initialize Session
    session_string = initialize_session(COPT['JOB_NAME'], start_time)
    total_test_sites = COPT['REFRESH_NUM'] * len(COPT['TEST_SITES'])
    visited = 0   # how many test sites visited so far
    google_apm_enabled = False
    google_results = { test_site : None for test_site in COPT['TEST_SITES'] }
    bluekai_results = { test_site : None for test_site in COPT['TEST_SITES']}
    timing = { test_site : None for test_site in COPT['TEST_SITES'] } 
    ################### START OF EXPERIMENT LOOP #####################
    for test_site in COPT['TEST_SITES']:
      test_fetch_start = datetime.datetime.now()
      test_site = test_site.strip()
      #test if test site is reachable
      try:
        socket.gethostbyname(test_site)
      except Exception as e:
        LOG.debug('fetch_website_process: unreachable url %s %s' % 
          (test_site, e))
        timing[test_site] = "UNREACHABLE"
        if COPT['GOOG_APM']:
          google_results[test_site] = "UNREACHABLE"
        if COPT['BLUEKAI_APM']:
          bluekai_results[test_site] = "UNREACHABLE"
        visited += 1
        continue

      attempt = 0
      # maximum of 3 attempts per test site, incase of network errors 
      while attempt < COPT['MAXATTEMPT']:
        session_results = {}
        attempt += 1 
        sanitized_url = test_site.strip().replace('/', '_')
        
        try:
          wd = run_master(COPT['PROFILE_PATH'], COPT['BIN_PATH'], port,
                          COPT['ADDONTIMEOUT'])
        except WebdriverException as e:
          LOG.info(e)
          continue
        except Exception as e:
          LOG.error(e)
          continue

        if (COPT['PRESERVE_COOKIES']):
          preserve_cookies(COPT['PROFILE_PATH'])
  
        #### TRAINING STAGE ####
        if COPT['TRAIN_MODE'] :
          LOG.info('Entering Training phase...')
          try:
            do_training_phase_sequential(wd, COPT['TRAIN_SITES'])
          except Exception as e:
            LOG.error(e)
            close_webdriver(wd, True)
            continue
     
        while not flask_ext_queue.empty():
          LOG.debug("*** FF queue not empty %s: " % flask_ext_queue.get())
        assert flask_ext_queue.empty()
  
        ######## TEST STAGE #########
        #  output_dirname = os.path.join(session_name, train_category,
        #      sitename_wo_slash)
        #  create_folder(SESSION_FOLDER, output_dirname)
          
        time_now = datetime.datetime.now()
        LOG.info('Fetch test site: %s. SitesVisited: %d/%d TimeElapsed: %s' %
            (test_site, visited, total_test_sites, time_now - start_time ))
        if COPT['GOOG_APM']:
          # We need to visit google apm site and click enable behavioral ad
          # button
          google_apm_enabled = enable_google_apm(wd)
          if google_apm_enabled:
            LOG.info('Enabled APM')
          else :
            LOG.error("Can't enable google APM. Retrying")
            close_webdriver(wd, True)
            continue

        # Spawn workers of WGET first 
        fetch_starttime = datetime.datetime.now()
        fetch_website(wd, test_site, implicit_to=11, explicit_to=14,
          scroll=True) 
        fetch_endtime = datetime.datetime.now()
       
        # Give each fetch a fixed allowance of time to finish loading third
        # party requests.  
        # get the result from the firefox addon
        timeout = 15
        if (fetch_endtime - fetch_starttime).seconds < MAX_TESTSITE_TIMEOUT:
          timeout = MAX_TESTSITE_TIMEOUT - (fetch_endtime - fetch_starttime).seconds
        payload = filter_results(flask_ext_queue, timeout, test_site)
        LOG.info('Done fetching test website: %s' % test_site)

        if payload:
          LOG.debug('Payload received. Preparing to send to hub %d' %
            len(payload))
          packet = { 'DOMAIN' : test_site,
                   'PAYLOAD' : payload
                   }
          if not COMM.send_request(packet, 'trackers', retry=1):
            LOG.error("Can't send result packet to server. Server Down?")
            close_webdriver(wd, True)
            continue
       
          apm_attempt = 0
          while apm_attempt < COPT['MAXATTEMPT']:
            apm_attempt += 1
            if COPT['GOOG_APM'] and google_apm_enabled:
              try: 
                google_results[test_site] = query_google_apm(wd)
              except Exception as e:
                LOG.error("Can't query google_apm. Retrying. %s" % e)
                google_results[test_site] = "ERROR"
                continue
            if COPT['BLUEKAI_APM']:
              try:
                bluekai_results[test_site] = query_bluekai_apm(wd) 
              except Exception as e:
                LOG.error("Can't query bluekai apm. Retrying. %s" % e)
                bluekai_results[test_site] = "ERROR"
                continue
            break
        else:
          LOG.info('fetch_website on url %s did not return success. '
                    'Retryin %d %s' % (test_site, attempt, COPT['MAXATTEMPT']))
          close_webdriver(wd, True)
          continue  

        #LOG.info('Closing webdriver ...\n\n')
        close_webdriver(wd)
        
        if COPT['GOOG_APM'] and google_results[test_site] == "ERROR":
          timing[test_site] = "ERROR"
        elif COPT['BLUEKAI_APM'] and google_results[test_site] == "ERROR":
          timing[test_site] = "ERROR"
        else:
          timing[test_site] = str(datetime.datetime.now() - test_fetch_start)
        visited += 1
        break
         
    ################################################################## 
    # Compiling results for analysis
    end_time = datetime.datetime.now()
    # Exporting results of this session
    LOG.info('Done. Process took %s' % (end_time - start_time)) 

    # TODO don't send results by HTTP. save to NFS
    # Exporting Results ...
    payload = { 'JOB_NAME' : COPT['JOB_NAME'], 
                'TIMING'   : timing }
    if COPT['GOOG_APM'] and google_apm_enabled:
      payload['GOOG_APM_RES'] = google_results
    if COPT['BLUEKAI_APM']:
      payload['BLUEKAI_APM_RES'] = bluekai_results

    sent = COMM.send_request(payload, 'results')
    if not sent: 
      payload['ID'] = COPT['MACHINEID']
      if not os.path.exists('unsent') : os.makedirs('unsent')
      with open('unsent/%s.pkl' % COPT['JOB_NAME'], 'w') as fwtr:
        # TODO write code to deal with unsent result
        cPickle.dump(payload, fwtr)
    
    # sending timing info of the test site

    if ret_queue :
      LOG.info('Done with this job, returning to client.py')
      ret_queue.put(port)
      return
  except KeyboardInterrupt:
    LOG.debug("KeyboardInterrupt detected ... Killing program")
    if ret_queue :
      ret_queue.put(port)
      return 

def load_config(port = 5000):
  global COPT, COMM
  config = ConfigParser.ConfigParser()
  config.optionxform = str
  config.readfp(open('baseconfig.cfg')) 
  # Machine Related configs
  COPT['MACHINEID'] = config.get('machineinfo', 'MACHINEID')
  COPT['MAXATTEMPT'] = config.getint('machineinfo', 'MAXATTEMPT')
  COPT['XVFBENABLED'] = config.getboolean('machineinfo', 'XVFBENABLED')
  # Output Related Configs
  COPT['SESSION_FOLDER'] = config.get('outputfolder', 'SDOWNLOADFOLDER') 
  COPT['STATS_FOLDER'] = config.get('outputfolder', 'STATSFOLDER')
  COPT['EXPORT_FOLDER'] = config.get('outputfolder', 'EXPORTFOLDER')
  COPT['LOGLEVEL'] = config.get('logging', 'LOGLEVEL')
  # Machine Related configs
  COPT['MACHINEID'] = config.get('machineinfo', 'MACHINEID')
  COPT['XVFBENABLED'] = config.getboolean('machineinfo', 'XVFBENABLED')
  # Firefox Plugin Related configs
  COPT['ADDONTIMEOUT'] = config.getint('firefoxplugin', 'ADDONTIMEOUT')

  if not port:
    fname = 'expconfig.pkl'
  else :
    fname = 'expconfig_%d.pkl' % port 
  with open(fname, 'r') as frdr :
    EXPCONF = cPickle.load(frdr)
  COPT['TEST_SITES'] = EXPCONF['TEST_SITES']
  COPT['TRAIN_SITES'] = EXPCONF['TRAIN_SITES']
  COPT['TRAIN_MODE'] = EXPCONF['TRAIN_MODE'] 
  COPT['REFRESH_NUM'] = EXPCONF['REFRESH_NUM']
  COPT['PROFILE'] = EXPCONF['PROFILE']
  COPT['PRESERVE_COOKIES'] = EXPCONF['PRESERVE_COOKIES']
  COPT['USE_TOR'] = EXPCONF['USE_TOR']
  COPT['NUM_OF_TRAIN_WORKERS'] = EXPCONF['NUM_OF_TRAIN_WORKERS']
  COPT['JOB_NAME'] = EXPCONF['JOB_NAME']
  COPT['GOOG_APM'] = EXPCONF['GOOG_APM']
  COPT['BLUEKAI_APM'] = EXPCONF['BLUEKAI_APM']
  COPT['SERVER'] = EXPCONF['SERVER']
  COPT['ERROR_SERVER'] = EXPCONF['ERROR_SERVER']
  COPT['PROFILE_PATH'] = config.get('firefox', COPT['PROFILE'])
  if COPT['USE_TOR'] :
    COPT['BIN_PATH'] = config.get('firefox', 'TORBINARYPATH')
  else:  
    COPT['BIN_PATH'] = config.get('firefox', 'BINARYPATH')
  COMM = Communicator(COPT['MACHINEID'], COPT['SERVER'], "logAdGrabber")
  os.remove(fname)

if __name__ == "__main__":
  # for unit testing
  ad_grabber_main()
