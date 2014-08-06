import json
import re

class AdRegEx(object):
  """
  A class to hold compiled ad regexes
  """
  def __init__(self):
    self.patterns = []
    with open('bugs.json', 'r') as frdr:
      bugsJson = json.load(frdr)
      for category in ['lsos','bugs']:
        for bug in bugsJson[category]:
          bug_name = bug['name']
          bug_type = bug['type']
          try :
            wb = WebBugRegex(bug_name, bug['pattern'], bug_type)
            if wb not in self.patterns:
              self.patterns.append(wb)
          except Exception:
            print "Invalid regex expression for pattern: ", bug['pattern']

  def search(self, pattern):
    """
    @type pattern: str
    @param pattern: a regex pattern 
    @return: isBug?, Bug_name, Bug_type
    """
    for wbr in self.patterns:
      if wbr.search(pattern):
        return True, wbr.get_bug_name(), wbr.get_bug_type()
    return False, None, None

class WebNode(object):
  """
  """
  def __init__(self, domain, isBug, bugName="", bugType=""):
    self.domain = domain
    self.isBug = isBug
    self.bugName = bugName
    self.bugType = bugType
    self.reqresp = []
    self.parents = []
    self.children = []
    self.cookies = []

  def add_parent(self, parent):
    if parent not in self.parents:
      self.parents.append(parent)
  def add_reqresp(self, reqresp):
    self.reqresp.append(reqresp)
  def set_cookies(self, cookies_list):
    """
    Cookies is a list where each element is a cookie, represented by a
dictionary that contains all the key-value pairs of the cookie
    """
    self.cookies = cookies_list
    
  def add_child(self, child):
    if child not in self.children: 
      self.children.append(child)
  def get_reqresp(self):
    """
    returns a list of paths found in Requests made to this domain
    """
    return self.reqresp
  def get_cookies(self):
    """
    returns a list of cookie values set to this domain
    """
    return self.cookies

  def get_children(self):
    """
    returns a list of child nodes to this domain.
    We define a node to be a child of this domain if HTTP requests were made to the domain of the node.
    """
    return self.children
  def get_parents(self):
    """
    returns a list of parents to this domain. It is possible for a node to have
multiple parents if each of the parent has made a request to the node. 
    """
    return self.parents
  def get_domain(self):
    return self.domain
  def __eq__(self, other):
    return self.domain == other.domain
  def __neq__(self, other):
    return self.domain != other.domain
  def __hash__(self):
    return hash(self.domain)
  def __str__(self):
    return 'domain:%s  isBug:%s  parent:%s' % (self.domain, self.isBug, self.parent)
  

class WebBugRegex(object):
  """
  """
  def __init__(self, name, pattern, bug_type):
    self.name = name
    self.bug_type = bug_type
    self.pattern = pattern
    self.regex = re.compile(pattern)
  def get_bug_name(self):
    return self.name
  def get_bug_type(self):
    return self.bug_type
  def get_bug_pattern(self):
    return self.pattern
  def search(self, string):
    return self.regex.search(string)
  def __str__(self):
    return str("name: %s, pattern:%s" % (self.name, self.pattern))
  def __eq__(self,other):
    return self.name + self.pattern == other.name + other.pattern
  def __neq__(self, other):
    return self.name + self.pattern != other.name + other.pattern
  def __hash__(self):
    return hash(self.name + self.pattern)
