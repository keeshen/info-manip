#! /usr/bin/env python

from flask import Flask, request
from multiprocessing import Queue
import json
import datetime
import pprint
import logging
from ad_grabber_logging import *

LOG = None
app = Flask(__name__)
ENQUEUEON = False
EXT_RES_QUEUE = None
@app.route('/join', methods=['GET','POST'])
def process_req():
  if request.method == 'POST' :
    data = json.loads(request.data)
    LOG.debug(data)
    # Registering a new client to the service
    try:
      clients[data['id']] 
    except KeyError:
      clients[data['id']] = datetime.datetime.now()
      LOG.debug('Added new client %s' % data['id'])
    return "OK"   
  elif request.method == 'GET':
    return "OK"

@app.route('/heartbeat', methods=['POST'])
def process_heartbeat():
  data = json.loads(request.data)

  clients[data['id']] = datetime.datetime.now()
  return "OK" 

@app.route('/results', methods=['POST'])
def process_results():
  data = json.loads(request.data)
  clients[data['id']] = datetime.datetime.now()
  return "OK"

@app.route('/enqueueon', methods=['GET','POST'])
def process_enqueue_on():
  global ENQUEUEON
  ENQUEUEON = True
  return "OK"

@app.route('/enqueueoff', methods=['GET','POST'])
def process_enqueue_off():
  global ENQUEUEON
  ENQUEUEON = False
  return "OK"

@app.route('/join', methods=['GET'])
def process_join():
  return "OK"

@app.route('/log', methods=['POST'])
def process_logs():
  try:
    LOG.debug('Adding result to ext queue')
    EXT_RES_QUEUE.put(request.data)
  except Exception as e :
    LOG.error(e)
  return "OK"

@app.route('/shutdown', methods=['POST', 'GET'])
def shutdown_server():
  LOG.debug('request received for flask /shutdown')
  func = request.environ.get('werkzeug.server.shutdown')
  if func is None:
    raise RuntimeError('Not running with the Werkzeug Server')
  func()
  return "OK"

def run_flask(eq=None, port=5000):
  global EXT_RES_QUEUE, LOG
  # get a logger for debugging purposes
  LOG = init_logger("FlaskServer", port=port)
  if not eq:
    EXT_RES_QUEUE = Queue()
  else :
    EXT_RES_QUEUE = eq
  app.run('127.0.0.1', port=port, debug=False)

if __name__ == "__main__" :
  # unit test
  run_flask()
