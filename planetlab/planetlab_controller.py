#! /usr/bin/env python


import xmlrpclib

PL_NODE_FILE = 'planetlab_ip.txt'
SLICE_NAME = 'michigan_nsrg'

def load_pl_nodes():
  with open(PL_NODE_FILE,'r') as frdr:
    nodes = [line.strip() for line in frdr]
  return nodes

def pl_authenticate():
  auth = {}
  auth['Username'] = 'qks@umich.edu'
  auth['AuthString'] = 
  auth['AuthMethod'] = 
  return auth

def main():
  api_server = xmlrpclib.ServerProxy('https://www.planet-lab.org/PLCAPI/')
  pl_nodes_list = load_pl_nodes()
  auth = pl_authenticate()
  ret_code = api_server.AddSliceToNodes(auth, SLICE_NAME, pl_nodes_list)
  print ret_code
if __name__ == "__main__":
  main()
