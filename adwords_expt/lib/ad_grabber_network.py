import urllib2
import jsonpickle
import logging
import datetime

class Communicator(object):
  def __init__(self, ID, SERVER, logtype):
    self.ID = ID
    self.SERVER = SERVER
    self.LOG = logging.getLogger(logtype)

  def send_request(self,payload, page, retry=3):
    """ Sends a request to the scheduler. Payload is a dict object 
        Returns a dict containing json decoded response
        ID should exist as a global module fore using this function call 
    """
    retry_count = 0
    while retry_count < retry:
      retry_count += 1
      response = ""
      try:
        payload['ID'] = self.ID
        date = datetime.datetime.now()
        datestr = '%s-%s-%s_%s:%s' % (date.year, date.month, date.day, 
date.hour, date.minute)
        payload['DATE'] = datestr 
        data = jsonpickle.encode(payload)
        ctype = {'Content-Type':'application/json'}
        req = urllib2.Request('%s/%s' % (self.SERVER,page), data, ctype)
        f = urllib2.urlopen(req,data)
        response = jsonpickle.decode(f.read())
        return response
      except urllib2.URLError:
        self.LOG.error('Cannot reach server:%s for req:%s' % (self.SERVER, page))
        continue
      except Exception as e:
        self.LOG.error("Some other exception occured in send_request "
          "of Communicator class: %s payload size=%d" % (e, len(data)))
        continue
    return False
