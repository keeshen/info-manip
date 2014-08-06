class LogFilter(object):
  def __init__(self, level):
    self.__level = level
  def filter(self, logRecord):
    return logRecord.levelno <= self.__level

class RegExp(object):
  """ 
  Convenient class to 
  """
  def __init__(self):
    pass 

class WebBug(object):
  """ A data structure containing the attributes of a webbug.
  """
  def __init__(self, name="", src="", affiliation = "", bug_type="",
      matched_pattern ="", pathname=""):
    self.name = name # Company name of this bug
    self.src = src # src url of this webbug
    self.bug_type = bug_type # ghostery's classification of this bug
    self.ftype = ""
    self.filepath = ""
    self.uuid = ""
    self.height = "" # for img/swf only
    self.width = "" # for img/swf only
    self.isad = False
    self.affiliation = affiliation # is this bug daa, or nai affiliated
    self.matched_pattern = matched_pattern # regex pattern which matched this
    self.pathname = pathname
    #TODO store the html dom element of the webbug
  
  def get_name(self):
    return self.name

  def get_uuid(self):
    return self.uuid
  
  def get_src(self):
    return self.src

  def get_filetype(self):
    return self.ftype
  
  def get_filepath(self):
    return self.filepath

  def get_dimension(self):
    return self.height, self.width

  def is_ad(self):
    return self.isad

  def set_uuid(self, uuid):
    self.uuid = uuid

  def set_dimension(self, height, width):
    self.height = height
    self.width = width
  def set_filepath(self, fp):
    self.filepath = fp
#
  def set_filetype(self, ftype):
    self.ftype = ftype
#
  def set_is_ad(self, isad):
    self.isad = isad

  def __str__(self):
    return str({ 'name' : self.name, 'src' : self.src, 'bug_type' : self.bug_type,
        'ftype': self.ftype, 'isad' : self.isad})
  def __eq__(self,other):
    return self.name+self.src ==  other.get_name() + other.get_src()
  def __neq__(self, other):
    return self.name+self.src != other.get_name() + other.get_src()
  def __hash__(self):
    return hash(self.name + self.src)

class Session(object):
  """
  Organizes the results of previous 'runs' 
  """
  def __init__(self,start_time, vmid=""):
    # info on exp duration
    self.start_time = None

    self.vmid = None
 
    self.total_ads = 0
    self.total_uniq_ads = 0

if __name__ == "__main__":
  w = WebBug(name="aliga", src="sss", affiliation = "afiliation", bug_type="b",
            matched_pattern ="e", pathname="d")
  d = WebBug(name="aliga", src="sss", affiliation = "afiliation", bug_type="b",
            matched_pattern ="e", pathname="d")
  print w
  print d
  print w == d
  b = {}
  b[w] = 1
