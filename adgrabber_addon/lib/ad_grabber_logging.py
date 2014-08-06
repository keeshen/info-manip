import logging
import logging.handlers
import urllib2
import json
import jsonpickle

"""
Handles all the custom logging methods used by ad grabber
"""
class JSONHTTPHandler(logging.Handler):
  """
  Handler class that sends log records in  json encoded format to
  a Web server, using only the POST method
  """
  def __init__(self, host, url, machineid):
    """
    Initialize instance with host and request URL 
    """
    logging.Handler.__init__(self)
    self.machineid = machineid
    if not host.startswith('http://'):
      raise Exception('URL should start with http://')
    self.host = host
    self.url = url

  def emit(self, record):
    """
    Emit a record.
    Send the record to the Web server as JSON encoded object
    """
    try:
      payload = {}
      ctype = {'Content-Type' : 'application/json'}
      payload['id'] = self.machineid
      payload['message'] = "fpath:%s line:%s funcName:%s :: %s"% (
          record.pathname, record.lineno,record.funcName, record.getMessage())
      #data = json.dumps(payload)
      data = jsonpickle.encode(payload)
      req = urllib2.Request('%s/%s' % (self.host, self.url), data, ctype)
      f = urllib2.urlopen(req, data)
      jsonpickle.decode(f.read())
    except urllib2.URLError:
      pass
    except:
      self.handleError(record)

class AdgLogFormatter(logging.Formatter):
  """ Subclass of Formatter so we can supply custom fmt values for adgrabber
  """
  def __init__(self,fmt=None, datefmt=None, port=None, name=None):
    """ 
    Initialize the base formatter with optional port param (opt) and name
    """
    logging.Formatter.__init__(self, fmt, datefmt)
    self.name = name
    self.port = port

  def format(self, record):
    msg = []
    if self.name :
      msg.append(self.name)
    if self.port : 
      msg.append("Port:%d " % self.port)
    msg.append(logging.Formatter.format(self,record))
    return ''.join(msg)

def init_logger(logname, loglevel="DEBUG", port=None, error_server=None,
    machineID=None):
  """ Returns a Logger Object specified by the log name
  """
  loglevel = loglevel.upper()
  if loglevel == 'DEBUG': loglevel = logging.DEBUG
  elif loglevel == 'WARN' :loglevel = logging.WARN
  elif loglevel == 'ERROR': loglevel = logging.ERROR
  elif loglevel == 'INFO' : loglevel = logging.INFO

  LOG = logging.getLogger(logname)
  handler_debug = logging.StreamHandler()
  handler_debug.setLevel(logging.DEBUG)
  formatter_debug = AdgLogFormatter("-- %(levelname)s %(filename)s %(funcName)s %(lineno)s %(asctime)s :: %(message)s", port=port)
  handler_debug.setFormatter(formatter_debug)
  LOG.addHandler(handler_debug) 
  
  if error_server:
    #handler_error = JSONHTTPHandler(error_server, 'error', machineID)
    handler_error = logging.StreamHandler()
    handler_error.setLevel(logging.ERROR)
    formatter_error = AdgLogFormatter("-- %(levelname)s %(filename)s %(funcName)s %(lineno)s %(asctime)s :: %(message)s\n", port=port, name=logname)
    handler_error.setFormatter(formatter_error)
    LOG.addHandler(handler_error)
  LOG.setLevel(loglevel)
  return LOG  

